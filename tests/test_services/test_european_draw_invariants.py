from pathlib import Path

import pytest

from backend.database import Competition, Fixture, Tournament
from backend.services.seeder import seed_single_competition


@pytest.fixture(autouse=True)
def _isolate_feed_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "backend.services.feed_builder.CACHE_FILE_PATH",
        str(tmp_path / "fixtures_feed_cache.json"),
    )


def test_european_draw_json_is_gone():
    data_dir = Path("backend/data")
    draw_file = data_dir / "european_draw_2026.json"
    assert not draw_file.exists(), "european_draw_2026.json must not be reintroduced"
    invented = [
        path
        for path in data_dir.glob("*.json")
        if "draw" in path.name.lower() or "european" in path.name.lower()
    ]
    assert invented == [], f"invented European-cup JSON must not exist: {invented}"
    assert (data_dir / "world_cup_2026.json").exists()


def test_empty_providers_leave_european_cups_with_empty_schedules(db_session, monkeypatch):
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

    for league_id, name in (
        (2, "UEFA Champions League"),
        (3, "UEFA Europa League"),
        (848, "UEFA Conference League"),
    ):
        result = seed_single_competition(db_session, league_id=league_id)
        assert result["status"] == "success"
        comp = db_session.query(Competition).filter(Competition.name == name).one()
        tourney = db_session.query(Tournament).filter(
            Tournament.competition_id == comp.id,
            Tournament.season_name == "2026/27",
        ).one()
        assert db_session.query(Fixture).filter(Fixture.tournament_id == tourney.id).count() == 0
