from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend.database import Competition, Fixture, Team, Tournament
from backend.services.ingestion.engine import IngestionEngine
from backend.services.providers.football_api import FootballApiProvider
from backend.services.rate_limiter import APIRateLimiter
from backend.services.seeder import seed_single_competition

UEL_FIXTURE = {
    "fixture": {
        "id": 880011,
        "date": "2026-09-24T19:00:00+00:00",
        "status": {"short": "NS", "long": "Not Started"},
    },
    "league": {"id": 3, "season": 2026, "round": "League Stage - 1"},
    "teams": {
        "home": {"id": 497, "name": "Roma"},
        "away": {"id": 212, "name": "FC Porto"},
    },
    "goals": {"home": None, "away": None},
}

def test_football_api_normalizes_league_phase_with_fa_stamp(db_session, monkeypatch):
    calls = []

    def _fetch(url, headers=None, **kwargs):
        calls.append((url, headers, kwargs.get("provider")))
        return {"response": [UEL_FIXTURE]}

    monkeypatch.setattr(
        "backend.services.providers.football_api.fetch_json_with_retry",
        _fetch,
    )
    provider = FootballApiProvider(api_key="test-key")
    raw = provider.fetch_fixtures("UEFA Europa League", 2026, league_id=3)
    assert len(raw) == 1
    url, headers, provider_name = calls[0]
    assert url == "https://v3.football.api-sports.io/fixtures?league=3&season=2026"
    assert headers == {"x-apisports-key": "test-key"}
    assert provider_name == "football_api"
    assert "squads" not in url
    assert "media.api-sports.io" not in url

    comp = Competition(name="UEFA Europa League", type="Cup", api_league_id=3)
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.commit()

    payload = provider.normalize_fixture_payload(db_session, raw[0], tourney.id, "Cup")
    assert payload["api_id"] == "fa_880011"
    assert payload["stage"] == "League Phase"
    assert payload["matchday_number"] == 1
    assert payload["home_team"].name == "Roma"
    assert payload["away_team"].name == "FC Porto"
    assert "media.api-sports.io" not in str(payload)


def test_football_api_rate_limit_leaves_headroom():
    limits = APIRateLimiter.LIMITS["football_api"]
    assert limits == {"per_min": 10, "per_day": 90}
    assert "api_football" not in APIRateLimiter.LIMITS


UECL_FIXTURE = {
    "fixture": {
        "id": 880848,
        "date": "2026-10-01T19:00:00+00:00",
        "status": {"short": "NS", "long": "Not Started"},
    },
    "league": {"id": 848, "season": 2026, "round": "League Stage - 2"},
    "teams": {
        "home": {"id": 99, "name": "Fiorentina"},
        "away": {"id": 100, "name": "Real Betis"},
    },
    "goals": {"home": None, "away": None},
}


def _engine_with_football_api(provider, tsdb=None, highlightly=None):
    fd = MagicMock()
    fd.fetch_fixtures.return_value = []
    fd.last_request_skipped = False
    openfootball = MagicMock()
    openfootball.fetch_fixtures.return_value = []
    hl = highlightly or MagicMock()
    hl.fetch_fixtures.return_value = []
    tsdb_provider = tsdb or MagicMock()
    tsdb_provider.fetch_fixtures.return_value = []
    return IngestionEngine(
        fd_provider=fd,
        openfootball_provider=openfootball,
        football_api_provider=provider,
        highlightly_provider=hl,
        tsdb_provider=tsdb_provider,
    ), openfootball, hl, tsdb_provider


def test_engine_uses_football_api_for_uel_and_skips_later_providers(db_session, monkeypatch):
    calls = []

    def _fetch(url, headers=None, **kwargs):
        calls.append((url, headers, kwargs.get("provider")))
        return {"response": [UEL_FIXTURE]}

    monkeypatch.setattr(
        "backend.services.providers.football_api.fetch_json_with_retry",
        _fetch,
    )
    provider = FootballApiProvider(api_key="test-key")
    tsdb = MagicMock()
    engine, openfootball, highlightly, _tsdb = _engine_with_football_api(provider, tsdb=tsdb)
    result = engine.seed_competition(
        db=db_session,
        competition_name="UEFA Europa League",
        competition_type="Cup",
        format_engine="league_phase_knockout",
        season="2026/27",
        api_league_id=3,
        api_season=2026,
    )
    assert result.created == 1
    url, headers, provider_name = calls[0]
    assert url == "https://v3.football.api-sports.io/fixtures?league=3&season=2026"
    assert headers == {"x-apisports-key": "test-key"}
    assert provider_name == "football_api"
    assert "squads" not in url
    assert "media.api-sports.io" not in url
    openfootball.fetch_fixtures.assert_not_called()
    highlightly.fetch_fixtures.assert_not_called()
    tsdb.fetch_fixtures.assert_not_called()
    fixture = db_session.query(Fixture).one()
    assert fixture.api_id == "fa_880011"
    assert fixture.stage == "League Phase"
    assert fixture.home_team.name == "Roma"


