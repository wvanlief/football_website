import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

from backend.database import Team, Fixture, Tournament, Competition, SessionLocal
from backend.services.ingestion import NameNormalizer
from backend.services.odds import update_odds_from_api, calculate_default_odds
from backend.services.knockout import propagate_knockout_fixtures
from backend.services.queries import (
    evaluate_nations_league_promotions,
    fixtures_in_match_window,
    invalidate_fixtures_cache,
    score_text,
)

from backend.services.simulation import run_monte_carlo_simulation
from backend.services.standings import recalculate_tournament_team_standings
from backend.services.format_adapters import (
    CompetitionSyncAdapter,
    STAGE_MAPPING,
    STADIUM_TIMEZONES,
    parse_match_date,
)

from backend.services.providers.football_data import (
    COMPETITION_CODE_MAP,
    FootballDataProvider,
    PROVIDER_NAME,
    apply_matches_to_existing_fixtures,
    get_football_data_org_key,
)
from backend.services.providers.football_api import FootballApiProvider, live_score_fields as football_api_live_fields
from backend.services.providers.highlightly import HighlightlyProvider, live_score_fields as highlightly_live_fields
from backend.services.ingestion.fixture_upserter import FixtureUpserter
from backend.crud.mapping import get_competition_by_external_id
from backend.utils import fetch_json_with_retry, fetch_url_with_retry, fetch_json


def _tournament_id_for_match(db: Session, match: dict) -> int | None:
    competition_data = match.get("competition") or {}
    competition = None
    external_id = competition_data.get("id")
    if external_id is not None:
        competition = get_competition_by_external_id(db, PROVIDER_NAME, external_id)

    if competition is None:
        code = competition_data.get("code")
        name = competition_data.get("name")
        canonical_name = next(
            (candidate for candidate, mapped_code in COMPETITION_CODE_MAP.items() if mapped_code == code),
            name,
        )
        if canonical_name:
            competition = db.query(Competition).filter(
                Competition.name == canonical_name
            ).first()

    if competition is None:
        return None

    tournament = db.query(Tournament).filter(
        Tournament.competition_id == competition.id,
        Tournament.status == "Active",
    ).first()
    return tournament.id if tournament else None

def _yesterday_and_today() -> tuple[str, str]:
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    return yesterday_str, today_str


def sync_football_data_matches(db: Session, date_from: str, date_to: str) -> tuple[int, int]:
    """Fetch Football-Data.org matches for a date range and update existing fixtures.

    Returns (non_finished_updates, finished_count).
    """
    if not get_football_data_org_key():
        print("FOOTBALL_DATA_ORG_KEY not configured. Skipping Football-Data.org match sync.")
        return 0, 0

    print(f"Fetching Football-Data.org matches dateFrom={date_from} dateTo={date_to}...")
    provider = FootballDataProvider()
    matches = provider.fetch_matches(date_from, date_to)
    print(f"Received {len(matches)} Football-Data.org matches for {date_from}..{date_to}.")
    updated = 0
    finished = 0
    matches_by_tournament: dict[int | None, list[dict]] = {}
    for match in matches:
        tournament_id = _tournament_id_for_match(db, match)
        matches_by_tournament.setdefault(tournament_id, []).append(match)

    for tournament_id, tournament_matches in matches_by_tournament.items():
        match_updated, match_finished = apply_matches_to_existing_fixtures(
            db,
            tournament_matches,
            tournament_id=tournament_id,
        )
        updated += match_updated
        finished += match_finished
    db.commit()
    print(f"Football-Data.org sync {date_from}..{date_to}: updated {updated}, finished {finished}.")
    return updated, finished


def backfill_football_data_results(db: Session, date_from: str, date_to: str) -> dict:
    """Apply Football-Data.org scores for an explicit date range without refreshing odds."""
    updated, finished = sync_football_data_matches(db, date_from, date_to)

    tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
    if not tournaments:
        tournaments = db.query(Tournament).all()

    try:
        propagate_knockout_fixtures(db)
    except Exception as e:
        print(f"Warning: propagate_knockout_fixtures failed: {e}")
    db.commit()

    for tourney in tournaments:
        try:
            recalculate_tournament_team_standings(db, tourney.id)
            if tourney.competition and tourney.competition.format_engine == "nations_league":
                evaluate_nations_league_promotions(db, tourney.id)
        except Exception as e:
            print(f"Warning: Failed to recalculate standings/promotions for tournament {tourney.id}: {e}")
    db.commit()

    try:
        from backend.services.feed_builder import build_fixtures_feed_cache
        build_fixtures_feed_cache(db)
    except Exception as e:
        print(f"Warning: Failed to rebuild feed cache: {e}")

    return {
        "status": "success",
        "date_from": date_from,
        "date_to": date_to,
        "fixtures_updated_results": updated,
        "fixtures_finished": finished,
    }


