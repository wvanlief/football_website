import json
from pathlib import Path

from backend.database import Team, TournamentTeam, Competition, Tournament, Fixture
from backend.services.seeder import (
    SeedResult,
    _normalize_wc_stage,
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
