import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.database import Team, TournamentTeam, Competition, Tournament, Fixture
import backend.services.seeder as seeder_module
from backend.services.seeder import (
    SeedResult,
    _live_seedable_competitions,
    _normalize_wc_stage,
    fetch_and_seed_teams,
    get_fallback_matches,
    seed,
    seed_database,
)

WC_JSON = Path("backend/data/world_cup_2026.json")


def test_world_cup_json_contains_static_dictionaries():
    assert WC_JSON.exists()
    data = json.loads(WC_JSON.read_text(encoding="utf-8"))
    assert set(data["groups"]) == set("ABCDEFGHIJKL")
    assert len(data["groups"]["A"]) == 4
    assert "Spain" in data["elo_ratings"]
    assert "Germany" in data["spotlight_players"]
    assert data["spotlight_players"]["Germany"][0]["name"] == "Florian Wirtz"
    assert len(data["fallback_matches"]) == 9


def test_get_fallback_matches_reads_json():
    matches = get_fallback_matches()
    assert matches[0]["home"] == "Mexico"
    assert matches[0]["away"] == "South Africa"
    assert matches[-1]["home"] == "England"


def test_normalize_wc_stage_handles_api_football_variants():
    assert _normalize_wc_stage("Quarter-finals") == "Quarter-final"
    assert _normalize_wc_stage("SEMI-FINALS") == "Semi-final"
    assert _normalize_wc_stage("group stage - 1") == "Group Stage"


def test_seed_unknown_kind_returns_error(db_session):
    result = seed(db_session, {"kind": "not-a-target"})
    assert isinstance(result, SeedResult)
    assert result.status == "error"
    assert "Unknown seed kind" in result.message


def test_seed_world_cup_via_canonical_api(db_session, monkeypatch):
    static_elo = json.loads(WC_JSON.read_text(encoding="utf-8"))["elo_ratings"]
    monkeypatch.setattr("backend.services.seeder.fetch_current_elo_ratings", lambda: dict(static_elo))
    result = seed(db_session, {"kind": "world_cup"})
    assert result.status == "success"
    assert result.competition == "FIFA World Cup"
    assert result.created >= 9

    comp = db_session.query(Competition).filter_by(name="FIFA World Cup").first()
    assert comp is not None
    tourney = db_session.query(Tournament).filter_by(competition_id=comp.id, season_name="2026").first()
    assert tourney is not None

    mexico = db_session.query(Team).filter_by(name="Mexico").first()
    assert mexico is not None
    tt = db_session.query(TournamentTeam).filter_by(tournament_id=tourney.id, team_id=mexico.id).first()
    assert tt is not None
    assert tt.group_name == "A"

    fixtures = db_session.query(Fixture).filter_by(tournament_id=tourney.id).all()
    assert len(fixtures) >= 9
    assert all(f.odds_history for f in fixtures)


def test_seed_database_wrapper_delegates_to_seed(db_session, monkeypatch):
    static_elo = json.loads(WC_JSON.read_text(encoding="utf-8"))["elo_ratings"]
    monkeypatch.setattr("backend.services.seeder.fetch_current_elo_ratings", lambda: dict(static_elo))
    result = seed_database(db_session)
    assert isinstance(result, SeedResult)
    assert result.status == "success"
    assert db_session.query(Team).count() >= 48


@patch("backend.services.providers.api_football.call_football_api")
def test_seed_world_cup_does_not_call_api_football(mock_api_football, db_session, monkeypatch):
    """World Cup seed uses the static dataset even when an API-Football key is present."""
    static_elo = json.loads(WC_JSON.read_text(encoding="utf-8"))["elo_ratings"]
    monkeypatch.setattr("backend.services.seeder.fetch_current_elo_ratings", lambda: dict(static_elo))
    monkeypatch.setenv("FOOTBALL_API_KEY", "suspended-key")
    mock_api_football.return_value = {
        "response": [
            {
                "fixture": {"id": 999001, "date": "2026-06-11T16:00:00Z", "status": {"short": "NS"}},
                "teams": {"home": {"id": 1, "name": "Mexico"}, "away": {"id": 2, "name": "South Africa"}},
                "goals": {"home": None, "away": None},
                "league": {"round": "Group Stage"},
            }
        ]
    }

    result = seed(db_session, {"kind": "world_cup"})

    assert result.status == "success"
    mock_api_football.assert_not_called()
    comp = db_session.query(Competition).filter_by(name="FIFA World Cup").one()
    tourney = db_session.query(Tournament).filter_by(competition_id=comp.id).one()
    api_ids = {f.api_id for f in db_session.query(Fixture).filter_by(tournament_id=tourney.id).all()}
    assert "1" in api_ids
    assert "999001" not in api_ids