def sync_global_date_results(db: Session, date_from: str, date_to: str) -> tuple:
    """
    Fetches yesterday and today's matches in one Football-Data.org date-range query
    and settles finished matches atomically.

    Matches returned fixtures to existing database records by prefixed provider id
    (`fd_{id}`) or by home/away team + kickoff window. Finished fixtures are settled
    via finish_fixture(). Returns (created_count, updated_count).
    """
    updated, finished = sync_football_data_matches(db, date_from, date_to)
    return 0, updated + finished


_KICKOFF_TOLERANCE = timedelta(hours=12)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _kickoff_matches(fixture: Fixture, kickoff: datetime | None) -> bool:
    if kickoff is None or fixture.date_utc is None:
        return True
    return abs(_as_utc(fixture.date_utc) - _as_utc(kickoff)) <= _KICKOFF_TOLERANCE


def _provider_stamp(prefix: str, match_id) -> str | None:
    if match_id is None:
        return None
    return f"{prefix}{match_id}"


def _stamp_blank_api_id(fixture: Fixture, stamp: str | None) -> None:
    if stamp and not fixture.api_id:
        fixture.api_id = stamp


def _write_live_score(fixture: Fixture, status: str, home_score, away_score) -> str | None:
    """Write status and scores only. This is the only score writer besides settlement.

    A concluded state is stored as Finished so the homepage can show the score.
    It does not call finish_fixture: live polling does not settle streaks,
    watchability, or standings, and it does not rebuild the feed.
    """
    if status not in ("Live", "Finished"):
        return None
    if status == "Finished" and (home_score is None or away_score is None):
        status = "Live"
    changed = False
    if fixture.status != status:
        fixture.status = status
        changed = True
    if home_score is not None and fixture.home_score != home_score:
        fixture.home_score = home_score
        changed = True
    if away_score is not None and fixture.away_score != away_score:
        fixture.away_score = away_score
        changed = True
    if not changed:
        return None
    return "finished" if fixture.status == "Finished" else "updated"


def _competitions_in_window(fixtures: list[Fixture]) -> list[Competition]:
    competitions = []
    seen = set()
    for fixture in fixtures:
        tournament = fixture.tournament
        competition = tournament.competition if tournament else None
        if competition is None or competition.id in seen:
            continue
        seen.add(competition.id)
        competitions.append(competition)
    competitions.sort(key=lambda competition: competition.name)
    return competitions


def _find_window_fixture(candidates, competition_id: int, home_name: str, away_name: str, kickoff):
    normalizer = NameNormalizer()
    hits = []
    for fixture in candidates:
        tournament = fixture.tournament
        competition = tournament.competition if tournament else None
        if competition is None or competition.id != competition_id:
            continue
        home = fixture.home_team.name if fixture.home_team else ""
        away = fixture.away_team.name if fixture.away_team else ""
        if not normalizer.match_names(home, home_name) or not normalizer.match_names(away, away_name):
            continue
        if not _kickoff_matches(fixture, kickoff):
            continue
        hits.append(fixture)
    if len(hits) == 1:
        return hits[0]
    return None


def _highlightly_row_for_competition(league_name: str, competition: Competition) -> bool:
    if not league_name:
        return True
    canonical = _HIGHLIGHTLY_LEAGUE_NAMES.get(league_name, league_name)
    query_name = _HIGHLIGHTLY_QUERY_NAMES.get(competition.name, competition.name)
    return canonical == competition.name or league_name in {competition.name, query_name}


def _missed_competition_for_football_api(fields: dict, missed: list[Competition]) -> Competition | None:
    league_id = fields.get("league_id")
    league_name = fields.get("league_name") or ""
    for competition in missed:
        if league_id is not None and competition.api_league_id == league_id:
            return competition
        if league_name and league_name == competition.name:
            return competition
    return None


def _apply_live_fields(fixture: Fixture, fields: dict, stamp_prefix: str) -> str | None:
    _stamp_blank_api_id(fixture, _provider_stamp(stamp_prefix, fields.get("match_id")))
    return _write_live_score(fixture, fields["status"], fields["home_score"], fields["away_score"])


