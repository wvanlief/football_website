from unittest.mock import patch
from datetime import datetime, timezone

import pytest

from backend.crud.mapping import get_team_by_external_id
from backend.services.providers.thesportsdb import (
    CALENDAR_YEAR_COMPETITIONS,
    LEAGUE_ID_MAP,
    TheSportsDBProvider,
    parse_event_datetime,
    parse_event_status,
    parse_score,
    season_string,
)

TSDB_UEL_EVENT = {
    "idEvent": "2272310",
    "strEvent": "Roma vs Athletic Club",
    "strSeason": "2026-2027",
    "idLeague": "4481",
    "strLeague": "UEFA Europa League",
    "strHomeTeam": "Roma",
    "strAwayTeam": "Athletic Club",
    "idHomeTeam": "133739",
    "idAwayTeam": "133704",
    "intRound": "1",
    "intHomeScore": "2",
    "intAwayScore": "1",
    "strTimestamp": "2026-09-17T19:00:00",
    "dateEvent": "2026-09-17",
    "strTime": "19:00:00",
    "strHomeTeamBadge": "https://r2.thesportsdb.com/images/media/team/badge/roma.png",
    "strAwayTeamBadge": "https://r2.thesportsdb.com/images/media/team/badge/athletic.png",
    "strPostponed": "no",
    "strStatus": "FT",
}


def test_league_id_mapping_covers_european_cups():
    provider = TheSportsDBProvider()
    assert provider.get_league_id("UEFA Europa League") == "4481"
    assert provider.get_league_id("UEFA Conference League") == "5071"
    assert provider.get_league_id("UEFA Champions League") == "4480"
    assert provider.get_league_id("Premier League") == "4328"
    assert provider.get_league_id("Non Existent League") is None
    assert LEAGUE_ID_MAP["UEFA Europa League"] == "4481"


def test_season_string_split_vs_calendar():
    assert season_string("UEFA Europa League", 2026) == "2026-2027"
    assert season_string("UEFA Conference League", 2026) == "2026-2027"
    assert season_string("Major League Soccer", 2026) == "2026"
    assert "Major League Soccer" in CALENDAR_YEAR_COMPETITIONS
    assert "UEFA Europa League" not in CALENDAR_YEAR_COMPETITIONS


@pytest.mark.parametrize(
    "raw,postponed,expected",
    [
        ("FT", "no", "Finished"),
        ("AET", None, "Finished"),
        ("PEN", None, "Finished"),
        ("Match Finished", None, "Finished"),
        ("1H", None, "Live"),
        ("2H", None, "Live"),
        ("HT", None, "Live"),
        ("Not Started", None, "Scheduled"),
        (None, None, "Scheduled"),
        ("", None, "Scheduled"),
        ("UNKNOWN", None, "Scheduled"),
        ("FT", "yes", "Postponed"),
        ("Postponed", None, "Postponed"),
        ("Cancelled", None, "Postponed"),
    ],
)
def test_parse_event_status(raw, postponed, expected):
    assert parse_event_status(raw, postponed) == expected


def test_parse_event_datetime_from_timestamp():
    dt = parse_event_datetime({"strTimestamp": "2026-09-17T19:00:00", "dateEvent": "2026-09-17"})
    assert dt == datetime(2026, 9, 17, 19, 0, tzinfo=timezone.utc)


def test_parse_event_datetime_from_date_and_time():
    dt = parse_event_datetime({"dateEvent": "2026-09-17", "strTime": "19:00:00"})
    assert dt == datetime(2026, 9, 17, 19, 0, tzinfo=timezone.utc)


def test_parse_event_datetime_missing_date_returns_none():
    assert parse_event_datetime({}) is None


def test_parse_score():
    assert parse_score("2") == 2
    assert parse_score(3) == 3
    assert parse_score("") is None
    assert parse_score(None) is None


@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
def test_fetch_fixtures_mocked(mock_fetch):
    mock_fetch.return_value = {"events": [TSDB_UEL_EVENT]}
    provider = TheSportsDBProvider(api_key="test-key")
    fixtures = provider.fetch_fixtures("UEFA Europa League", 2026)

    assert len(fixtures) == 1
    assert fixtures[0]["idEvent"] == "2272310"
    mock_fetch.assert_called_once()
    url = mock_fetch.call_args[0][0]
    assert url.startswith("https://www.thesportsdb.com/api/v1/json/test-key/eventsseason.php?")
    assert "id=4481" in url
    assert "s=2026-2027" in url
    assert mock_fetch.call_args.kwargs.get("provider") == "thesportsdb"


@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
def test_fetch_fixtures_drops_cross_league_events(mock_fetch):
    foreign = dict(TSDB_UEL_EVENT)
    foreign["idLeague"] = "4480"
    mock_fetch.return_value = {"events": [TSDB_UEL_EVENT, foreign]}

    provider = TheSportsDBProvider(api_key="test-key")
    fixtures = provider.fetch_fixtures("UEFA Europa League", 2026)

    assert len(fixtures) == 1
    assert fixtures[0]["idLeague"] == "4481"


@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
def test_fetch_fixtures_unmapped_competition_skips_http(mock_fetch):
    provider = TheSportsDBProvider()
    assert provider.fetch_fixtures("Unknown Cup", 2026) == []
    mock_fetch.assert_not_called()


@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
def test_fetch_fixtures_empty_payload(mock_fetch):
    mock_fetch.return_value = {"events": None}
    provider = TheSportsDBProvider(api_key="test-key")
    assert provider.fetch_fixtures("UEFA Conference League", 2026) == []
    url = mock_fetch.call_args[0][0]
    assert "id=5071" in url


def test_normalize_fixture_payload(db_session):
    provider = TheSportsDBProvider()
    norm = provider.normalize_fixture_payload(
        db_session, TSDB_UEL_EVENT, tournament_id=10, competition_type="Cup"
    )

    assert norm is not None
    assert norm["api_id"] == "tsdb_2272310"
    assert norm["provider_name"] == "thesportsdb"
    assert norm["status"] == "Finished"
    assert norm["home_score"] == 2
    assert norm["away_score"] == 1
    assert norm["matchday_number"] == 1
    assert norm["home_team"].name == "Roma"
    assert norm["away_team"].name == "Athletic Club"
    assert norm["home_team"].logo_url == TSDB_UEL_EVENT["strHomeTeamBadge"]

    mapped = get_team_by_external_id(db_session, "thesportsdb", "133739")
    assert mapped is not None
    assert mapped.id == norm["home_team"].id


def test_normalize_qualifying_round_has_no_matchday(db_session):
    provider = TheSportsDBProvider()
    item = dict(TSDB_UEL_EVENT)
    item["intRound"] = "400"
    norm = provider.normalize_fixture_payload(db_session, item, tournament_id=10)
    assert norm["stage"] == "Qualifying"
    assert norm["matchday_number"] is None


def test_normalize_missing_date_returns_none(db_session):
    provider = TheSportsDBProvider()
    item = {"idEvent": "1", "strHomeTeam": "A", "strAwayTeam": "B"}
    assert provider.normalize_fixture_payload(db_session, item, tournament_id=1) is None
