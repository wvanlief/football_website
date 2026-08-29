from unittest.mock import patch, MagicMock
from backend.services.seeder import seed_competition
from backend.database import Competition, Tournament, Fixture, Team

@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
def test_seed_competition_primary_football_data(mock_fd_fetch, db_session):
    # Mock Football-Data.org returning 1 fixture
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
    assert fixtures[0].away_team.name == "Man United"


@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
@patch("backend.services.providers.api_football.call_football_api")
def test_seed_competition_failover_to_api_football(mock_api_football, mock_fd_fetch, db_session):
    # Primary Football-Data.org returns 0 fixtures (e.g. unmapped or offline)
    mock_fd_fetch.return_value = []

    # Secondary API-Football returns a fixture
    mock_api_football.return_value = {
        "response": [
            {
                "fixture": {"id": 99001, "date": "2026-08-22T14:00:00Z", "status": {"short": "NS"}},
                "teams": {
                    "home": {"id": 33, "name": "Arsenal"},
                    "away": {"id": 42, "name": "Chelsea"}
                },
                "goals": {"home": None, "away": None},
                "league": {"round": "Regular Season - 1"}
            }
        ]
    }

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
    assert fixtures[0].api_id == "99001"
    assert fixtures[0].home_team.name == "Arsenal"
    assert fixtures[0].away_team.name == "Chelsea"


@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
@patch("backend.services.providers.api_football.call_football_api")
def test_seed_competition_api_football_suspended_graceful_handling(mock_api_football, mock_fd_fetch, db_session):
    # Both APIs return 0 / error payloads
    mock_fd_fetch.return_value = []
    mock_api_football.return_value = {
        "errors": {"access": "Your account is suspended"}
    }

    # Should log error gracefully and not crash
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