def _record_live_write(outcome, fixture: Fixture, patches: list, updated: int, finished: int):
    if outcome == "updated":
        updated += 1
    elif outcome == "finished":
        finished += 1
    else:
        return updated, finished
    patches.append({
        "id": fixture.id,
        "status": fixture.status,
        "score": score_text(fixture.status, fixture.home_score, fixture.away_score),
    })
    return updated, finished


def _patch_cached_scores(patches: list[dict]) -> None:
    if not patches:
        return
    try:
        from backend.services.feed_builder import patch_feed_cache_scores
        patch_feed_cache_scores(patches)
        invalidate_fixtures_cache()
    except Exception as exc:
        print(f"Warning: Failed to patch feed cache scores: {exc}")


def sync_global_live_scores(db: Session) -> tuple:
    """
    Poll Highlightly for each competition's distinct UTC kickoff dates.

    One API-Football ``GET /fixtures?live=all`` runs only for competitions
    Highlightly missed (error, empty, or quota). Writes status, home_score,
    and away_score. A blank api_id may take an hl_ or fa_ stamp. Does not
    replace an fd_ stamp, create teams or fixtures, settle the match, or
    fall through to Football-Data.org. Returns (updated_count, finished_count).
    """
    window = fixtures_in_match_window(db)
    competitions = _competitions_in_window(window)
    if not competitions:
        return 0, 0

    highlightly = HighlightlyProvider()
    missed: list[Competition] = []
    covered_fixture_ids = set()
    updated = finished = 0
    patches: list[dict] = []

    for competition in competitions:
        league_name = _HIGHLIGHTLY_QUERY_NAMES.get(competition.name, competition.name)
        dates = sorted({
            _as_utc(fixture.date_utc).date().isoformat()
            for fixture in window
            if fixture.date_utc is not None
            and fixture.tournament is not None
            and fixture.tournament.competition_id == competition.id
        })
        rows = []
        for date in dates:
            try:
                rows.extend(highlightly.fetch_matches_by_date(date, league_name=league_name) or [])
            except Exception as exc:
                print(f"Highlightly live poll failed for {competition.name} on {date}: {exc}")
        for item in rows:
            fields = highlightly_live_fields(item)
            if not fields or not _highlightly_row_for_competition(fields["league_name"], competition):
                continue
            fixture = _find_window_fixture(
                window,
                competition.id,
                fields["home_name"],
                fields["away_name"],
                fields["date_utc"],
            )
            if fixture is None:
                continue
            covered_fixture_ids.add(fixture.id)
            outcome = _apply_live_fields(fixture, fields, "hl_")
            updated, finished = _record_live_write(outcome, fixture, patches, updated, finished)
        if any(
            fixture.tournament and fixture.tournament.competition_id == competition.id
            and fixture.id not in covered_fixture_ids
            for fixture in window
        ):
            missed.append(competition)

    if missed:
        print(
            "Highlightly missed "
            + ", ".join(competition.name for competition in missed)
            + "; trying one API-Football live=all call."
        )
        live_rows, failed = FootballApiProvider().fetch_live_fixtures()
        if live_rows and not failed:
            for item in live_rows:
                fields = football_api_live_fields(item)
                if not fields:
                    continue
                competition = _missed_competition_for_football_api(fields, missed)
                if competition is None:
                    continue
                fixture = _find_window_fixture(
                    window,
                    competition.id,
                    fields["home_name"],
                    fields["away_name"],
                    fields["date_utc"],
                )
                if fixture is None or fixture.id in covered_fixture_ids:
                    continue
                outcome = _apply_live_fields(fixture, fields, "fa_")
                updated, finished = _record_live_write(outcome, fixture, patches, updated, finished)

    if db.dirty:
        db.commit()
    _patch_cached_scores(patches)
    return updated, finished


_HIGHLIGHTLY_LEAGUE_NAMES = {
    "UEFA Europa Conference League": "UEFA Conference League",
}
_HIGHLIGHTLY_QUERY_NAMES = {canonical: raw for raw, canonical in _HIGHLIGHTLY_LEAGUE_NAMES.items()}


def _active_tournament_for_competition(db: Session, competition: Competition | None):
    if competition is None or competition.name in COMPETITION_CODE_MAP:
        return None
    return db.query(Tournament).filter(
        Tournament.competition_id == competition.id,
        Tournament.status == "Active",
    ).first()


