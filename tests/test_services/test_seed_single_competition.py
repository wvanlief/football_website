import pytest
from unittest.mock import patch, MagicMock

from backend.database import Competition, Tournament, Fixture
from backend.services.seeder import seed_single_competition, seed_european_cups


def test_seed_single_competition_european_cup(db_session):
    # Seeding single European cup (e.g. Champions League, league_id=2)
    result = seed_single_competition(db_session, league_id=2)
    assert result["status"] == "success"
    assert result["league_id"] == 2
    assert "details" in result
    
    # Check that UEFA Champions League was created in DB
    ucl_comp = db_session.query(Competition).filter(Competition.name == "UEFA Champions League").first()
    assert ucl_comp is not None
    assert ucl_comp.api_league_id == 2
    
    # Check that UEFA Europa League was NOT seeded when filtering by league_id=2
    uel_comp = db_session.query(Competition).filter(Competition.name == "UEFA Europa League").first()
    assert uel_comp is None


@patch("backend.services.seeder.fetch_and_seed_teams")
@patch("backend.services.seeder.seed_competition")
def test_seed_single_competition_default_league(mock_seed_comp, mock_fetch_teams, db_session):
    # Setup mock return
    mock_upsert = MagicMock()
    mock_upsert.created = 380
    mock_upsert.updated = 0
    mock_upsert.odds_added = 380
    mock_seed_comp.return_value = mock_upsert

    result = seed_single_competition(db_session, league_id=39)
    assert result["status"] == "success"
    assert result["competition"] == "Premier League"
    assert result["league_id"] == 39
    assert result["fixtures_created"] == 380
    mock_seed_comp.assert_called_once()


@patch("backend.services.seeder.fetch_and_seed_teams")
@patch("backend.services.seeder.seed_competition")
def test_seed_single_competition_custom_db_competition(mock_seed_comp, mock_fetch_teams, db_session):
    # Insert custom competition in DB
    custom_comp = Competition(
        name="Scottish Cup",
        type="Cup",
        format_engine="cup",
        api_league_id=5555
    )
    db_session.add(custom_comp)
    db_session.commit()

    mock_upsert = MagicMock()
    mock_upsert.created = 60
    mock_upsert.updated = 5
    mock_upsert.odds_added = 60
    mock_seed_comp.return_value = mock_upsert

    result = seed_single_competition(db_session, league_id=5555)
    assert result["status"] == "success"
    assert result["competition"] == "Scottish Cup"
    assert result["league_id"] == 5555
    assert result["fixtures_created"] == 60


def test_seed_single_competition_invalid_id(db_session):
    with pytest.raises(ValueError) as excinfo:
        seed_single_competition(db_session, league_id=9999999)
    assert "9999999" in str(excinfo.value)
