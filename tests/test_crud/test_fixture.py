from backend.database import Fixture
from backend.crud.fixture import get_recommended_fixtures, get_fixtures_by_stage

def test_get_recommended_fixtures(db_session):
    f1 = Fixture(
        home_team_name="Germany",
        away_team_name="Scotland",
        stage="Group Stage",
        watchability_score=80.0,
        date="2026-06-11T20:00:00"
    )
    f2 = Fixture(
        home_team_name="Hungary",
        away_team_name="Switzerland",
        stage="Group Stage",
        watchability_score=65.0,
        date="2026-06-11T20:00:00"
    )
    db_session.add_all([f1, f2])
    db_session.commit()
    
    recommended = get_recommended_fixtures(db_session, min_score=75.0)
    assert len(recommended) == 1
    assert recommended[0].home_team_name == "Germany"

def test_get_fixtures_by_stage(db_session):
    f1 = Fixture(
        home_team_name="Germany",
        away_team_name="Scotland",
        stage="Group Stage",
        date="2026-06-11T20:00:00"
    )
    f2 = Fixture(
        home_team_name="Winner A",
        away_team_name="Runner-up B",
        stage="Round of 16",
        date="2026-06-20T20:00:00"
    )
    db_session.add_all([f1, f2])
    db_session.commit()
    
    group_stage_fixtures = get_fixtures_by_stage(db_session, "Group Stage")
    assert len(group_stage_fixtures) == 1
    assert group_stage_fixtures[0].home_team_name == "Germany"
