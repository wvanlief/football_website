from unittest.mock import patch
import inspect

import pytest

from backend.services.providers.api_football import (
    ApiFootballProvider,
    STATUS_MAP,
    call_football_api,
    parse_match_status,
)


def test_normalize_fixture_payload_finished():
    """Verifies parsing and normalization of a finished API-Football fixture payload."""
    provider = ApiFootballProvider(api_key="test-key")
    raw_payload = {
        "fixture": {
            "id": 99001,
            "date": "2026-08-22T14:00:00Z",
            "status": {"short": "FT"}
        },
        "teams": {
            "home": {"id": 33, "name": "Manchester United"},
            "away": {"id": 40, "name": "Liverpool"}
        },
        "goals": {"home": 2, "away": 1},
        "league": {"round": "Regular Season - 3"}
    }

    normalized = provider.normalize_fixture_payload(raw_payload)

    assert normalized["provider_name"] == "api_football"
    assert normalized["api_id"] == "99001"
    assert normalized["status"] == "Finished"
    assert normalized["home_team_name"] == "Manchester United"
    assert normalized["home_team_external_id"] == "33"
    assert normalized["home_team_api_id"] == 33
    assert normalized["away_team_name"] == "Liverpool"
    assert normalized["away_team_external_id"] == "40"
    assert normalized["away_team_api_id"] == 40
    assert normalized["home_score"] == 2
    assert normalized["away_score"] == 1
    assert normalized["matchday_number"] == 3


def test_normalize_fixture_payload_live():
    """Verifies normalization of an in-play (2H) fixture payload."""
    provider = ApiFootballProvider(api_key="test-key")
    raw_payload = {
        "fixture": {
            "id": 99002,
            "date": "2026-08-22T16:30:00Z",
            "status": {"short": "2H"}
        },
        "teams": {
            "home": {"id": 50, "name": "Manchester City"},
            "away": {"id": 42, "name": "Arsenal"}
        },
        "goals": {"home": 1, "away": 1},
        "league": {"round": "Regular Season - 3"}
    }

    normalized = provider.normalize_fixture_payload(raw_payload)

    assert normalized["api_id"] == "99002"
    assert normalized["status"] == "Live"
    assert normalized["home_score"] == 1
    assert normalized["away_score"] == 1


@patch("backend.services.providers.api_football.fetch_json_with_retry")
def test_fetch_fixtures_mocked(mock_fetch):
    """Verifies fetch_fixtures API call parsing."""
    mock_fetch.return_value = {
        "response": [
            {"fixture": {"id": 123}, "teams": {}, "goals": {}, "league": {}}
        ]
    }

    provider = ApiFootballProvider(api_key="test-key")
    res = provider.fetch_fixtures(league_id=39, season=2026)

    assert len(res) == 1
    assert res[0]["fixture"]["id"] == 123
    mock_fetch.assert_called_once()


@pytest.mark.parametrize(
    "short,expected",
    [
        ("FT", "Finished"),
        ("AET", "Finished"),
        ("PEN", "Finished"),
        ("1H", "Live"),
        ("2H", "Live"),
        ("HT", "Live"),
        ("ET", "Live"),
        ("P", "Live"),
        ("LIVE", "Live"),
        ("NS", "Scheduled"),
        ("TBD", "Scheduled"),
        ("PST", "Postponed"),
        ("CANC", "Postponed"),
        ("ABD", "Postponed"),
        ("UNKNOWN", "Scheduled"),
        (None, "Scheduled"),
        ("", "Scheduled"),
    ],
)
def test_parse_match_status(short, expected):
    assert parse_match_status(short) == expected


def test_parse_match_status_live_default():
    """Live sync paths pass default='Live' for unknown codes in an active feed."""
    assert parse_match_status(None, default="Live") == "Live"
    assert parse_match_status("FT", default="Live") == "Finished"


def test_status_map_covers_finished_live_postponed():
    finished = {k for k, v in STATUS_MAP.items() if v == "Finished"}
    live = {k for k, v in STATUS_MAP.items() if v == "Live"}
    postponed = {k for k, v in STATUS_MAP.items() if v == "Postponed"}
    assert finished == {"FT", "AET", "PEN"}
    assert {"1H", "2H", "HT", "ET", "P", "LIVE"}.issubset(live)
    assert postponed == {"PST", "CANC", "ABD"}


@patch("backend.services.providers.api_football.fetch_json_with_retry")
@patch.dict("os.environ", {"FOOTBALL_API_KEY": "test-key"}, clear=False)
def test_call_football_api_enforces_rate_limiting(mock_fetch):
    """Canonical client must pass provider='api_football' so the rate limiter runs."""
    mock_fetch.return_value = {"response": []}

    call_football_api("fixtures", {"date": "2026-09-03"})

    mock_fetch.assert_called_once()
    _, kwargs = mock_fetch.call_args
    assert kwargs.get("provider") == "api_football"
    assert "x-apisports-key" in kwargs.get("headers", {})


def test_call_football_api_requires_api_key():
    with patch("os.getenv", return_value=None):
        with pytest.raises(ValueError, match="FOOTBALL_API_KEY"):
            call_football_api("fixtures")


def test_seeder_no_longer_defines_call_football_api():
    """Acceptance: call_football_api must not be defined in seeder.py."""
    import backend.services.seeder as seeder

    source = inspect.getsource(seeder)
    assert "def call_football_api" not in source


def test_updater_imports_provider_not_seeder():
    """Acceptance: updater.py imports call_football_api from the provider module."""
    import backend.services.updater as updater

    source = inspect.getsource(updater)
    assert "from backend.services.seeder import call_football_api" not in source
    assert "from backend.services.providers.api_football import" in source
    assert updater.call_football_api.__module__ == "backend.services.providers.api_football"
