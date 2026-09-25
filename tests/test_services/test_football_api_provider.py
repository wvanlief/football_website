from datetime import datetime, timezone
from copy import deepcopy
from unittest.mock import MagicMock
import pytest

from backend.database import Competition, Fixture, Team, Tournament
from backend.services.ingestion.engine import IngestionEngine
from backend.services.providers.football_api import FootballApiProvider
from backend.services.rate_limiter import APIRateLimiter

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

UECL_FIXTURE = {
    "fixture": {
        "id": 990022,
        "date": "2026-10-02T16:45:00+00:00",
        "status": {"short": "NS"},
    },
    "league": {"id": 848, "season": 2026, "round": "League Stage - 2"},
    "teams": {
        "home": {"id": 99, "name": "Fiorentina"},
        "away": {"id": 100, "name": "Real Betis"},
    },
    "goals": {"home": None, "away": None},
}


@pytest.mark.parametrize("scores", [
    {"home": None, "away": 1},
    {"home": 1, "away": None},
])
def test_finished_football_api_fixture_requires_both_scores(db_session, scores):
    item = deepcopy(UEL_FIXTURE)
    item["fixture"]["status"]["short"] = "FT"
    item["goals"] = scores
    provider = FootballApiProvider(api_key="test-key")

    assert provider.normalize_fixture_payload(db_session, item, 1) is None
    item["fixture"]["status"]["short"] = "1H"
    assert provider.normalize_fixture_payload(db_session, item, 1)["status"] == "Live"


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


def test_engine_uses_football_api_for_uel_and_skips_thesportsdb(db_session):
    fd = MagicMock()
    fd.fetch_fixtures.return_value = []
    fd.last_request_skipped = False
    of = MagicMock()
    of.fetch_fixtures.return_value = []
    fa = FootballApiProvider(api_key="test-key")
    fa.fetch_fixtures = MagicMock(return_value=[UEL_FIXTURE])
    tsdb = MagicMock()

    engine = IngestionEngine(
        fd_provider=fd,
        openfootball_provider=of,
        football_api_provider=fa,
        tsdb_provider=tsdb,
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

    assert result.created == 1
    fa.fetch_fixtures.assert_called_once()
    assert fa.fetch_fixtures.call_args.kwargs["league_id"] == 3
    tsdb.fetch_fixtures.assert_not_called()
    of.fetch_fixtures.assert_not_called()
    fixture = db_session.query(Fixture).one()
    assert fixture.api_id == "fa_880011"
    assert fixture.stage == "League Phase"


def test_engine_uses_football_api_for_conference_league(db_session):
    fd = MagicMock()
    fd.fetch_fixtures.return_value = []
    fd.last_request_skipped = False
    fa = FootballApiProvider(api_key="test-key")
    fa.fetch_fixtures = MagicMock(return_value=[UECL_FIXTURE])
    tsdb = MagicMock()
    engine = IngestionEngine(
        fd_provider=fd,
        openfootball_provider=MagicMock(),
        football_api_provider=fa,
        tsdb_provider=tsdb,
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
    assert fa.fetch_fixtures.call_args.kwargs["league_id"] == 848
    tsdb.fetch_fixtures.assert_not_called()
    fixture = db_session.query(Fixture).one()
    assert fixture.api_id == "fa_990022"


def test_football_api_shifted_kickoff_updates_unique_pairing(db_session):
    comp = Competition(name="UEFA Europa League", type="Cup", format_engine="league_phase_knockout", api_league_id=3)
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

    fd = MagicMock()
    fd.fetch_fixtures.return_value = []
    fd.last_request_skipped = False
    fa = FootballApiProvider(api_key="test-key")
    fa.fetch_fixtures = MagicMock(return_value=[UEL_FIXTURE])
    engine = IngestionEngine(
        fd_provider=fd,
        openfootball_provider=MagicMock(),
        football_api_provider=fa,
        tsdb_provider=MagicMock(),
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
    db_session.refresh(original)
    assert original.api_id == "fa_880011"
    stored = original.date_utc
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored == datetime(2026, 9, 24, 19, 0, tzinfo=timezone.utc)
    assert db_session.query(Fixture).filter_by(tournament_id=tourney.id).count() == 1


def test_football_api_rate_limit_leaves_headroom():
    limits = APIRateLimiter.LIMITS["football_api"]
    assert limits == {"per_min": 10, "per_day": 90}
    assert "api_football" not in APIRateLimiter.LIMITS
