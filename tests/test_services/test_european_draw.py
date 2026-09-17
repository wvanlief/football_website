import pytest

from backend.database import Competition, Fixture, Tournament, TournamentTeam
from backend.services.seeder import seed


@pytest.fixture(autouse=True)
def _isolate_feed_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "backend.services.feed_builder.CACHE_FILE_PATH",
        str(tmp_path / "fixtures_feed_cache.json"),
    )


def test_european_cups_kind_uses_ingestion_engine_not_draw(db_session, monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_ORG_KEY", raising=False)
    monkeypatch.delenv("FOOTBALL_DATA_API_KEY", raising=False)
    monkeypatch.delenv("FOOTBALL_DATA_KEY", raising=False)
    monkeypatch.setattr(
        "backend.services.providers.thesportsdb.fetch_json_with_retry",
        lambda url, *args, **kwargs: {"countries": [], "leagues": [], "events": None},
    )
    monkeypatch.setattr(
        "backend.services.seeder.fetch_and_seed_teams",
        lambda *args, **kwargs: None,
    )

    result = seed(db_session, {"kind": "european_cups"})
    assert result.status == "success"
    assert "UEFA Champions League" in result.details
    assert "UEFA Europa League" in result.details
    assert "UEFA Conference League" in result.details

    ucl = db_session.query(Competition).filter(Competition.name == "UEFA Champions League").one()
    assert ucl.format_engine == "league_phase_knockout"
    assert ucl.type == "Cup"
    assert ucl.api_league_id == 2

    tourney = db_session.query(Tournament).filter(
        Tournament.competition_id == ucl.id,
        Tournament.season_name == "2026/27",
    ).one()
    assert tourney.status == "Active"
    assert db_session.query(TournamentTeam).filter(
        TournamentTeam.tournament_id == tourney.id
    ).count() == 0
    assert db_session.query(Fixture).filter(Fixture.tournament_id == tourney.id).count() == 0
    assert db_session.query(Fixture).filter(Fixture.stage == "Play-offs").count() == 0
