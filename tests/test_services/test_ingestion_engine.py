from unittest.mock import patch
from datetime import datetime, timezone
import pytest

from backend.database import Competition, Tournament, Fixture, Team, ExternalTeamMapping
from backend.crud.mapping import get_external_id_for_competition, get_team_by_external_id
from backend.services.ingestion.engine import IngestionEngine, seed_competition
from backend.services.ingestion.preflight import IngestionAborted

FD_ARSENAL_CREST = "https://crests.football-data.org/57.png"
FD_UNITED_CREST = "https://crests.football-data.org/66.png"

FD_PL_MATCH = {
    "id": 8001,
    "utcDate": "2026-08-22T14:00:00Z",
    "status": "SCHEDULED",
    "matchday": 1,
    "stage": "REGULAR_SEASON",
    "homeTeam": {
        "id": 57,
        "name": "Arsenal FC",
        "shortName": "Arsenal",
        "crest": FD_ARSENAL_CREST,
    },
    "awayTeam": {
        "id": 66,
        "name": "Manchester United FC",
        "shortName": "Man United",
        "crest": FD_UNITED_CREST,
    },
}

OF_PL_MATCH = {
    "round": "Matchday 1",
    "date": "2026-08-22",
    "time": "14:00",
    "team1": "Arsenal FC",
    "team2": "Chelsea FC",
}

OF_UCL_MATCH = {
    "round": "Matchday 1",
    "date": "2026-09-09",
    "time": "20:00",
    "team1": "Invented UCL Home",
    "team2": "Invented UCL Away",
}


def _fd_http(matches=None, teams=None):
    def _fetch(url, *args, **kwargs):
        if "/matches" in url:
            return {"matches": list(matches or [])}
        if "/teams" in url:
            return {"teams": list(teams or [])}
        return {}
    return _fetch


def _of_http(matches=None):
    def _fetch(url, *args, **kwargs):
        if "football.json" in url:
            return {"name": "community", "matches": list(matches or [])}
        return {}
    return _fetch


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
        {"idLeague": "4481", "strLeague": "UEFA Europa League", "strSport": "Soccer"},
        {
            "idLeague": "5071",
            "strLeague": "UEFA Europa Conference League",
            "strLeagueAlternate": "UEFA Conference League",
            "strSport": "Soccer",
        },
    ]
}


def _tsdb_http(events=None, search=None):
    def side_effect(url, *args, **kwargs):
        if "search_all_leagues.php" in url or "all_leagues.php" in url:
            return search if search is not None else TSDB_EURO_SEARCH
        if "eventsseason.php" in url:
            if isinstance(events, dict):
                return events
            return {"events": events}
        return {}

    return side_effect


@patch("backend.services.providers.openfootball.fetch_json_with_retry")
@patch("backend.services.providers.football_data.fetch_json_with_retry")
def test_seed_competition_with_football_data_org_http(mock_fd_http, mock_of_http, db_session):
    """seed_competition with Football-Data.org HTTP creates mapped fixtures and stores crests."""
    mock_fd_http.side_effect = _fd_http(matches=[FD_PL_MATCH])
    mock_of_http.side_effect = _of_http(matches=[OF_PL_MATCH])

    result = seed_competition(
        db=db_session,
        competition_name="Premier League",
        competition_type="League",
        format_engine="league",
        season="2026/27",
        api_league_id=39,
        api_season=2026,
    )

    assert result.created == 1
    tourney = db_session.query(Tournament).join(Competition).filter(
        Competition.name == "Premier League"
    ).one()
    fixture = db_session.query(Fixture).filter_by(tournament_id=tourney.id).one()
    assert fixture.api_id == "fd_8001"
    assert fixture.home_team.name == "Arsenal"
    assert fixture.away_team.name == "Manchester United"
    assert fixture.home_team.logo_url == FD_ARSENAL_CREST
    assert fixture.away_team.logo_url == FD_UNITED_CREST

    mapped = get_team_by_external_id(db_session, "football_data", 57)
    assert mapped is not None
    assert mapped.id == fixture.home_team_id
    mapping = db_session.query(ExternalTeamMapping).filter_by(
        provider_name="football_data",
        external_id="57",
    ).one()
    assert mapping.team_id == fixture.home_team_id