def _upsert_payloads(db: Session, grouped: dict) -> tuple[int, int]:
    upserter = FixtureUpserter()
    created = updated = 0
    for tournament, payloads in grouped.items():
        if not payloads:
            continue
        result = upserter.upsert_fixtures(
            db, tournament, payloads, competition=tournament.competition
        )
        created += result.created
        updated += result.updated
    return created, updated


def _apply_football_api_date(db: Session, provider: FootballApiProvider, fixtures: list[dict]) -> tuple[int, int]:
    grouped: dict = {}
    for item in fixtures:
        league = item.get("league") or {}
        league_id = league.get("id")
        competition = None
        if league_id is not None:
            competition = db.query(Competition).filter(
                Competition.api_league_id == league_id
            ).first()
        tournament = _active_tournament_for_competition(db, competition)
        if tournament is None:
            continue
        payload = provider.normalize_fixture_payload(
            db, item, tournament.id, competition.type or "Cup"
        )
        if payload:
            grouped.setdefault(tournament, []).append(payload)
    return _upsert_payloads(db, grouped)


def _apply_highlightly_date(db: Session, provider: HighlightlyProvider, matches: list[dict]) -> tuple[int, int]:
    grouped: dict = {}
    for item in matches:
        league = item.get("league")
        raw_name = league.get("name") if isinstance(league, dict) else league
        name = _HIGHLIGHTLY_LEAGUE_NAMES.get(raw_name or "", raw_name)
        competition = db.query(Competition).filter(Competition.name == name).first() if name else None
        tournament = _active_tournament_for_competition(db, competition)
        if tournament is None:
            continue
        payload = provider.normalize_fixture_payload(
            db, item, tournament.id, competition.type or "Cup"
        )
        if payload:
            grouped.setdefault(tournament, []).append(payload)
    return _upsert_payloads(db, grouped)


def sync_non_fd_date_overlay(db: Session, dates: list[str]) -> tuple[int, int]:
    """Insert or update cups that Football-Data.org does not own.

    Typical daily cost is 2 Football-API ``GET /fixtures?date=`` calls
    (yesterday and today). Highlightly date pages run only when a Football-API
    date request fails or returns an empty list, or lacks an active competition.
    Big 5 and UCL stay on Football-Data.org.
    """
    football_api = FootballApiProvider()
    highlightly = HighlightlyProvider()
    created = updated = 0
    for match_date in dates:
        fixtures, failed = football_api.fetch_fixtures_by_date(match_date)
        active_tournaments = [
            tournament for tournament in db.query(Tournament).filter(Tournament.status == "Active").all()
            if tournament.competition and tournament.competition.name not in COMPETITION_CODE_MAP
        ]
        if fixtures and not failed:
            day_created, day_updated = _apply_football_api_date(db, football_api, fixtures)
            covered_league_ids = {
                (item.get("league") or {}).get("id") for item in fixtures
                if (item.get("league") or {}).get("id") is not None
            }
            fallback_tournaments = [
                tournament for tournament in active_tournaments
                if tournament.competition.api_league_id not in covered_league_ids
            ]
        else:
            print(
                f"Football-API date {match_date} was "
                f"{'failed' if failed else 'empty'}; trying Highlightly."
            )
            day_created = day_updated = 0
            fallback_tournaments = active_tournaments
        rows = []
        for tournament in fallback_tournaments:
            name = tournament.competition.name
            rows.extend(highlightly.fetch_matches_by_date(
                match_date, league_name=_HIGHLIGHTLY_QUERY_NAMES.get(name, name)
            ))
        if rows:
            hl_created, hl_updated = _apply_highlightly_date(db, highlightly, rows)
            day_created += hl_created
            day_updated += hl_updated
        created += day_created
        updated += day_updated
    db.commit()
    return created, updated


