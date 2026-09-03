"""Thin seeding orchestrator.

Static World Cup data lives in ``backend/data/world_cup_2026.json``. Persistence
goes through ``TeamResolver`` and ``FixtureUpserter``; competition fixture
ingestion delegates to ``IngestionEngine``.
"""
from __future__ import annotations

import json
import os
import time
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
from backend.scoring import update_fixture_score
from backend.services.ingestion import (
    NameNormalizer,
    COUNTRY_ISO_MAP,
    TeamResolver,
    FixtureUpserter,
)
from backend.services.odds import update_odds_from_api
from backend.services.elo import fetch_current_elo_ratings, record_elo_history, elo_to_form
from backend.services.providers.api_football import call_football_api, parse_match_status
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
    """World Cup 2026 group-stage fixtures used when the live API is unavailable."""
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
    stage = _WC_STAGE_MAPPING.get(raw_stage, raw_stage) or "Group Stage"
    if "Group" in str(stage):
        return "Group Stage"
    return stage


def _parse_iso_datetime(value: Optional[str], fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception as date_err:
        print(f"Error parsing date {value}: {date_err}")
        return fallback


def _fetch_world_cup_api_fixtures(normalizer: NameNormalizer) -> list[dict]:
    api_key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
    if not api_key:
        return []
    wc = _load_world_cup_data()
    try:
        print("Fetching official schedule from API-Football...")
        res = call_football_api("fixtures", {
            "league": wc.get("api_league_id", 1),
            "season": wc.get("api_season", 2026),
        })
    except Exception as exc:
        print(f"Failed to fetch matches from API-Football: {exc}. Seeding fallback schedule.")
        return []

    if not isinstance(res, dict) or "response" not in res:
        return []

    payloads = []
    default_kickoff = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
    for raw in res["response"]:
        fixture_info = raw.get("fixture", {})
        teams_info = raw.get("teams", {})
        goals_info = raw.get("goals", {})
        league_info = raw.get("league", {})
        status = parse_match_status(fixture_info.get("status", {}).get("short", ""))
        dt_utc = _parse_iso_datetime(fixture_info.get("date"), default_kickoff)
        home_score = goals_info.get("home")
        away_score = goals_info.get("away")
        payloads.append({
            "api_id": str(fixture_info.get("id")),
            "home_team_name": normalizer.normalize(teams_info.get("home", {}).get("name", "")),
            "away_team_name": normalizer.normalize(teams_info.get("away", {}).get("name", "")),
            "home_team_api_id": teams_info.get("home", {}).get("id"),
            "away_team_api_id": teams_info.get("away", {}).get("id"),
            "date_utc": dt_utc,
            "stage": _normalize_wc_stage(league_info.get("round", "Group Stage")),
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
            "provider_name": "api_football",
        })
    print(f"Successfully fetched {len(payloads)} matches from API-Football.")
    return payloads


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

    try:
        print("Fetching live Elo ratings from eloratings.net...")
        live_elo = fetch_current_elo_ratings()
        print(f"Successfully fetched {len(live_elo)} Elo ratings from eloratings.net.")
    except Exception as exc:
        print(f"Failed to fetch live Elo ratings: {exc}. Falling back to JSON ratings.")
        live_elo = dict(wc["elo_ratings"])

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

    payloads = _fetch_world_cup_api_fixtures(normalizer) or _fallback_fixture_payloads()
    upsert = upserter.upsert_fixtures(db, tourney, payloads, competition=comp)
    db.commit()

    fixtures = db.query(Fixture).filter(Fixture.tournament_id == tourney.id).all()
    update_odds_from_api(fixtures, db)
    db.commit()
    for fixture in fixtures:
        update_fixture_score(fixture, db)
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

            fixtures = db.query(Fixture).filter(Fixture.tournament_id == tourney.id).all()
            for fixture in fixtures:
                update_fixture_score(fixture, db)
            recalculate_standings(db, tourney.id)
            db.commit()

            results[comp_name] = (
                f"Successfully seeded {len(comp_data.get('teams', []))} teams "
                f"and {len(payloads)} fixtures"
            )
            print(f"[{comp_name}] {results[comp_name]}")
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


def _seed_all(db: Session) -> SeedResult:
    results = {}
    print("--- Starting Full Multi-Competition Database Seeding ---")
    try:
        seed_database(db)
        results["FIFA World Cup"] = "Seeded successfully"
    except Exception as exc:
        results["FIFA World Cup"] = f"Error: {exc}"

    api_key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
    if api_key:
        for name, comp_type, format_eng, league_id, season_str, api_season, releg_spots, home_adv in DEFAULT_LEAGUES_TO_SEED:
            try:
                comp = db.query(Competition).filter(Competition.name == name).first()
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
                fetch_and_seed_teams(db, api_league_id=league_id, api_season=api_season, fetch_squads=False)
                seed_competition(
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
                results[name] = "Seeded successfully"
            except Exception as exc:
                print(f"Error seeding {name}: {exc}")
                results[name] = f"Error: {exc}"
    else:
        print("FOOTBALL_API_KEY not found. Skipping API-Football league seeding.")
        results["Leagues"] = "Skipped (No FOOTBALL_API_KEY)"

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
    if league_id in (2, 3, 848) and _EURO_DRAW_JSON.exists():
        euro_res = seed_european_cups(db, target_league_id=league_id)
        api_key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
        if api_key:
            try:
                fetch_and_seed_teams(db, api_league_id=league_id, api_season=2026, fetch_squads=fetch_squads)
            except Exception as exc:
                print(f"Warning: Failed to fetch API teams for euro cup {league_id}: {exc}")
        return SeedResult(
            status="success",
            message=f"European cup (league_id={league_id}) seeded successfully.",
            league_id=league_id,
            details=euro_res if isinstance(euro_res, dict) else {},
        )

    if league_id in DEFAULT_LEAGUES_BY_ID:
        name, comp_type, format_eng, _lid, season_str, api_season, releg_spots, home_adv = DEFAULT_LEAGUES_BY_ID[league_id]
        api_key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
        if api_key:
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
    api_key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
    if api_key and eff_api_league_id:
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
    """Seeds World Cup plus the default API-Football competitions."""
    return seed(db, {"kind": "all"}).details


def seed_single_competition(db: Session, league_id: int, fetch_squads: bool = False) -> dict:
    """
    Seeds or updates a single competition idempotently by API-Football league ID or Competition ID.
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
    """Fetches all teams for a league and optionally picks spotlight players for each team."""
    normalizer = NameNormalizer()
    resolver = TeamResolver(normalizer)
    print(f"Fetching teams for league {api_league_id}, season {api_season}...")
    try:
        res = call_football_api("teams", {"league": api_league_id, "season": api_season})
    except Exception as exc:
        print(f"Error calling football API for teams: {exc}")
        return

    if not isinstance(res, dict) or "response" not in res:
        print(f"Invalid API response: {res}")
        return
    if res.get("errors"):
        print(f"API-Football Error: {res['errors']}")
        return

    teams_data = res["response"]
    print(f"Seeding {len(teams_data)} teams...")

    for t_wrapper in teams_data:
        t_info = t_wrapper.get("team", {})
        api_team_id = t_info.get("id")
        name = normalizer.normalize(t_info.get("name", ""))
        country_name = t_info.get("country", "")
        country_code = t_info.get("code")
        if not country_code and country_name:
            country_code = normalizer.get_country_code(country_name)

        db_team = resolver.resolve(
            db,
            provider_name="api_football",
            raw_name=name,
            external_id=api_team_id,
            team_type=team_type,
            default_elo=1500,
            country_code=country_code,
            api_id=api_team_id,
        )
        if not db_team:
            continue
        db_team.api_id = api_team_id
        if country_code:
            db_team.country_code = country_code
        db_team.team_type = team_type
        db_team.elo_source = elo_source
        db.flush()

        if not fetch_squads:
            continue

        existing_contracts = db.query(PlayerContract).filter(PlayerContract.team_id == db_team.id).first()
        if existing_contracts:
            print(f"Squad already populated for {name}, skipping squad API call.")
            continue
        try:
            print(f"Fetching squad for {name}...")
            squad_res = call_football_api("players/squads", {"team": api_team_id})
            time.sleep(6.0)
            squad_data = squad_res.get("response", [])
            if not (squad_data and isinstance(squad_data, list)):
                continue
            players_list = squad_data[0].get("players", [])
            gks = [p for p in players_list if p.get("position") == "Goalkeeper"]
            mids = [p for p in players_list if p.get("position") == "Midfielder"]
            fwds = [p for p in players_list if p.get("position") in ("Attacker", "Forward")]
            spotlights = []
            for p_group in (gks, mids, fwds):
                if p_group:
                    p_group_sorted = sorted(p_group, key=lambda x: x.get("age") or 0, reverse=True)
                    spotlights.append(p_group_sorted[0])
            for player in spotlights:
                p_name = player.get("name")
                p_pos = player.get("position")
                if p_pos == "Attacker":
                    p_pos = "Forward"
                db_player = db.query(Player).filter(Player.name == p_name, Player.position == p_pos).first()
                if not db_player:
                    db_player = Player(name=p_name, position=p_pos, form_score=75.0)
                    db.add(db_player)
                    db.flush()
                contract = db.query(PlayerContract).filter(
                    PlayerContract.player_id == db_player.id,
                    PlayerContract.team_id == db_team.id,
                    PlayerContract.type == team_type,
                ).first()
                if not contract:
                    db.add(PlayerContract(
                        player_id=db_player.id,
                        team_id=db_team.id,
                        type=team_type,
                        is_active=True,
                    ))
        except Exception as squad_err:
            print(f"Warning: Failed to fetch squad for {name}: {squad_err}")

    db.commit()
    print(f"Successfully seeded teams and spotlights for league={api_league_id}.")


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