def test_seed_world_cup_overlays_sparse_live_elo(db_session, monkeypatch):
    static_elo = json.loads(WC_JSON.read_text(encoding="utf-8"))["elo_ratings"]
    monkeypatch.setattr(
        "backend.services.seeder.fetch_current_elo_ratings",
        lambda: {"Mexico": 1999},
    )

    result = seed(db_session, {"kind": "world_cup"})

    assert result.status == "success"
    assert db_session.query(Team).filter_by(name="Mexico").one().elo == 1999
    assert db_session.query(Team).filter_by(name="Spain").one().elo == static_elo["Spain"]


def test_live_seedable_competitions_includes_thesportsdb_only_leagues():
    assert "UEFA Conference League" in _live_seedable_competitions()


def test_fetch_and_seed_teams_applies_matched_clubelo(db_session, monkeypatch):
    monkeypatch.setattr(
        "backend.services.providers.football_data.FootballDataProvider.fetch_teams",
        lambda self, competition_name, season: [
            {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal"}
        ],
    )
    monkeypatch.setattr(
        "backend.services.seeder.fetch_clubelo_ratings",
        lambda: {"Arsenal": 1888},
    )

    result = fetch_and_seed_teams(db_session, api_league_id=39, api_season=2026)

    arsenal = db_session.query(Team).filter_by(name="Arsenal").one()
    assert result.status == "success"
    assert arsenal.elo == 1888
    assert arsenal.form_score == 69.4
    assert arsenal.elo_source == "clubelo"


def test_fetch_and_seed_teams_does_not_claim_clubelo_for_unmatched_team(
    db_session, monkeypatch
):
    monkeypatch.setattr(
        "backend.services.providers.football_data.FootballDataProvider.fetch_teams",
        lambda self, competition_name, season: [
            {"id": 999, "name": "Unmatched Town", "shortName": "Unmatched Town"}
        ],
    )
    monkeypatch.setattr(
        "backend.services.seeder.fetch_clubelo_ratings",
        lambda: {"Arsenal": 1888},
    )

    fetch_and_seed_teams(db_session, api_league_id=39, api_season=2026)

    team = db_session.query(Team).filter_by(name="Unmatched Town").one()
    assert team.elo == 1500
    assert team.elo_source == "manual"


def test_seed_all_records_skipped_fixture_request(db_session, monkeypatch):
    monkeypatch.setattr(
        seeder_module,
        "DEFAULT_LEAGUES_TO_SEED",
        [("Premier League", "League", "league", 39, "2026/27", 2026, 3, 100)],
    )
    monkeypatch.setattr(seeder_module, "seed_database", lambda db: SeedResult())
    monkeypatch.setattr(
        seeder_module,
        "fetch_and_seed_teams",
        lambda *args, **kwargs: SeedResult(status="success"),
    )
    skipped = MagicMock(status="skipped", message="fixture request skipped")
    monkeypatch.setattr(seeder_module, "seed_competition", lambda *args, **kwargs: skipped)

    result = seeder_module._seed_all(db_session)

    assert result.details["Premier League"] == "Skipped: fixture request skipped"


def test_seed_all_records_skipped_team_request(db_session, monkeypatch):
    monkeypatch.setattr(
        seeder_module,
        "DEFAULT_LEAGUES_TO_SEED",
        [("Premier League", "League", "league", 39, "2026/27", 2026, 3, 100)],
    )
    monkeypatch.setattr(seeder_module, "seed_database", lambda db: SeedResult())
    monkeypatch.setattr(
        seeder_module,
        "fetch_and_seed_teams",
        lambda *args, **kwargs: SeedResult(
            status="skipped", message="team request skipped"
        ),
    )
    monkeypatch.setattr(
        seeder_module,
        "seed_competition",
        lambda *args, **kwargs: MagicMock(status="success", message=""),
    )

    result = seeder_module._seed_all(db_session)

    assert result.details["Premier League"] == "Skipped: team request skipped"


def test_seed_all_skips_team_fetch_when_tournament_teams_exist(db_session, monkeypatch):
    comp = Competition(name="Premier League", type="League")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    team = Team(name="Arsenal")
    db_session.add_all([tourney, team])
    db_session.flush()
    db_session.add(TournamentTeam(tournament_id=tourney.id, team_id=team.id))
    db_session.commit()

    monkeypatch.setattr(
        seeder_module,
        "DEFAULT_LEAGUES_TO_SEED",
        [("Premier League", "League", "league", 39, "2026/27", 2026, 3, 100)],
    )
    monkeypatch.setattr(seeder_module, "seed_database", lambda db: SeedResult())
    fetch_teams = MagicMock()
    monkeypatch.setattr(seeder_module, "fetch_and_seed_teams", fetch_teams)
    monkeypatch.setattr(
        seeder_module,
        "seed_competition",
        lambda *args, **kwargs: MagicMock(status="success", message=""),
    )

    result = seeder_module._seed_all(db_session)

    fetch_teams.assert_not_called()
    assert result.details["Premier League"] == "Seeded successfully"
