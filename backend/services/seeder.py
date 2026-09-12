"""Thin seeding orchestrator.

Static World Cup data lives in ``backend/data/world_cup_2026.json``. Persistence
goes through ``TeamResolver`` and ``FixtureUpserter``; competition fixture
ingestion delegates to ``IngestionEngine``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.database import (
    Team,
    Player,
    Fixture,
    Competition,
    Tournament,
    TournamentTeam,
    PlayerContract,
)
from backend.scoring import score
from backend.services.ingestion import (
    NameNormalizer,
    COUNTRY_ISO_MAP,
    TeamResolver,
    FixtureUpserter,
    IngestionAborted,
)
from backend.services.odds import update_odds_from_api
from backend.services.elo import (
    elo_to_form,
    fetch_clubelo_ratings,
    fetch_current_elo_ratings,
    fuzzy_match_team,
    record_elo_history,
)
from backend.services.standings import recalculate_standings

NATIONAL_TEAM_ISO_CODES = COUNTRY_ISO_MAP

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_WORLD_CUP_JSON = _DATA_DIR / "world_cup_2026.json"
_EURO_DRAW_JSON = _DATA_DIR / "european_draw_2026.json"

_WC_STAGE_MAPPING = {
    "group": "Group Stage",
    "r32": "Round of 32",
    "round_of_32": "Round of 32",
    "r16": "Round of 16",
    "round_of_16": "Round of 16",
    "qf": "Quarter-final",
    "quarter": "Quarter-final",
    "semi": "Semi-final",
    "sf": "Semi-final",
    "third": "Third-place play-off",
    "final": "Final",
}


@lru_cache(maxsize=1)
def _load_world_cup_data() -> dict:
    with open(_WORLD_CUP_JSON, encoding="utf-8") as handle:
        return json.load(handle)


def get_fallback_matches() -> list[dict]:
    """World Cup 2026 group-stage fixtures from the static tournament dataset."""
    return list(_load_world_cup_data()["fallback_matches"])


@dataclass
class SeedResult:
    """Outcome of a ``seed(db, config)`` run."""

    status: str = "success"
    message: str = ""
    created: int = 0
    updated: int = 0
    odds_added: int = 0
    competition: Optional[str] = None
    league_id: Optional[int] = None
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        payload: dict[str, Any] = {"status": self.status}
        if self.message:
            payload["message"] = self.message
        if self.competition:
            payload["competition"] = self.competition
        if self.league_id is not None:
            payload["league_id"] = self.league_id
        if self.details:
            payload["details"] = self.details
        payload["fixtures_created"] = self.created
        payload["fixtures_updated"] = self.updated
        payload["odds_added"] = self.odds_added
        return payload


def seed(db: Session, config: dict) -> SeedResult:
    """Canonical seeding entry point. ``config['kind']`` selects the target."""
    kind = (config or {}).get("kind") or (config or {}).get("target") or "world_cup"
    league_id = config.get("league_id") if config else None
    fetch_squads = bool(config.get("fetch_squads")) if config else False

    if kind in ("world_cup", "fifa_world_cup"):
        return _seed_world_cup(db)
    if kind in ("european_cups", "euro_cups"):
        return _seed_european_cups(db, target_league_id=league_id)
    if kind in ("all", "default"):
        return _seed_all(db)
    if kind == "single":
        if league_id is None:
            return SeedResult(status="error", message="league_id is required for kind='single'")
        return _seed_single(db, league_id=int(league_id), fetch_squads=fetch_squads)
    if kind == "competition":
        return _seed_named_competition(db, config)

    return SeedResult(status="error", message=f"Unknown seed kind: {kind}")


def _get_or_create_competition(db: Session, name: str, **fields) -> Competition:
    comp = db.query(Competition).filter(Competition.name == name).first()
    if not comp:
        comp = Competition(name=name, **fields)
        db.add(comp)
        db.flush()
        return comp
    for key, value in fields.items():
        if value is not None:
            setattr(comp, key, value)
    db.flush()
    return comp


def _get_or_create_tournament(
    db: Session,
    competition: Competition,
    season: str,
    deactivate_other_seasons: bool = False,
) -> Tournament:
    if deactivate_other_seasons:
        db.query(Tournament).filter(
            Tournament.competition_id == competition.id,
            Tournament.season_name != season,
            Tournament.status == "Active",
        ).update({"status": "Completed"})

    tourney = db.query(Tournament).filter(
        Tournament.competition_id == competition.id,
        Tournament.season_name == season,
    ).first()
    if not tourney:
        tourney = Tournament(competition_id=competition.id, season_name=season, status="Active")
        db.add(tourney)
        db.flush()
        return tourney
    tourney.status = "Active"
    db.flush()
    return tourney


def _link_tournament_team(
    db: Session,
    tournament_id: int,
    team_id: int,
    group_name: Optional[str] = None,
) -> None:
    tt = db.query(TournamentTeam).filter(
        TournamentTeam.tournament_id == tournament_id,
        TournamentTeam.team_id == team_id,
    ).first()
    if not tt:
        db.add(TournamentTeam(
            tournament_id=tournament_id,
            team_id=team_id,
            group_name=group_name,
            tournament_status="Active",
        ))
        return
    if group_name and tt.group_name != group_name:
        tt.group_name = group_name


def _normalize_wc_stage(raw_stage: str) -> str:
    raw_stage = str(raw_stage or "").strip()
    stage_key = raw_stage.lower().replace("-", "_").replace(" ", "_")
    stage = _WC_STAGE_MAPPING.get(stage_key)
    if stage:
        return stage
    if "group" in stage_key:
        return "Group Stage"
    if "32" in stage_key:
        return "Round of 32"
    if "16" in stage_key:
        return "Round of 16"
    if "quarter" in stage_key:
        return "Quarter-final"
    if "semi" in stage_key:
        return "Semi-final"
    if "third" in stage_key or "3rd" in stage_key:
        return "Third-place play-off"
    if "final" in stage_key:
        return "Final"
    return raw_stage or "Group Stage"


def _fallback_fixture_payloads() -> list[dict]:
    payloads = []
    for match in get_fallback_matches():
        date_value = match.get("date")
        dt_utc = (
            datetime.fromisoformat(date_value)
            if date_value
            else datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
        )
        payloads.append({
            "api_id": str(match["id"]),
            "home_team_name": match["home"],
            "away_team_name": match["away"],
            "date_utc": dt_utc,
            "stage": match.get("stage", "Group Stage"),
            "status": match.get("status", "Scheduled"),
            "provider_name": "world_cup_static",
        })
    return payloads


def _seed_spotlight_players(db: Session, spotlight: dict) -> None:
    teams_by_name = {team.name: team.id for team in db.query(Team).all()}
    for team_name, players in spotlight.items():
        team_id = teams_by_name.get(team_name)
        if not team_id:
            continue
        for player in players:
            name = player["name"]
            position = player["position"]
            form = player["form"]
            existing = (
                db.query(Player)
                .join(PlayerContract, PlayerContract.player_id == Player.id)
                .filter(
                    Player.name == name,
                    PlayerContract.team_id == team_id,
                    PlayerContract.is_active.is_(True),
                )
                .first()
            )
            if existing:
                continue
            db_player = Player(name=name, position=position, form_score=form)
            db.add(db_player)
            db.flush()
            db.add(PlayerContract(
                player_id=db_player.id,
                team_id=team_id,
                type="Country",
                is_active=True,
            ))
    db.commit()


def _seed_world_cup(db: Session) -> SeedResult:
    wc = _load_world_cup_data()
    normalizer = NameNormalizer()
    resolver = TeamResolver(normalizer)
    upserter = FixtureUpserter(team_resolver=resolver)

    comp = _get_or_create_competition(
        db,
        wc.get("competition", "FIFA World Cup"),
        type="International",
        format_engine=wc.get("format_engine", "group_knockout"),
        odds_api_sport_key=wc.get("odds_api_sport_key", "soccer_fifa_world_cup"),
        home_advantage_elo=0,
        neutral_venue=True,
    )
    tourney = _get_or_create_tournament(db, comp, wc.get("season", "2026"))

    live_elo = dict(wc["elo_ratings"])
    try:
        print("Fetching live Elo ratings from eloratings.net...")
        fetched_elo = fetch_current_elo_ratings()
        live_elo.update(fetched_elo)
        print(f"Successfully fetched {len(fetched_elo)} Elo ratings from eloratings.net.")
    except Exception as exc:
        print(f"Failed to fetch live Elo ratings: {exc}. Falling back to JSON ratings.")

    now = datetime.now(timezone.utc)
    for group, teams_list in wc["groups"].items():
        for name in teams_list:
            elo = live_elo.get(name, 1700)
            team = resolver.resolve(
                db,
                provider_name="world_cup_static",
                raw_name=name,
                team_type="National",
                default_elo=elo,
                country_code=normalizer.get_country_code(name),
            )
            if not team:
                continue
            team.elo = elo
            team.form_score = elo_to_form(elo)
            team.win_streak = 4 if elo > 2000 else (2 if elo > 1850 else 0)
            team.draw_streak = 0
            team.loss_streak = 0
            team.elo_source = "eloratings"
            db.flush()
            _link_tournament_team(db, tourney.id, team.id, group_name=group)
            record_elo_history(db, team.id, elo, now)
    db.commit()

    _seed_spotlight_players(db, wc.get("spotlight_players") or {})

    payloads = _fallback_fixture_payloads()
    upsert = upserter.upsert_fixtures(db, tourney, payloads, competition=comp)
    db.commit()
    fixtures = db.query(Fixture).filter(Fixture.tournament_id == tourney.id).all()
    update_odds_from_api(fixtures, db)
    db.commit()
    for fixture in fixtures:
        score(fixture, db)
    recalculate_standings(db, tourney.id)
    db.commit()

    print("Database seeding and simulation completed.")
    return SeedResult(
        status="success",
        message="FIFA World Cup seeded successfully.",
        competition="FIFA World Cup",
        created=upsert.created,
        updated=upsert.updated,
        details={"fixtures": len(fixtures)},
    )


def _overlay_ucl_from_football_data(db: Session, tourney, comp):
    """Stamp official UCL pairings from Football-Data.org onto the draw-seeded tournament."""
    from backend.services.ingestion.engine import IngestionEngine

    api_season = 2026
    try:
        api_season = int(tourney.season_name.split("/")[0])
    except (ValueError, AttributeError):
        pass

    engine = IngestionEngine()
    return engine.overlay_from_football_data(
        db,
        tournament=tourney,
        competition=comp,
        api_season=api_season,
    )


def _seed_european_cups(db: Session, target_league_id: Optional[int] = None) -> SeedResult:
    if not _EURO_DRAW_JSON.exists():
        print(f"Error: {_EURO_DRAW_JSON} not found.")
        return SeedResult(status="error", message=f"{_EURO_DRAW_JSON} not found")

    with open(_EURO_DRAW_JSON, encoding="utf-8") as handle:
        data = json.load(handle)

    results = {}
    normalizer = NameNormalizer()
    resolver = TeamResolver(normalizer)
    upserter = FixtureUpserter(team_resolver=resolver)
    created_total = 0
    updated_total = 0

    for comp_name, comp_data in data.items():
        api_league_id = comp_data.get("api_league_id")
        if target_league_id is not None and api_league_id != target_league_id:
            continue
        try:
            format_engine = comp_data.get("format_engine", "league_phase_knockout")
            season = comp_data.get("season", "2026/27")
            home_adv = comp_data.get("home_advantage_elo", 80)
            comp = _get_or_create_competition(
                db,
                comp_name,
                type=comp_data.get("competition_type", "Cup"),
                format_engine=format_engine,
                home_advantage_elo=home_adv,
                api_league_id=api_league_id,
            )
            tourney = _get_or_create_tournament(
                db, comp, season, deactivate_other_seasons=True
            )

            team_map: dict[str, Team] = {}
            for t_info in comp_data.get("teams", []):
                t_name = normalizer.normalize(t_info["name"])
                country = t_info.get("country")
                elo = t_info.get("elo", 1700)
                db_team = resolver.resolve(
                    db,
                    provider_name="european_draw",
                    raw_name=t_name,
                    team_type="Club",
                    default_elo=elo,
                    country_code=country,
                )
                if not db_team:
                    continue
                if country and not db_team.country_code:
                    db_team.country_code = country
                if elo and (not db_team.elo or db_team.elo == 1500):
                    db_team.elo = elo
                    db_team.form_score = elo_to_form(elo)
                db.flush()
                team_map[t_name] = db_team
                _link_tournament_team(db, tourney.id, db_team.id)
            db.flush()

            payloads = []
            for f_info in comp_data.get("fixtures", []):
                h_name = normalizer.normalize(f_info["home"])
                a_name = normalizer.normalize(f_info["away"])
                h_team = team_map.get(h_name)
                a_team = team_map.get(a_name)
                if not h_team or not a_team:
                    continue
                date_utc = datetime.fromisoformat(f_info["date_utc"].replace("Z", "+00:00"))
                payloads.append({
                    "home_team": h_team,
                    "away_team": a_team,
                    "date_utc": date_utc,
                    "stage": f_info.get("stage", "League Phase"),
                    "matchday_number": f_info.get("matchday"),
                    "leg_number": f_info.get("leg_number", 1),
                    "status": "Scheduled",
                    "provider_name": "european_draw",
                })

            upsert = upserter.upsert_fixtures(db, tourney, payloads, competition=comp)
            created_total += upsert.created
            updated_total += upsert.updated

            if api_league_id == 2:
                overlay = _overlay_ucl_from_football_data(db, tourney, comp)
                created_total += overlay.created
                updated_total += overlay.updated

            fixtures = db.query(Fixture).filter(Fixture.tournament_id == tourney.id).all()
            for fixture in fixtures:
                score(fixture, db)
            recalculate_standings(db, tourney.id)
            db.commit()

            results[comp_name] = (
                f"Successfully seeded {len(comp_data.get('teams', []))} teams "
                f"and {len(payloads)} fixtures"
            )
            print(f"[{comp_name}] {results[comp_name]}")
        except IngestionAborted:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            results[comp_name] = f"Error: {exc}"
            print(f"Error seeding {comp_name}: {exc}")

    return SeedResult(
        status="success",
        created=created_total,
        updated=updated_total,
        details=results,
    )


def _live_seedable_competitions() -> set[str]:
    from backend.services.providers.football_data import COMPETITION_CODE_MAP
    from backend.services.providers.openfootball import OPENFOOTBALL_DATASETS
    from backend.services.providers.thesportsdb import LEAGUE_ID_MAP

    names = set(COMPETITION_CODE_MAP) | set(OPENFOOTBALL_DATASETS) | set(LEAGUE_ID_MAP)
    names.discard("FIFA World Cup")
    names.discard("European Championship")
    return names


def _seed_all(db: Session) -> SeedResult:
    results = {}
    print("--- Starting Full Multi-Competition Database Seeding ---")
    try:
        seed_database(db)
        results["FIFA World Cup"] = "Seeded successfully"
    except Exception as exc:
        results["FIFA World Cup"] = f"Error: {exc}"

    covered = _live_seedable_competitions()
    for name, comp_type, format_eng, league_id, season_str, api_season, releg_spots, home_adv in DEFAULT_LEAGUES_TO_SEED:
        if name not in covered:
            continue
        try:
            comp = db.query(Competition).filter(Competition.name == name).first()
            tourney = None
            if comp:
                tourney = db.query(Tournament).filter(
                    Tournament.competition_id == comp.id,
                    Tournament.season_name == season_str,
                ).first()
                if tourney:
                    f_count = db.query(Fixture).filter(Fixture.tournament_id == tourney.id).count()
                    if f_count > 0:
                        print(f"Skipping {name} ({season_str}): already seeded with {f_count} fixtures.")
                        results[name] = f"Already seeded ({f_count} fixtures)"
                        continue

            print(f"Seeding competition: {name}...")
            teams_exist = bool(
                tourney
                and db.query(TournamentTeam).filter(
                    TournamentTeam.tournament_id == tourney.id
                ).first()
            )
            team_result = None
            if teams_exist:
                print(f"Skipping team fetch for {name}: tournament teams already exist.")
            else:
                team_result = fetch_and_seed_teams(
                    db,
                    api_league_id=league_id,
                    api_season=api_season,
                    fetch_squads=False,
                )
            fixture_result = seed_competition(
                db=db,
                competition_name=name,
                competition_type=comp_type,
                format_engine=format_eng,
                season=season_str,
                api_league_id=league_id,
                api_season=api_season,
                relegation_spots=releg_spots,
                home_advantage_elo=home_adv,
            )
            skipped = [
                result.message
                for result in (team_result, fixture_result)
                if getattr(result, "status", None) == "skipped"
            ]
            if skipped:
                results[name] = f"Skipped: {'; '.join(skipped)}"
            else:
                results[name] = "Seeded successfully"
        except Exception as exc:
            print(f"Error seeding {name}: {exc}")
            results[name] = f"Error: {exc}"

    print("--- Full Database Seeding Completed ---")
    return SeedResult(status="success", details=results)


def _seed_named_competition(db: Session, config: dict) -> SeedResult:
    upsert = seed_competition(
        db=db,
        competition_name=config["competition_name"],
        competition_type=config.get("competition_type", "League"),
        format_engine=config.get("format_engine", "league"),
        season=config.get("season", "2026/27"),
        api_league_id=config.get("api_league_id"),
        api_season=config.get("api_season", 2026),
        relegation_spots=config.get("relegation_spots", 0),
        promotion_spots=config.get("promotion_spots", 0),
        relegation_playoff_spots=config.get("relegation_playoff_spots", 0),
        odds_api_sport_key=config.get("odds_api_sport_key"),
        home_advantage_elo=config.get("home_advantage_elo", 100),
        neutral_venue=config.get("neutral_venue", False),
    )
    return SeedResult(
        status="success",
        competition=config.get("competition_name"),
        league_id=config.get("api_league_id") or config.get("league_id"),
        created=getattr(upsert, "created", 0),
        updated=getattr(upsert, "updated", 0),
        odds_added=getattr(upsert, "odds_added", 0),
    )


def _seed_single(db: Session, league_id: int, fetch_squads: bool = False) -> SeedResult:
    if league_id in EURO_CUP_LEAGUE_IDS and _EURO_DRAW_JSON.exists():
        euro_res = seed_european_cups(db, target_league_id=league_id)
        try:
            fetch_and_seed_teams(db, api_league_id=league_id, api_season=2026, fetch_squads=fetch_squads)
        except Exception as exc:
            print(f"Warning: Failed to fetch Football-Data.org teams for euro cup {league_id}: {exc}")
        return SeedResult(
            status="success",
            message=f"European cup (league_id={league_id}) seeded successfully.",
            league_id=league_id,
            details=euro_res if isinstance(euro_res, dict) else {},
        )

    if league_id in DEFAULT_LEAGUES_BY_ID:
        name, comp_type, format_eng, _lid, season_str, api_season, releg_spots, home_adv = DEFAULT_LEAGUES_BY_ID[league_id]
        fetch_and_seed_teams(db, api_league_id=league_id, api_season=api_season, fetch_squads=fetch_squads)
        upsert_res = seed_competition(
            db=db,
            competition_name=name,
            competition_type=comp_type,
            format_engine=format_eng,
            season=season_str,
            api_league_id=league_id,
            api_season=api_season,
            relegation_spots=releg_spots,
            home_advantage_elo=home_adv,
        )
        return SeedResult(
            status="success",
            message=f"Competition '{name}' (league_id={league_id}) seeded successfully.",
            competition=name,
            league_id=league_id,
            created=getattr(upsert_res, "created", 0),
            updated=getattr(upsert_res, "updated", 0),
            odds_added=getattr(upsert_res, "odds_added", 0),
        )

    comp = db.query(Competition).filter(
        (Competition.api_league_id == league_id) | (Competition.id == league_id)
    ).first()
    if not comp:
        return SeedResult(
            status="error",
            message=f"Competition with league_id {league_id} not found in default configurations or database.",
            league_id=league_id,
        )

    tourney = db.query(Tournament).filter(
        Tournament.competition_id == comp.id,
        Tournament.status == "Active",
    ).first()
    season_str = tourney.season_name if tourney else "2026/27"
    api_season = 2026
    try:
        api_season = int(season_str.split("/")[0])
    except (ValueError, AttributeError):
        pass

    eff_api_league_id = comp.api_league_id or league_id
    if eff_api_league_id:
        fetch_and_seed_teams(db, api_league_id=eff_api_league_id, api_season=api_season, fetch_squads=fetch_squads)

    upsert_res = seed_competition(
        db=db,
        competition_name=comp.name,
        competition_type=comp.type or "League",
        format_engine=comp.format_engine or "league",
        season=season_str,
        api_league_id=eff_api_league_id,
        api_season=api_season,
        home_advantage_elo=comp.home_advantage_elo or 100,
        odds_api_sport_key=comp.odds_api_sport_key,
    )
    return SeedResult(
        status="success",
        message=f"Competition '{comp.name}' (league_id={league_id}) seeded successfully.",
        competition=comp.name,
        league_id=league_id,
        created=getattr(upsert_res, "created", 0),
        updated=getattr(upsert_res, "updated", 0),
        odds_added=getattr(upsert_res, "odds_added", 0),
    )


def seed_database(db: Session) -> SeedResult:
    """Seeds the FIFA World Cup 2026. Compatibility wrapper around ``seed()``."""
    return seed(db, {"kind": "world_cup"})


def seed_all_default_competitions(db: Session) -> dict:
    """Seeds World Cup plus Football-Data.org / openfootball-covered competitions."""
    return seed(db, {"kind": "all"}).details


def seed_single_competition(db: Session, league_id: int, fetch_squads: bool = False) -> dict:
    """
    Seeds or updates a single competition idempotently by catalog league id or Competition id.
    """
    result = seed(db, {"kind": "single", "league_id": league_id, "fetch_squads": fetch_squads})
    if result.status == "error":
        raise ValueError(result.message)
    return result.to_dict()


def seed_european_cups(db: Session, target_league_id: int = None) -> dict:
    """
    Seeds UEFA European competitions from ``european_draw_2026.json``.
    If ``target_league_id`` is set (2, 3, or 848), only that competition is seeded.
    """
    result = seed(db, {"kind": "european_cups", "league_id": target_league_id})
    if result.status == "error" and not result.details:
        return {"status": "error", "message": result.message}
    return result.details


def fetch_and_seed_teams(
    db: Session,
    api_league_id: int,
    api_season: int,
    team_type: str = "Club",
    elo_source: str = "clubelo",
    fetch_squads: bool = False,
):
    """Fetch teams for a covered competition from Football-Data.org and store crests on logo_url."""
    from backend.services.providers.football_data import FootballDataProvider

    entry = DEFAULT_LEAGUES_BY_ID.get(api_league_id)
    competition_name = entry[0] if entry else None
    if not competition_name:
        comp = db.query(Competition).filter(Competition.api_league_id == api_league_id).first()
        competition_name = comp.name if comp else None
    if not competition_name:
        print(f"No mapped competition name for league {api_league_id}; skipping team seed.")
        return SeedResult(status="skipped", message="No mapped competition name")

    print(f"Fetching Football-Data.org teams for {competition_name}, season {api_season}...")
    provider = FootballDataProvider()
    teams_data = provider.fetch_teams(competition_name, api_season)
    if not teams_data:
        print(f"No Football-Data.org teams returned for {competition_name}.")
        status = "skipped" if provider.last_request_skipped else "success"
        message = "Football-Data.org team request was skipped" if provider.last_request_skipped else ""
        return SeedResult(status=status, message=message)

    if fetch_squads:
        print("Squad ingestion is not available without API-Football; seeding team crests only.")

    clubelo_ratings = fetch_clubelo_ratings() if team_type == "Club" else {}
    clubelo_names = list(clubelo_ratings)

    print(f"Seeding {len(teams_data)} teams...")
    for t_info in teams_data:
        raw_name = t_info.get("shortName") or t_info.get("name", "")
        clubelo_name, confidence = fuzzy_match_team(raw_name, clubelo_names)
        matched_elo = (
            clubelo_ratings.get(clubelo_name)
            if clubelo_name and confidence >= 0.85
            else None
        )
        db_team = provider.resolve_team(
            db,
            t_info,
            team_type=team_type,
            default_elo=matched_elo if matched_elo is not None else 1500,
            elo_source="manual",
        )
        if not db_team:
            continue
        db_team.team_type = team_type
        if matched_elo is not None:
            db_team.elo = matched_elo
            db_team.form_score = elo_to_form(matched_elo)
            db_team.elo_source = elo_source
        db.flush()

    db.commit()
    print(f"Successfully seeded teams for {competition_name} (league={api_league_id}).")
    return SeedResult(status="success")


def seed_competition(
    db: Session,
    competition_name: str,
    competition_type: str,
    format_engine: str,
    season: str,
    api_league_id: int,
    api_season: int,
    neutral_venue: bool = False,
    relegation_spots: int = 0,
    promotion_spots: int = 0,
    relegation_playoff_spots: int = 0,
    odds_api_sport_key: str = None,
    home_advantage_elo: int = 100,
):
    """Seed / upsert competition fixture data via the ingestion engine."""
    from backend.services.ingestion import seed_competition as ingestion_seed_competition

    return ingestion_seed_competition(
        db,
        competition_name=competition_name,
        competition_type=competition_type,
        format_engine=format_engine,
        season=season,
        api_league_id=api_league_id,
        api_season=api_season,
        home_advantage_elo=0 if neutral_venue else home_advantage_elo,
        odds_api_sport_key=odds_api_sport_key,
    )


DEFAULT_LEAGUES_TO_SEED = [
    ("Premier League", "League", "league", 39, "2026/27", 2026, 3, 100),
    ("La Liga", "League", "league", 140, "2026/27", 2026, 3, 120),
    ("Serie A", "League", "league", 135, "2026/27", 2026, 3, 100),
    ("Bundesliga", "League", "league", 78, "2026/27", 2026, 2, 100),
    ("Ligue 1", "League", "league", 61, "2026/27", 2026, 2, 90),
    ("UEFA Champions League", "Cup", "league_phase_knockout", 2, "2026/27", 2026, 0, 80),
    ("UEFA Europa League", "Cup", "league_phase_knockout", 3, "2026/27", 2026, 0, 60),
    ("UEFA Conference League", "Cup", "league_phase_knockout", 848, "2026/27", 2026, 0, 50),
    ("FA Cup", "Cup", "cup", 45, "2026/27", 2026, 0, 30),
    ("EFL Cup", "Cup", "cup", 48, "2026/27", 2026, 0, 30),
    ("Coppa Italia", "Cup", "cup", 137, "2026/27", 2026, 0, 30),
    ("DFB Pokal", "Cup", "cup", 81, "2026/27", 2026, 0, 30),
    ("Coupe de France", "Cup", "cup", 66, "2026/27", 2026, 0, 30),
    ("Eredivisie", "League", "league", 88, "2026/27", 2026, 3, 90),
    ("KNVB Beker", "Cup", "cup", 90, "2026/27", 2026, 0, 30),
    ("Primeira Liga", "League", "league", 94, "2026/27", 2026, 3, 90),
    ("Taça de Portugal", "Cup", "cup", 96, "2026/27", 2026, 0, 30),
    ("Scottish Premiership", "League", "league", 179, "2026/27", 2026, 2, 80),
    ("Belgian Pro League", "League", "league", 144, "2026/27", 2026, 3, 80),
    ("Süper Lig", "League", "league", 203, "2026/27", 2026, 4, 100),
    ("Major League Soccer", "League", "league", 253, "2026", 2026, 0, 80),
    ("US Open Cup", "Cup", "cup", 257, "2026", 2026, 0, 30),
    ("Brasileirão Série A", "League", "league", 71, "2026", 2026, 4, 110),
    ("Copa do Brasil", "Cup", "cup", 73, "2026", 2026, 0, 30),
    ("Liga Profesional Argentina", "League", "league", 128, "2026", 2026, 2, 110),
    ("Copa Argentina", "Cup", "cup", 130, "2026", 2026, 0, 30),
    ("Copa Libertadores", "Cup", "group_knockout", 13, "2026", 2026, 0, 80),
    ("Copa Sudamericana", "Cup", "group_knockout", 11, "2026", 2026, 0, 60),
    ("CONCACAF Champions Cup", "Cup", "cup", 16, "2026", 2026, 0, 40),
]

DEFAULT_LEAGUES_BY_ID = {item[3]: item for item in DEFAULT_LEAGUES_TO_SEED}
EURO_CUP_LEAGUE_IDS = (2, 3, 848)


def retire_european_draw_placeholders(db: Session, tournament_id: int) -> int:
    """Remove scheduled draw-seeded fixtures that were never mapped to a live API id."""
    stale = (
        db.query(Fixture)
        .filter(
            Fixture.tournament_id == tournament_id,
            Fixture.api_id.is_(None),
            Fixture.status == "Scheduled",
        )
        .all()
    )
    count = len(stale)
    for fixture in stale:
        db.delete(fixture)
    if count:
        db.flush()
    return count


