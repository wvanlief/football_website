import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

from backend.database import Team, Fixture, Tournament, Competition, SessionLocal
from backend.services.ingestion import NameNormalizer
from backend.services.odds import update_odds_from_api, calculate_default_odds
from backend.services.knockout import propagate_knockout_fixtures
from backend.services.queries import evaluate_nations_league_promotions, invalidate_fixtures_cache

from backend.services.simulation import run_monte_carlo_simulation
from backend.services.standings import recalculate_tournament_team_standings
from backend.services.format_adapters import (
    get_format_adapter,
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
from backend.services.providers.football_api import FootballApiProvider
from backend.services.providers.highlightly import HighlightlyProvider
from backend.services.ingestion.fixture_upserter import FixtureUpserter
from backend.crud.mapping import get_competition_by_external_id
from backend.utils import fetch_json_with_retry, fetch_url_with_retry, fetch_json


def normalize_team_name(name: str) -> str:
    """Normalizes a team name using the NameNormalizer."""
    return NameNormalizer().normalize(name)

def matches_team_name(db_name: str, api_name: str) -> bool:
    """Checks if two team names match using fuzzy matching and alias mapping."""
    return NameNormalizer().match_names(db_name, api_name)


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


def sync_global_live_scores(db: Session) -> tuple:
    """
    Fetches in-window live or delayed scores from Football-Data.org matches.

    Delayed scores on the free plan are acceptable. Matches that transition to
    Finished are settled via finish_fixture(). Returns (updated_count, finished_count).

    The 15-minute live cron stays on Football-Data.org. It does not call
    Football-API or Highlightly.
    """
    date_from, date_to = _yesterday_and_today()
    return sync_football_data_matches(db, date_from, date_to)


_HIGHLIGHTLY_LEAGUE_NAMES = {
    "UEFA Europa Conference League": "UEFA Conference League",
}


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
    date returns HTTP 4xx or an empty list. Big 5 and UCL stay on Football-Data.org.
    """
    football_api = FootballApiProvider()
    highlightly = HighlightlyProvider()
    created = updated = 0
    for match_date in dates:
        fixtures, failed = football_api.fetch_fixtures_by_date(match_date)
        if fixtures and not failed:
            day_created, day_updated = _apply_football_api_date(db, football_api, fixtures)
        else:
            print(
                f"Football-API date {match_date} was "
                f"{'4xx' if failed else 'empty'}; trying Highlightly."
            )
            rows = highlightly.fetch_matches_by_date(match_date)
            day_created, day_updated = _apply_highlightly_date(db, highlightly, rows)
        created += day_created
        updated += day_updated
    db.commit()
    return created, updated


def update_results_and_odds(db: Session) -> dict:
    """
    Main daily update task.

    Typical day: 1 Football-Data.org range call (yesterday and today) for the
    Big 5 and UCL, then 2 Football-API date calls for UEL, Conference, and other
    cups. Highlightly is the failover when Football-API is 4xx or empty.
    The 15-minute live path does not use those providers.
    Rebuilds the fixtures feed cache after the overlay.
    """
    yesterday_str, today_str = _yesterday_and_today()
    fixtures_created, fixtures_updated_results = sync_global_date_results(
        db, yesterday_str, today_str
    )
    overlay_created, overlay_updated = sync_non_fd_date_overlay(
        db, [yesterday_str, today_str]
    )
    fixtures_created += overlay_created
    fixtures_updated_results += overlay_updated

    # Fallback to tournament adapters if global date sync did not find/update fixtures
    if fixtures_created == 0 and fixtures_updated_results == 0:
        tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
        for tourney in tournaments:
            adapter = get_format_adapter(tourney.competition.format_engine if tourney.competition else "", tourney.competition.name if tourney.competition else "")
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
    Lightweight updater for live scores. Only queries when matches are scheduled/live.
    """
    now_time = datetime.now(timezone.utc)
    
    window_start = now_time - timedelta(hours=3)
    window_end = now_time + timedelta(minutes=15)
    
    active_fixtures = db.query(Fixture).filter(
        Fixture.status != "Finished",
        Fixture.date_utc >= window_start,
        Fixture.date_utc <= window_end
    ).all()
    
    live_fixtures = db.query(Fixture).filter(Fixture.status == "Live").all()
    is_active_window = len(active_fixtures) > 0 or len(live_fixtures) > 0
    
    if not is_active_window and not force:
        print("No active match window detected in DB. Skipping live API call.")
        return {"status": "skipped", "message": "No active match window."}
        
    updated, finished = sync_global_live_scores(db)

    # Fallback to tournament adapters if global sync did not update any fixtures
    if updated == 0 and finished == 0:
        tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
        for tourney in tournaments:
            adapter = get_format_adapter(tourney.competition.format_engine if tourney.competition else "", tourney.competition.name if tourney.competition else "")
            u, f = adapter.sync_live_scores(db, tourney)
            updated += u
            finished += f

    if finished > 0 or updated > 0:
        try:
            propagate_knockout_fixtures(db)
        except Exception as e:
            pass
        db.commit()
        
        tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
        for tourney in tournaments:
            try:
                recalculate_tournament_team_standings(db, tourney.id)
                if tourney.competition and tourney.competition.format_engine == "nations_league":
                    evaluate_nations_league_promotions(db, tourney.id)
            except Exception as e:
                pass
        db.commit()

    simulation_status = "Simulation temporarily disabled"

    return {
        "status": "success",
        "fixtures_updated_live": updated,
        "fixtures_finished": finished,
        "simulation": simulation_status
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
    finally:
        db.close()
