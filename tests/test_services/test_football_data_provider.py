from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from backend.services.providers.football_data import (
    COMPETITION_CODE_MAP,
    FootballDataProvider,
    extract_match_scores,
    find_fixture_for_match,
)
from backend.crud.mapping import get_team_by_external_id
from backend.database import Competition, Fixture, Team, Tournament
from backend.services.ingestion import NameNormalizer

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
    assert mock_fetch.call_args.kwargs["use_cache"] is True


@patch("backend.services.providers.football_data.fetch_json_with_retry")
def test_fetch_fixtures_can_bypass_cache(mock_fetch):
    mock_fetch.return_value = {"matches": []}

    FootballDataProvider(api_key="test_key").fetch_fixtures(
        "Premier League", 2026, use_cache=False
    )

    assert mock_fetch.call_args.kwargs["use_cache"] is False


@patch("backend.services.providers.football_data.fetch_json_with_retry")
def test_fetch_fixtures_records_rate_limit_skip(mock_fetch):
    mock_fetch.side_effect = RuntimeError("rate limit safeguard")
    provider = FootballDataProvider(api_key="test_key")

    assert provider.fetch_fixtures("Premier League", 2026) == []
    assert provider.last_request_skipped is True


def test_extract_match_scores_prefers_complete_pair_over_partial_full_time():
    item = {
        "score": {
            "fullTime": {"home": 2, "away": None},
            "regularTime": {"home": 1, "away": 1},
            "halfTime": {"home": 0, "away": 0},
        }
    }

    assert extract_match_scores(item) == (1, 1)


def test_extract_match_scores_uses_partial_pair_as_last_resort():
    item = {"score": {"fullTime": {"home": 2, "away": None}}}

    assert extract_match_scores(item) == (2, None)


def test_raw_api_id_lookup_is_restricted_by_competition(db_session):
    pl = Competition(name="Premier League", type="League")
    cl = Competition(name="UEFA Champions League", type="Cup")
    db_session.add_all([pl, cl])
    db_session.flush()
    pl_tourney = Tournament(competition_id=pl.id, season_name="2026/27", status="Active")
    cl_tourney = Tournament(competition_id=cl.id, season_name="2026/27", status="Active")
    db_session.add_all([pl_tourney, cl_tourney])
    db_session.flush()
    home = Team(name="Arsenal")
    away = Team(name="Chelsea")
    db_session.add_all([home, away])
    db_session.flush()
    foreign = Fixture(
        tournament_id=cl_tourney.id,
        api_id="4242",
        home_team_id=home.id,
        away_team_id=away.id,
        date_utc=datetime.now(timezone.utc),
        status="Scheduled",
        stage="Regular Season",
    )
    expected = Fixture(
        tournament_id=pl_tourney.id,
        api_id="4242",
        home_team_id=home.id,
        away_team_id=away.id,
        date_utc=datetime.now(timezone.utc),
        status="Scheduled",
        stage="Regular Season",
    )
    db_session.add_all([foreign, expected])
    db_session.commit()

    match = {"id": 4242, "competition": {"code": "PL"}}
    found = find_fixture_for_match(
        db_session,
        match,
        [home, away],
        NameNormalizer(),
    )

    assert found.id == expected.id


def test_find_fixture_matches_atletico_de_madrid_alias(db_session):
    from backend.services.providers.football_data import apply_matches_to_existing_fixtures

    cl = Competition(name="UEFA Champions League", type="Cup")
    db_session.add(cl)
    db_session.flush()
    tourney = Tournament(competition_id=cl.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()
    home = Team(name="Liverpool")
    away = Team(name="Atlético Madrid")
    db_session.add_all([home, away])
    db_session.flush()
    kickoff = datetime(2026, 9, 9, 19, 0, tzinfo=timezone.utc)
    fixture = Fixture(
        tournament_id=tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        date_utc=kickoff.replace(tzinfo=None),
        stage="League Phase",
        status="Scheduled",
    )
    db_session.add(fixture)
    db_session.commit()

    updated, finished = apply_matches_to_existing_fixtures(
        db_session,
        [
            {
                "id": 575340,
                "utcDate": "2026-09-09T19:00:00Z",
                "status": "FINISHED",
                "homeTeam": {"name": "Liverpool FC", "shortName": "Liverpool"},
                "awayTeam": {
                    "name": "Club Atlético de Madrid",
                    "shortName": "Atleti",
                },
                "score": {"fullTime": {"home": 2, "away": 1}},
                "competition": {"code": "CL", "name": "UEFA Champions League"},
            }
        ],
        tournament_id=tourney.id,
    )

    assert (updated, finished) == (0, 1)
    db_session.refresh(fixture)
    assert fixture.status == "Finished"
    assert fixture.home_score == 2
    assert fixture.away_score == 1
    assert fixture.api_id == "fd_575340"


def test_find_team_prefers_full_name_over_short_slovan(db_session):
    from backend.services.providers.football_data import _find_team_for_sync

    bratislava = Team(name="Slovan Bratislava")
    liberec = Team(name="Slovan Liberec")
    db_session.add_all([bratislava, liberec])
    db_session.commit()

    found = _find_team_for_sync(
        db_session,
        {"name": "ŠK Slovan Bratislava", "shortName": "Slovan"},
        [liberec, bratislava],
        NameNormalizer(),
    )
    assert found.id == bratislava.id


def test_raw_api_id_from_other_competition_is_rejected(db_session):
    pl = Competition(name="Premier League", type="League")
    cl = Competition(name="UEFA Champions League", type="Cup")
    db_session.add_all([pl, cl])
    db_session.flush()
    cl_tourney = Tournament(competition_id=cl.id, season_name="2026/27", status="Active")
    db_session.add(cl_tourney)
    db_session.flush()
    fixture = Fixture(
        tournament_id=cl_tourney.id,
        api_id="4242",
        date_utc=datetime.now(timezone.utc),
        status="Scheduled",
        stage="Regular Season",
    )
    db_session.add(fixture)
    db_session.commit()

    found = find_fixture_for_match(
        db_session,
        {"id": 4242, "competition": {"code": "PL"}},
        [],
        NameNormalizer(),
    )

    assert found is None

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
    assert norm["away_team"].name == "Manchester United"
