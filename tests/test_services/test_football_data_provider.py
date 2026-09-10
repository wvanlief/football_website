from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from backend.services.providers.football_data import FootballDataProvider, COMPETITION_CODE_MAP
from backend.crud.mapping import get_team_by_external_id

def test_competition_code_mapping():
    provider = FootballDataProvider()
    assert provider.get_competition_code("Premier League") == "PL"
    assert provider.get_competition_code("La Liga") == "PD"
    assert provider.get_competition_code("Brasileirão Série A") == "BSA"
    assert provider.get_competition_code("Non Existent League") is None

def test_get_football_data_org_key_prefers_canonical(monkeypatch):
    from backend.services.providers.football_data import get_football_data_org_key

    monkeypatch.setenv("FOOTBALL_DATA_ORG_KEY", "canonical")
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "alias-api")
    monkeypatch.setenv("FOOTBALL_DATA_KEY", "alias-short")
    assert get_football_data_org_key() == "canonical"


def test_get_football_data_org_key_reads_aliases(monkeypatch):
    from backend.services.providers.football_data import get_football_data_org_key

    monkeypatch.delenv("FOOTBALL_DATA_ORG_KEY", raising=False)
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "alias-api")
    monkeypatch.delenv("FOOTBALL_DATA_KEY", raising=False)
    assert get_football_data_org_key() == "alias-api"

    monkeypatch.delenv("FOOTBALL_DATA_API_KEY", raising=False)
    monkeypatch.setenv("FOOTBALL_DATA_KEY", "alias-short")
    assert get_football_data_org_key() == "alias-short"


@patch("backend.services.providers.football_data.fetch_json_with_retry")
def test_fetch_matches_date_range(mock_fetch):
    mock_fetch.return_value = {"matches": [{"id": 1}, {"id": 2}]}
    provider = FootballDataProvider(api_key="test_key")
    matches = provider.fetch_matches("2026-09-09", "2026-09-10")

    assert len(matches) == 2
    url = mock_fetch.call_args[0][0]
    assert url.startswith("https://api.football-data.org/v4/matches?")
    assert "dateFrom=2026-09-09" in url
    assert "dateTo=2026-09-10" in url
    assert mock_fetch.call_args.kwargs.get("use_cache") is False


@patch("backend.services.providers.football_data.fetch_json_with_retry")
def test_fetch_fixtures(mock_fetch):
    mock_fetch.return_value = {
        "matches": [
            {
                "id": 1001,
                "utcDate": "2026-08-22T14:00:00Z",
                "status": "SCHEDULED",
                "matchday": 1,
                "stage": "REGULAR_SEASON",
                "homeTeam": {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal"},
                "awayTeam": {"id": 66, "name": "Manchester United FC", "shortName": "Man United"}
            }
        ]
    }
    provider = FootballDataProvider(api_key="test_key")
    fixtures = provider.fetch_fixtures("Premier League", 2026)

    assert len(fixtures) == 1
    assert fixtures[0]["id"] == 1001
    mock_fetch.assert_called_once()

def test_resolve_team_and_mapping(db_session):
    provider = FootballDataProvider()
    raw_home = {
        "id": 57,
        "name": "Arsenal FC",
        "shortName": "Arsenal",
        "crest": "https://crests.football-data.org/57.png",
        "area": {"name": "England"},
    }

    # Resolve team (should create team and external mapping)
    team = provider.resolve_team(db_session, raw_home, team_type="Club")
    assert team is not None
    assert team.name == "Arsenal"
    assert team.logo_url == "https://crests.football-data.org/57.png"

    # Verify external mapping exists in DB
    mapped_team = get_team_by_external_id(db_session, "football_data", 57)
    assert mapped_team is not None
    assert mapped_team.id == team.id

    # Second resolve should hit mapping directly
    team_again = provider.resolve_team(db_session, raw_home, team_type="Club")
    assert team_again.id == team.id

def test_normalize_fixture_payload(db_session):
    provider = FootballDataProvider()
    item = {
        "id": 1001,
        "utcDate": "2026-08-22T14:00:00Z",
        "status": "FINISHED",
        "matchday": 1,
        "stage": "REGULAR_SEASON",
        "homeTeam": {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal"},
        "awayTeam": {"id": 66, "name": "Manchester United FC", "shortName": "Man United"},
        "score": {
            "fullTime": {"home": 2, "away": 1}
        }
    }

    norm = provider.normalize_fixture_payload(db_session, item, tournament_id=10, competition_type="League")
    assert norm is not None
    assert norm["api_id"] == "fd_1001"
    assert norm["provider"] == "football_data"
    assert norm["status"] == "Finished"
    assert norm["home_score"] == 2
    assert norm["away_score"] == 1
    assert norm["home_team"].name == "Arsenal"
    assert norm["away_team"].name == "Man United"
