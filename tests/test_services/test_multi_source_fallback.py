from unittest.mock import patch
from backend.services.seeder import seed_competition
from backend.database import Competition, Tournament, Fixture


@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
def test_seed_competition_primary_football_data(mock_fd_fetch, db_session):
    mock_fd_fetch.return_value = [
        {
            "id": 5001,
            "utcDate": "2026-08-22T14:00:00Z",
            "status": "SCHEDULED",
            "matchday": 1,
            "stage": "REGULAR_SEASON",
            "homeTeam": {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal"},
            "awayTeam": {"id": 66, "name": "Manchester United FC", "shortName": "Man United"}
        }
    ]

    seed_competition(
        db=db_session,
        competition_name="Premier League",
        competition_type="League",
        format_engine="league",
        season="2026/27",
        api_league_id=39,
        api_season=2026
    )

    comp = db_session.query(Competition).filter_by(name="Premier League").first()
    assert comp is not None

    tourney = db_session.query(Tournament).filter_by(competition_id=comp.id, season_name="2026/27").first()
    assert tourney is not None

    fixtures = db_session.query(Fixture).filter_by(tournament_id=tourney.id).all()
    assert len(fixtures) == 1
    assert fixtures[0].api_id == "fd_5001"
    assert fixtures[0].home_team.name == "Arsenal"
    assert fixtures[0].away_team.name == "Manchester United"


@patch("backend.services.providers.openfootball.OpenFootballProvider.fetch_fixtures")
@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
def test_seed_competition_failover_to_openfootball(mock_fd_fetch, mock_of_fetch, db_session):
    mock_fd_fetch.return_value = []
    mock_of_fetch.return_value = [
        {
            "round": "Matchday 1",
            "date": "2026-08-22",
            "time": "14:00",
            "team1": "Arsenal FC",
            "team2": "Chelsea FC",
        }
    ]

    seed_competition(
        db=db_session,
        competition_name="Premier League Failover",
        competition_type="League",
        format_engine="league",
        season="2026/27",
        api_league_id=39,
        api_season=2026
    )

    comp = db_session.query(Competition).filter_by(name="Premier League Failover").first()
    assert comp is not None

    tourney = db_session.query(Tournament).filter_by(competition_id=comp.id, season_name="2026/27").first()
    assert tourney is not None

    fixtures = db_session.query(Fixture).filter_by(tournament_id=tourney.id).all()
    assert len(fixtures) == 1
    assert not str(fixtures[0].api_id).startswith("fd_")
    assert fixtures[0].home_team.name in ("Arsenal FC", "Arsenal")
    assert fixtures[0].away_team.name in ("Chelsea FC", "Chelsea")


@patch("backend.services.providers.thesportsdb.TheSportsDBProvider.fetch_fixtures")
@patch("backend.services.providers.openfootball.OpenFootballProvider.fetch_fixtures")
@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
def test_seed_competition_failover_to_thesportsdb(mock_fd_fetch, mock_of_fetch, mock_tsdb_fetch, db_session):
    mock_fd_fetch.return_value = []
    mock_of_fetch.return_value = []
    mock_tsdb_fetch.return_value = [
        {
            "idEvent": "2272310",
            "idLeague": "4481",
            "strHomeTeam": "Roma",
            "strAwayTeam": "Athletic Club",
            "idHomeTeam": "133739",
            "idAwayTeam": "133704",
            "intRound": "1",
            "intHomeScore": None,
            "intAwayScore": None,
            "strTimestamp": "2026-09-17T19:00:00",
            "dateEvent": "2026-09-17",
            "strTime": "19:00:00",
            "strPostponed": "no",
            "strStatus": "Not Started",
        }
    ]

    seed_competition(
        db=db_session,
        competition_name="UEFA Europa League",
        competition_type="Cup",
        format_engine="league_phase_knockout",
        season="2026/27",
        api_league_id=3,
        api_season=2026
    )

    comp = db_session.query(Competition).filter_by(name="UEFA Europa League").first()
    assert comp is not None
    tourney = db_session.query(Tournament).filter_by(competition_id=comp.id, season_name="2026/27").first()
    fixtures = db_session.query(Fixture).filter_by(tournament_id=tourney.id).all()
    assert len(fixtures) == 1
    assert fixtures[0].api_id == "tsdb_2272310"
    assert fixtures[0].home_team.name == "Roma"
    assert fixtures[0].away_team.name == "Athletic Club"


@patch("backend.services.providers.thesportsdb.TheSportsDBProvider.fetch_fixtures")
@patch("backend.services.providers.openfootball.OpenFootballProvider.fetch_fixtures")
@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
def test_seed_competition_all_providers_empty_is_graceful(
    mock_fd_fetch, mock_of_fetch, mock_tsdb_fetch, db_session
):
    mock_fd_fetch.return_value = []
    mock_of_fetch.return_value = []
    mock_tsdb_fetch.return_value = []

    seed_competition(
        db=db_session,
        competition_name="Premier League Error Test",
        competition_type="League",
        format_engine="league",
        season="2026/27",
        api_league_id=39,
        api_season=2026
    )

    comp = db_session.query(Competition).filter_by(name="Premier League Error Test").first()
    assert comp is not None
    tourney = db_session.query(Tournament).filter_by(competition_id=comp.id).first()
    fixtures = db_session.query(Fixture).filter_by(tournament_id=tourney.id).all()
    assert fixtures == []
