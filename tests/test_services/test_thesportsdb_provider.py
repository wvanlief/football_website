from unittest.mock import patch
from datetime import datetime, timezone

import pytest

from backend.crud.mapping import get_external_id_for_competition, get_team_by_external_id
from backend.database import Competition
from backend.services.providers.thesportsdb import (
    CALENDAR_YEAR_COMPETITIONS,
    LEAGUE_ID_MAP,
    SEARCH_RESOLVED_COMPETITIONS,
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

TSDB_UECL_EVENT = {
    "idEvent": "3000001",
    "idLeague": "5071",
    "strLeague": "UEFA Europa Conference League",
    "strHomeTeam": "Fiorentina",
    "strAwayTeam": "Real Betis",
    "idHomeTeam": "133832",
    "idAwayTeam": "133739",
    "intRound": "1",
    "intHomeScore": None,
    "intAwayScore": None,
    "strTimestamp": "2026-10-01T19:00:00",
    "dateEvent": "2026-10-01",
    "strTime": "19:00:00",
    "strPostponed": "no",
    "strStatus": "Not Started",
}

TSDB_EURO_SEARCH = {
    "countries": [
        {
            "idLeague": "4481",
            "strLeague": "UEFA Europa League",
            "strSport": "Soccer",
        },
        {
            "idLeague": "5071",
            "strLeague": "UEFA Europa Conference League",
            "strLeagueAlternate": "UEFA Conference League",
            "strSport": "Soccer",
        },
    ]
}


def _tsdb_http(events=None, search=None):
    """Route mocked TheSportsDB HTTP by endpoint."""

    def side_effect(url, *args, **kwargs):
        if "search_all_leagues.php" in url or "all_leagues.php" in url:
            return search if search is not None else TSDB_EURO_SEARCH
        if "eventsseason.php" in url:
            if isinstance(events, dict):
                return events
            return {"events": events}
        return {}

    return side_effect


def test_league_id_mapping_covers_european_cups():
    provider = TheSportsDBProvider()
    assert provider.get_league_id("UEFA Europa League") is None
    assert provider.get_league_id("UEFA Conference League") is None
    assert "UEFA Europa League" not in LEAGUE_ID_MAP
    assert "UEFA Conference League" not in LEAGUE_ID_MAP
    assert "UEFA Europa League" in SEARCH_RESOLVED_COMPETITIONS
    assert provider.get_league_id("UEFA Champions League") == "4480"
    assert provider.get_league_id("Premier League") == "4328"
    assert provider.get_league_id("Non Existent League") is None


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
    mock_fetch.side_effect = _tsdb_http(events=[TSDB_UEL_EVENT])
    provider = TheSportsDBProvider(api_key="test-key")
    fixtures = provider.fetch_fixtures("UEFA Europa League", 2026)

    assert len(fixtures) == 1
    assert fixtures[0]["idEvent"] == "2272310"
    urls = [call.args[0] for call in mock_fetch.call_args_list]
    assert any("search_all_leagues.php" in url for url in urls)
    season_url = next(url for url in urls if "eventsseason.php" in url)
    assert season_url.startswith("https://www.thesportsdb.com/api/v1/json/test-key/eventsseason.php?")
    assert "id=4481" in season_url
    assert "s=2026-2027" in season_url
    assert mock_fetch.call_args.kwargs.get("provider") == "thesportsdb"


@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
def test_fetch_fixtures_drops_cross_league_events(mock_fetch):
    foreign = dict(TSDB_UEL_EVENT)
    foreign["idLeague"] = "4480"
    mock_fetch.side_effect = _tsdb_http(events=[TSDB_UEL_EVENT, foreign])

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
    mock_fetch.side_effect = _tsdb_http(events={"events": None})
    provider = TheSportsDBProvider(api_key="test-key")
    assert provider.fetch_fixtures("UEFA Conference League", 2026) == []
    urls = [call.args[0] for call in mock_fetch.call_args_list]
    season_url = next(url for url in urls if "eventsseason.php" in url)
    assert "id=5071" in season_url


@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
def test_empty_search_skips_season_events(mock_fetch):
    mock_fetch.side_effect = _tsdb_http(
        events=[TSDB_UEL_EVENT],
        search={"countries": [], "leagues": []},
    )
    provider = TheSportsDBProvider(api_key="test-key")
    assert provider.fetch_fixtures("UEFA Europa League", 2026) == []
    urls = [call.args[0] for call in mock_fetch.call_args_list]
    assert any("search_all_leagues.php" in url for url in urls)
    assert any("all_leagues.php" in url for url in urls)
    assert not any("eventsseason.php" in url for url in urls)


@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
def test_search_persists_league_id_on_competition_mapping(mock_fetch, db_session):
    mock_fetch.side_effect = _tsdb_http(events=[TSDB_UEL_EVENT])
    comp = Competition(name="UEFA Europa League", type="Cup", format_engine="league_phase_knockout")
    db_session.add(comp)
    db_session.flush()

    provider = TheSportsDBProvider(api_key="test-key")
    fixtures = provider.fetch_fixtures("UEFA Europa League", 2026, db=db_session, competition=comp)

    assert len(fixtures) == 1
    assert get_external_id_for_competition(db_session, comp.id, "thesportsdb") == "4481"

    mock_fetch.reset_mock()
    mock_fetch.side_effect = _tsdb_http(events=[TSDB_UEL_EVENT], search={"countries": []})
    again = provider.fetch_fixtures("UEFA Europa League", 2026, db=db_session, competition=comp)
    assert len(again) == 1
    urls = [call.args[0] for call in mock_fetch.call_args_list]
    assert not any("search_all_leagues.php" in url for url in urls)
    assert any("eventsseason.php" in url and "id=4481" in url for url in urls)


@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
def test_search_skips_non_soccer_and_prefers_exact_name(mock_fetch):
    mock_fetch.side_effect = _tsdb_http(
        events=[TSDB_UEL_EVENT],
        search={
            "countries": [
                {
                    "idLeague": "9999",
                    "strLeague": "UEFA Europa League",
                    "strSport": "Basketball",
                },
                {
                    "idLeague": "1111",
                    "strLeague": "Europa League",
                    "strSport": "Soccer",
                },
                {
                    "idLeague": "4481",
                    "strLeague": "UEFA Europa League",
                    "strSport": "Soccer",
                },
            ]
        },
    )
    provider = TheSportsDBProvider(api_key="test-key")
    fixtures = provider.fetch_fixtures("UEFA Europa League", 2026)
    assert len(fixtures) == 1
    season_url = next(
        call.args[0] for call in mock_fetch.call_args_list if "eventsseason.php" in call.args[0]
    )
    assert "id=4481" in season_url
    assert "id=9999" not in season_url
    assert "id=1111" not in season_url


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
    assert norm["stage"] == "League Phase"
    assert norm["home_team"].name == "Roma"
    assert norm["away_team"].name == "Athletic Club"
    assert norm["home_team"].logo_url == TSDB_UEL_EVENT["strHomeTeamBadge"]

    mapped = get_team_by_external_id(db_session, "thesportsdb", "133739")
    assert mapped is not None
    assert mapped.id == norm["home_team"].id


def test_finished_event_with_partial_score_remains_ingestible(db_session):
    provider = TheSportsDBProvider()
    item = dict(TSDB_UEL_EVENT)
    item["intAwayScore"] = None

    norm = provider.normalize_fixture_payload(
        db_session, item, tournament_id=10, competition_type="Cup"
    )

    assert norm["status"] == "Live"
    assert norm["home_score"] == 2
    assert norm["away_score"] is None


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
