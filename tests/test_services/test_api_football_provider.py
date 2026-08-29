from unittest.mock import patch
from backend.services.providers.api_football import ApiFootballProvider


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