@patch("backend.services.providers.openfootball.fetch_json_with_retry")
@patch("backend.services.providers.football_data.fetch_json_with_retry")
def test_empty_football_data_falls_back_to_openfootball(mock_fd_http, mock_of_http, db_session):
    """Empty Football-Data.org payload falls back to published openfootball domestic datasets."""
    mock_fd_http.side_effect = _fd_http(matches=[])
    mock_of_http.side_effect = _of_http(matches=[OF_PL_MATCH])

    result = seed_competition(
        db=db_session,
        competition_name="Premier League",
        competition_type="League",
        format_engine="league",
        season="2026/27",
        api_league_id=39,
        api_season=2026,
    )

    assert result.created == 1
    tourney = db_session.query(Tournament).join(Competition).filter(
        Competition.name == "Premier League"
    ).one()
    fixture = db_session.query(Fixture).filter_by(tournament_id=tourney.id).one()
    assert fixture.home_team.name in ("Arsenal FC", "Arsenal")
    assert fixture.away_team.name in ("Chelsea FC", "Chelsea")
    assert fixture.api_id
    assert not str(fixture.api_id).startswith("fd_")


@patch("backend.services.providers.thesportsdb.TheSportsDBProvider.fetch_fixtures")
@patch("backend.services.providers.openfootball.fetch_json_with_retry")
@patch("backend.services.providers.football_data.fetch_json_with_retry")
def test_empty_football_data_does_not_invent_ucl_openfootball_path(
    mock_fd_http, mock_of_http, mock_tsdb_fetch, db_session
):
    """Champions League must not be filled from an invented openfootball community path."""
    mock_fd_http.side_effect = _fd_http(matches=[])
    mock_of_http.side_effect = _of_http(matches=[OF_UCL_MATCH])
    mock_tsdb_fetch.return_value = []

    seed_competition(
        db=db_session,
        competition_name="UEFA Champions League",
        competition_type="Cup",
        format_engine="league_phase_knockout",
        season="2026/27",
        api_league_id=2,
        api_season=2026,
    )

    invented = db_session.query(Team).filter(Team.name == "Invented UCL Home").first()
    assert invented is None
    fixtures = db_session.query(Fixture).all()
    assert fixtures == []


@patch("backend.services.providers.highlightly.HighlightlyProvider.fetch_fixtures", return_value=[])
@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
@patch("backend.services.providers.openfootball.fetch_json_with_retry")
@patch("backend.services.providers.football_data.fetch_json_with_retry")
def test_empty_fd_and_openfootball_falls_back_to_thesportsdb_for_conference_league(
    mock_fd_http, mock_of_http, mock_tsdb_http, _mock_fa_fetch, db_session
):
    """Conference League has no FD free-plan or openfootball dataset; TheSportsDB is tertiary."""
    mock_fd_http.side_effect = _fd_http(matches=[])
    mock_of_http.side_effect = _of_http(matches=[])
    mock_tsdb_http.side_effect = _tsdb_http(events=[TSDB_UECL_EVENT])

    result = seed_competition(
        db=db_session,
        competition_name="UEFA Conference League",
        competition_type="Cup",
        format_engine="league_phase_knockout",
        season="2026/27",
        api_league_id=848,
        api_season=2026,
    )

    assert result.created == 1
    tourney = db_session.query(Tournament).join(Competition).filter(
        Competition.name == "UEFA Conference League"
    ).one()
    fixture = db_session.query(Fixture).filter_by(tournament_id=tourney.id).one()
    assert fixture.api_id == "tsdb_3000001"
    assert fixture.home_team.name == "Fiorentina"
    assert fixture.away_team.name == "Real Betis"
    assert fixture.watchability_score and fixture.watchability_score > 0
    assert get_external_id_for_competition(db_session, tourney.competition_id, "thesportsdb") == "5071"
    mock_of_http.assert_not_called()
    tsdb_urls = [call.args[0] for call in mock_tsdb_http.call_args_list]
    assert any("search_all_leagues.php" in url for url in tsdb_urls)
    season_url = next(url for url in tsdb_urls if "eventsseason.php" in url)
    assert "id=5071" in season_url
    assert "s=2026-2027" in season_url


