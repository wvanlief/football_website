from backend.database import Team, Fixture
from backend.services.tournament import calculate_standings, simulate_group_stage, simulate_bracket

def test_calculate_standings(db_session):
    # Setup teams in Group A
    t1 = Team(name="Germany", group_name="A", elo=1900, form_score=80.0, win_streak=1)
    t2 = Team(name="Scotland", group_name="A", elo=1650, form_score=50.0, win_streak=0)
    db_session.add_all([t1, t2])
    
    # Finished fixture
    f1 = Fixture(
        home_team_name="Germany",
        away_team_name="Scotland",
        stage="Group Stage",
        status="Finished",
        home_score=3,
        away_score=1,
        date="2026-06-11T20:00:00"
    )
    db_session.add(f1)
    db_session.commit()
    
    # Run standings calculation
    standings = calculate_standings(db_session, "A")
    
    # Asserts
    assert len(standings) == 2
    assert standings[0]["name"] == "Germany"
    assert standings[0]["played"] == 1
    assert standings[0]["won"] == 1
    assert standings[0]["goals_for"] == 3
    assert standings[0]["goals_against"] == 1
    assert standings[0]["goal_difference"] == 2
    assert standings[0]["points"] == 3
    
    assert standings[1]["name"] == "Scotland"
    assert standings[1]["played"] == 1
    assert standings[1]["lost"] == 1
    assert standings[1]["goals_for"] == 1
    assert standings[1]["goals_against"] == 3
    assert standings[1]["goal_difference"] == -2
    assert standings[1]["points"] == 0

def test_simulate_group_stage_finished_vs_unplayed(db_session):
    # Setup teams
    t1 = Team(name="Germany", group_name="A", elo=1900)
    t2 = Team(name="Scotland", group_name="A", elo=1650)
    db_session.add_all([t1, t2])
    
    # One finished match
    f1 = Fixture(
        home_team_name="Germany",
        away_team_name="Scotland",
        stage="Group Stage",
        status="Finished",
        home_score=2,
        away_score=1,
        date="2026-06-11T20:00:00"
    )
    # One scheduled match (needs simulation)
    f2 = Fixture(
        home_team_name="Scotland",
        away_team_name="Germany",
        stage="Group Stage",
        status="Scheduled",
        date="2026-06-12T20:00:00"
    )
    db_session.add_all([f1, f2])
    db_session.commit()
    
    groups_data = simulate_group_stage(db_session)
    
    assert "A" in groups_data
    # Germany ELO > Scotland ELO, Germany will likely win the simulated match as well,
    # but let's just make sure both matches were computed.
    germany_stats = next(s for s in groups_data["A"] if s["name"] == "Germany")
    scotland_stats = next(s for s in groups_data["A"] if s["name"] == "Scotland")
    assert germany_stats["played"] == 2
    assert scotland_stats["played"] == 2
