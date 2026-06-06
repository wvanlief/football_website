from datetime import datetime
from backend.database import Fixture, Competition, Tournament, Team
from backend.crud.fixture import get_recommended_fixtures, get_fixtures_by_stage

def test_get_recommended_fixtures(db_session):
    comp = Competition(name="World Cup", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()
    
    t1 = Team(name="Germany")
    t2 = Team(name="Scotland")
    t3 = Team(name="Hungary")
    t4 = Team(name="Switzerland")
    db_session.add_all([t1, t2, t3, t4])
    db_session.flush()

    f1 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        watchability_score=80.0,
        date_utc=datetime.fromisoformat("2026-06-11T20:00:00")
    )
    f2 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t3.id,
        away_team_id=t4.id,
        stage="Group Stage",
        watchability_score=65.0,
        date_utc=datetime.fromisoformat("2026-06-11T20:00:00")
    )
    db_session.add_all([f1, f2])
    db_session.commit()
    
    recommended = get_recommended_fixtures(db_session, min_score=75.0)
    assert len(recommended) == 1
    assert recommended[0].home_team.name == "Germany"

def test_get_fixtures_by_stage(db_session):
    comp = Competition(name="World Cup", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()
    
    t1 = Team(name="Germany")
    t2 = Team(name="Scotland")
    t3 = Team(name="Winner A")
    t4 = Team(name="Runner-up B")
    db_session.add_all([t1, t2, t3, t4])
    db_session.flush()

    f1 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        date_utc=datetime.fromisoformat("2026-06-11T20:00:00")
    )
    f2 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t3.id,
        away_team_id=t4.id,
        stage="Round of 16",
        date_utc=datetime.fromisoformat("2026-06-20T20:00:00")
    )
    db_session.add_all([f1, f2])
    db_session.commit()
    
    group_stage_fixtures = get_fixtures_by_stage(db_session, "Group Stage")
    assert len(group_stage_fixtures) == 1
    assert group_stage_fixtures[0].home_team.name == "Germany"