def update_results_and_odds(db: Session) -> dict:
    """
    Main daily update task.

    Typical day: 1 Football-Data.org range call (yesterday and today) for the
    Big 5 and UCL, then 2 Football-API date calls for UEL, Conference, and other
    cups. Highlightly fills active competitions missing from each date's
    Football-API response and handles failed or empty responses.
    The live score poll is separate and does not rebuild this feed.
    Rebuilds the fixtures feed cache after the overlay.
    """
    yesterday_str, today_str = _yesterday_and_today()
    fixtures_created, fixtures_updated_results = sync_global_date_results(
        db, yesterday_str, today_str
    )
    try:
        overlay_created, overlay_updated = sync_non_fd_date_overlay(
            db, [yesterday_str, today_str]
        )
    except Exception as exc:
        db.rollback()
        print(f"Warning: Non-FD date overlay failed: {exc}")
        overlay_created = overlay_updated = 0
    fixtures_created += overlay_created
    fixtures_updated_results += overlay_updated

    # Fallback to tournament adapters if global date sync did not find/update fixtures
    if fixtures_created == 0 and fixtures_updated_results == 0:
        tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
        for tourney in tournaments:
            adapter = CompetitionSyncAdapter()
            c, u = adapter.sync_results(db, tourney)
            fixtures_created += c
            fixtures_updated_results += u

    tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
    if not tournaments:
        tournaments = db.query(Tournament).all()

    for tourney in tournaments:
        comp = tourney.competition
        if comp and comp.odds_api_sport_key:
            try:
                tourney_fixtures = db.query(Fixture).filter(Fixture.tournament_id == tourney.id).all()
                update_odds_from_api(tourney_fixtures, db, sport_key=comp.odds_api_sport_key)
            except Exception as e:
                print(f"Warning: Failed to update odds for tournament {tourney.id}: {e}")

    try:
        propagate_knockout_fixtures(db)
    except Exception as e:
        print(f"Warning: propagate_knockout_fixtures failed: {e}")
        
    db.commit()

    for tourney in tournaments:
        try:
            recalculate_tournament_team_standings(db, tourney.id)
            if tourney.competition and tourney.competition.format_engine == "nations_league":
                evaluate_nations_league_promotions(db, tourney.id)
        except Exception as e:
            print(f"Warning: Failed to recalculate standings/promotions for tournament {tourney.id}: {e}")
    db.commit()

    simulation_status = "Simulation temporarily disabled"

    try:
        from backend.services.feed_builder import build_fixtures_feed_cache
        build_fixtures_feed_cache(db)
    except Exception as e:
        print(f"Warning: Failed to rebuild feed cache: {e}")

    return {
        "status": "success",
        "fixtures_created": fixtures_created,
        "fixtures_updated_results": fixtures_updated_results,
        "simulation": simulation_status
    }

def update_live_scores(db: Session, force: bool = False) -> dict:
    """
    Lightweight updater for live scores. Only queries when a match is in the window.

    Writes status and scores, then patches those two fields on the feed cache.
    Does not settle the match or rebuild the feed.
    """
    if not fixtures_in_match_window(db) and not force:
        print("No active match window detected in DB. Skipping live API call.")
        return {"status": "skipped", "message": "No active match window."}

    updated, finished = sync_global_live_scores(db)
    return {
        "status": "success",
        "fixtures_updated_live": updated,
        "fixtures_finished": finished,
        "simulation": "Simulation temporarily disabled",
    }

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="findfootball.games Database Ingestion and Update Task")
    parser.add_argument("--live", action="store_true", help="Run lightweight live-score update only")
    parser.add_argument("--force", action="store_true", help="Force updates even outside active match windows")
    parser.add_argument("--date-from", dest="date_from", help="Backfill start date YYYY-MM-DD (with --date-to)")
    parser.add_argument("--date-to", dest="date_to", help="Backfill end date YYYY-MM-DD (with --date-from)")
    args = parser.parse_args()

    if bool(args.date_from) != bool(args.date_to):
        parser.error("--date-from and --date-to must be used together")
    if args.live and args.date_from:
        parser.error("--live cannot be combined with --date-from/--date-to")
    
    db = SessionLocal()
    try:
        if args.date_from:
            print(f"Running Football-Data.org results backfill {args.date_from}..{args.date_to}...")
            result = backfill_football_data_results(db, args.date_from, args.date_to)
            print(json.dumps(result, indent=2))
        elif args.live:
            print("Running live-score updater...")
            result = update_live_scores(db, force=args.force)
            print(json.dumps(result, indent=2))
        else:
            print("Running full results and odds updater...")
            result = update_results_and_odds(db)
            print(json.dumps(result, indent=2))
            from backend.services.hygiene import run_hygiene_report
            print("Running database hygiene report...")
            hygiene_report = run_hygiene_report(db)
            print(json.dumps({
                "split_seasons": len(hygiene_report["split_seasons"]),
                "duplicate_fixtures": len(hygiene_report["duplicate_fixtures"]),
                "world_cup_rows": len(hygiene_report["world_cup_dates_on_other_tournaments"]["rows"]),
                "european_cup_leftovers": hygiene_report["european_cup_leftovers"]["total"],
            }, indent=2))
    finally:
        db.close()