def test_engine_uses_football_api_for_conference_league(db_session, monkeypatch):
    calls = []

    def _fetch(url, headers=None, **kwargs):
        calls.append(url)
        return {"response": [UECL_FIXTURE]}

    monkeypatch.setattr(
        "backend.services.providers.football_api.fetch_json_with_retry",
        _fetch,
    )
    engine, _openfootball, highlightly, tsdb = _engine_with_football_api(
        FootballApiProvider(api_key="test-key")
    )
    result = engine.seed_competition(
        db=db_session,
        competition_name="UEFA Conference League",
        competition_type="Cup",
        format_engine="league_phase_knockout",
        season="2026/27",
        api_league_id=848,
        api_season=2026,
    )
    assert result.created == 1
    assert calls == ["https://v3.football.api-sports.io/fixtures?league=848&season=2026"]
    assert "squads" not in calls[0]
    highlightly.fetch_fixtures.assert_not_called()
    tsdb.fetch_fixtures.assert_not_called()
    fixture = db_session.query(Fixture).one()
    assert fixture.api_id == "fa_880848"
    assert fixture.stage == "League Phase"
    assert fixture.matchday_number == 2


def test_football_api_shifted_kickoff_updates_unique_pairing(db_session, monkeypatch):
    comp = Competition(
        name="UEFA Europa League",
        type="Cup",
        format_engine="league_phase_knockout",
        api_league_id=3,
    )
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()
    home = Team(name="Roma", team_type="Club")
    away = Team(name="FC Porto", team_type="Club")
    db_session.add_all([home, away])
    db_session.flush()
    original = Fixture(
        tournament_id=tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        date_utc=datetime(2026, 8, 1, 19, 0, tzinfo=timezone.utc),
        stage="Qualifying",
        status="Scheduled",
    )
    db_session.add(original)
    db_session.commit()

    monkeypatch.setattr(
        "backend.services.providers.football_api.fetch_json_with_retry",
        lambda url, headers=None, **kwargs: {"response": [UEL_FIXTURE]},
    )
    tsdb = MagicMock()
    engine, _openfootball, _highlightly, _tsdb = _engine_with_football_api(
        FootballApiProvider(api_key="test-key"),
        tsdb=tsdb,
    )
    result = engine.seed_competition(
        db=db_session,
        competition_name="UEFA Europa League",
        competition_type="Cup",
        format_engine="league_phase_knockout",
        season="2026/27",
        api_league_id=3,
        api_season=2026,
    )
    assert result.created == 0
    assert result.updated == 1
    tsdb.fetch_fixtures.assert_not_called()
    db_session.refresh(original)
    assert original.api_id == "fa_880011"
    stored = original.date_utc
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored == datetime(2026, 9, 24, 19, 0, tzinfo=timezone.utc)
    assert original.stage == "League Phase"
    assert db_session.query(Fixture).filter_by(tournament_id=tourney.id).count() == 1


def test_seed_one_overlays_uel_and_conference_from_football_api(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "backend.services.feed_builder.CACHE_FILE_PATH",
        str(tmp_path / "fixtures_feed_cache.json"),
    )
    monkeypatch.setattr(
        "backend.services.seeder.fetch_and_seed_teams",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "backend.services.providers.football_data.FootballDataProvider.fetch_fixtures",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "backend.services.providers.highlightly.HighlightlyProvider.fetch_fixtures",
        lambda *args, **kwargs: [],
    )
    tsdb_calls = []

    def _tsdb(*args, **kwargs):
        tsdb_calls.append(args)
        return []

    monkeypatch.setattr(
        "backend.services.providers.thesportsdb.TheSportsDBProvider.fetch_fixtures",
        _tsdb,
    )

    def _fetch(url, headers=None, **kwargs):
        assert "squads" not in url
        assert "media.api-sports.io" not in url
        if "league=848" in url:
            return {"response": [UECL_FIXTURE]}
        return {"response": [UEL_FIXTURE]}

    monkeypatch.setattr(
        "backend.services.providers.football_api.fetch_json_with_retry",
        _fetch,
    )
    monkeypatch.setenv("FOOTBALLAPI_API_KEY", "test-key")

    uel = seed_single_competition(db_session, league_id=3)
    conference = seed_single_competition(db_session, league_id=848)
    assert uel["status"] == "success"
    assert conference["status"] == "success"
    assert uel["fixtures_created"] == 1
    assert conference["fixtures_created"] == 1
    assert db_session.query(Fixture).filter_by(api_id="fa_880011").one().stage == "League Phase"
    assert db_session.query(Fixture).filter_by(api_id="fa_880848").one().stage == "League Phase"
    assert tsdb_calls == []
