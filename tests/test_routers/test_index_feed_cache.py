import asyncio
import json

from backend.main import app, lifespan


def test_index_serves_zero_fixture_cache_without_rebuilding(client, monkeypatch, tmp_path):
    """A cache file with zero fixtures is a finished answer, not a reason to rebuild."""
    cache_path = tmp_path / "fixtures_feed_cache.json"
    payload = {"updated_at": "empty", "total_fixtures": 0, "fixtures": []}
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("backend.services.feed_builder.CACHE_FILE_PATH", str(cache_path))

    def forbid_rebuild(*_args, **_kwargs):
        raise AssertionError("index rebuilt a cache that already existed")

    monkeypatch.setattr("backend.routers.pages.build_fixtures_feed_cache", forbid_rebuild)

    first = client.get("/")
    second = client.get("/")

    assert first.status_code == 200
    assert second.status_code == 200
    assert '"total_fixtures": 0' in first.text
    assert json.loads(cache_path.read_text(encoding="utf-8")) == payload


def test_index_rebuilds_once_when_the_cache_file_is_missing(client, monkeypatch, tmp_path):
    cache_path = tmp_path / "fixtures_feed_cache.json"
    monkeypatch.setattr("backend.services.feed_builder.CACHE_FILE_PATH", str(cache_path))
    payload = {"updated_at": "built", "total_fixtures": 0, "fixtures": []}
    calls = []

    def build(_db):
        calls.append(1)
        cache_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr("backend.routers.pages.build_fixtures_feed_cache", build)

    first = client.get("/")
    second = client.get("/")

    assert first.status_code == 200
    assert '"updated_at": "built"' in first.text
    assert second.status_code == 200
    assert calls == [1]


def test_lifespan_skips_feed_warm_while_testing(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "backend.main.build_fixtures_feed_cache",
        lambda db: calls.append(db),
    )

    async def _enter():
        async with lifespan(app):
            return None

    asyncio.run(_enter())
    assert calls == []


def test_lifespan_warms_a_missing_cache_outside_tests(monkeypatch):
    monkeypatch.setenv("TESTING", "False")
    calls = []

    class _Session:
        def close(self):
            calls.append("closed")

    monkeypatch.setattr("backend.main.SessionLocal", lambda: _Session())
    monkeypatch.setattr("backend.main.load_precalculated_feed_cache", lambda: None)
    monkeypatch.setattr(
        "backend.main.build_fixtures_feed_cache",
        lambda db: calls.append("built"),
    )

    async def _enter():
        async with lifespan(app):
            return None

    asyncio.run(_enter())
    assert calls == ["built", "closed"]


def test_lifespan_keeps_a_zero_fixture_cache(monkeypatch):
    monkeypatch.setenv("TESTING", "False")
    calls = []

    class _Session:
        def close(self):
            calls.append("closed")

    monkeypatch.setattr("backend.main.SessionLocal", lambda: _Session())
    monkeypatch.setattr(
        "backend.main.load_precalculated_feed_cache",
        lambda: {"total_fixtures": 0, "fixtures": []},
    )
    monkeypatch.setattr(
        "backend.main.build_fixtures_feed_cache",
        lambda db: calls.append("built"),
    )

    async def _enter():
        async with lifespan(app):
            return None

    asyncio.run(_enter())
    assert calls == ["closed"]


def test_lifespan_still_starts_when_feed_warm_fails(monkeypatch):
    monkeypatch.setenv("TESTING", "False")
    closed = []

    class _Session:
        def close(self):
            closed.append(True)

    monkeypatch.setattr("backend.main.SessionLocal", lambda: _Session())
    monkeypatch.setattr("backend.main.load_precalculated_feed_cache", lambda: None)

    def explode(_db):
        raise RuntimeError("enrichment failed")

    monkeypatch.setattr("backend.main.build_fixtures_feed_cache", explode)

    async def _enter():
        async with lifespan(app):
            return "serving"

    assert asyncio.run(_enter()) == "serving"
    assert closed == [True]