@patch("backend.services.providers.openfootball.fetch_json_with_retry")
@patch("backend.services.providers.football_data.fetch_json_with_retry")
def test_engine_preflight_aborts_sparse_provider_payload(mock_fd_http, mock_of_http, db_session):
    """Pre-flight aborts when providers return far fewer fixtures than already stored."""
    comp = Competition(name="La Liga", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    now_utc = datetime.now(timezone.utc)
    for i in range(10):
        db_session.add(Fixture(
            tournament_id=tourney.id,
            api_id=f"exist_{i}",
            date_utc=now_utc,
            stage="Regular Season",
            status="Scheduled",
        ))
    db_session.commit()

    sparse_match = dict(FD_PL_MATCH)
    mock_fd_http.side_effect = _fd_http(matches=[sparse_match])
    mock_of_http.side_effect = _of_http(matches=[OF_PL_MATCH])

    engine = IngestionEngine()
    with pytest.raises(IngestionAborted):
        engine.seed_competition(
            db=db_session,
            competition_name="La Liga",
            season="2026/27",
            api_league_id=140,
        )

    existing_after = db_session.query(Fixture).filter_by(tournament_id=tourney.id).all()
    assert len(existing_after) == 10
    assert {f.api_id for f in existing_after} == {f"exist_{i}" for i in range(10)}


@patch("backend.services.providers.openfootball.fetch_json_with_retry")
@patch("backend.services.providers.football_data.fetch_json_with_retry")
def test_seeding_mapped_league_leaves_uncovered_competitions(mock_fd_http, mock_of_http, db_session):
    """Uncovered cups and Americas competitions stay in the database during a mapped seed."""
    now_utc = datetime.now(timezone.utc)
    for name, fmt, api_league_id in (
        ("FA Cup", "cup", 45),
        ("Major League Soccer", "league", 253),
        ("Copa Libertadores", "group_knockout", 13),
    ):
        comp = Competition(
            name=name,
            type="Cup" if fmt != "league" else "League",
            format_engine=fmt,
            api_league_id=api_league_id,
        )
        db_session.add(comp)
        db_session.flush()
        tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
        db_session.add(tourney)
        db_session.flush()
        db_session.add(Fixture(
            tournament_id=tourney.id,
            api_id=f"{name}-keep",
            date_utc=now_utc,
            stage="Regular Season",
            status="Scheduled",
        ))
    db_session.commit()

    mock_fd_http.side_effect = _fd_http(matches=[FD_PL_MATCH])
    mock_of_http.side_effect = _of_http(matches=[])

    seed_competition(
        db=db_session,
        competition_name="Premier League",
        competition_type="League",
        format_engine="league",
        season="2026/27",
        api_league_id=39,
        api_season=2026,
    )

    for name in ("FA Cup", "Major League Soccer", "Copa Libertadores"):
        leftover = db_session.query(Competition).filter_by(name=name).one()
        leftover_tourney = db_session.query(Tournament).filter_by(
            competition_id=leftover.id
        ).one()
        leftover_fixtures = db_session.query(Fixture).filter_by(
            tournament_id=leftover_tourney.id
        ).all()
        assert len(leftover_fixtures) == 1
        assert leftover_fixtures[0].api_id == f"{name}-keep"


@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
def test_thesportsdb_overlay_stamps_sparse_payload_without_abort(mock_tsdb_http, db_session):
    """Additive overlay INSERT/UPDATE even when TheSportsDB returns far fewer events."""
    mock_tsdb_http.side_effect = _tsdb_http(events=[TSDB_UECL_EVENT])
    comp = Competition(
        name="UEFA Conference League",
        type="Cup",
        format_engine="league_phase_knockout",
        api_league_id=848,
    )
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()
    now_utc = datetime.now(timezone.utc)
    for i in range(10):
        db_session.add(Fixture(
            tournament_id=tourney.id,
            api_id=f"tsdb_old_{i}",
            date_utc=now_utc,
            stage="League Phase",
            status="Scheduled",
        ))
    db_session.commit()

    result = IngestionEngine().overlay_from_thesportsdb(db_session, tourney, comp, 2026)
    assert result.created == 1
    assert db_session.query(Fixture).filter_by(tournament_id=tourney.id).count() == 11
    assert db_session.query(Fixture).filter_by(api_id="tsdb_3000001").one().home_team.name == "Fiorentina"
