from datetime import datetime
from backend.database import Team, Fixture, Competition, Tournament, TournamentTeam
from backend.services.tournament import calculate_standings, simulate_group_stage

def test_calculate_standings(db_session):
    comp = Competition(name="World Cup", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()

    # Setup teams in Group A
    t1 = Team(name="Germany", elo=1900, form_score=80.0, win_streak=1)
    t2 = Team(name="Scotland", elo=1650, form_score=50.0, win_streak=0)
    db_session.add_all([t1, t2])
    db_session.flush()

    tt1 = TournamentTeam(tournament_id=tourney.id, team_id=t1.id, group_name="A")
    tt2 = TournamentTeam(tournament_id=tourney.id, team_id=t2.id, group_name="A")
    db_session.add_all([tt1, tt2])
    db_session.flush()
    
    # Finished fixture
    f1 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        status="Finished",
        home_score=3,
        away_score=1,
        date_utc=datetime.fromisoformat("2026-06-11T20:00:00")
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
    comp = Competition(name="World Cup", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()

    # Setup teams
    t1 = Team(name="Germany", elo=1900)
    t2 = Team(name="Scotland", elo=1650)
    db_session.add_all([t1, t2])
    db_session.flush()

    tt1 = TournamentTeam(tournament_id=tourney.id, team_id=t1.id, group_name="A")
    tt2 = TournamentTeam(tournament_id=tourney.id, team_id=t2.id, group_name="A")
    db_session.add_all([tt1, tt2])
    db_session.flush()
    
    # One finished match
    f1 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        status="Finished",
        home_score=2,
        away_score=1,
        date_utc=datetime.fromisoformat("2026-06-11T20:00:00")
    )
    # One scheduled match (needs simulation)
    f2 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t2.id,
        away_team_id=t1.id,
        stage="Group Stage",
        status="Scheduled",
        date_utc=datetime.fromisoformat("2026-06-12T20:00:00")
    )
    db_session.add_all([f1, f2])
    db_session.commit()
    
    groups_data = simulate_group_stage(db_session)
    
    assert "A" in groups_data
    germany_stats = next(s for s in groups_data["A"] if s["name"] == "Germany")
    scotland_stats = next(s for s in groups_data["A"] if s["name"] == "Scotland")
    assert germany_stats["played"] == 2
    assert scotland_stats["played"] == 2

def test_calculate_points_needed_to_guarantee_top_2(db_session):
    from backend.services.tournament import calculate_points_needed_to_guarantee_top_2
    
    comp = Competition(name="World Cup 2", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()

    # Setup 4 teams in Group B
    t1 = Team(name="Argentina", elo=2000)
    t2 = Team(name="Mexico", elo=1750)
    t3 = Team(name="Poland", elo=1700)
    t4 = Team(name="Saudi Arabia", elo=1550)
    db_session.add_all([t1, t2, t3, t4])
    db_session.flush()

    db_session.add_all([
        TournamentTeam(tournament_id=tourney.id, team_id=t1.id, group_name="B"),
        TournamentTeam(tournament_id=tourney.id, team_id=t2.id, group_name="B"),
        TournamentTeam(tournament_id=tourney.id, team_id=t3.id, group_name="B"),
        TournamentTeam(tournament_id=tourney.id, team_id=t4.id, group_name="B"),
    ])
    db_session.flush()
    
    f_list = [
        Fixture(tournament_id=tourney.id, home_team_id=t1.id, away_team_id=t2.id, stage="Group Stage", status="Scheduled", date_utc=datetime.now()),
        Fixture(tournament_id=tourney.id, home_team_id=t3.id, away_team_id=t4.id, stage="Group Stage", status="Scheduled", date_utc=datetime.now()),
        Fixture(tournament_id=tourney.id, home_team_id=t1.id, away_team_id=t3.id, stage="Group Stage", status="Scheduled", date_utc=datetime.now()),
        Fixture(tournament_id=tourney.id, home_team_id=t2.id, away_team_id=t4.id, stage="Group Stage", status="Scheduled", date_utc=datetime.now()),
        Fixture(tournament_id=tourney.id, home_team_id=t1.id, away_team_id=t4.id, stage="Group Stage", status="Scheduled", date_utc=datetime.now()),
        Fixture(tournament_id=tourney.id, home_team_id=t2.id, away_team_id=t3.id, stage="Group Stage", status="Scheduled", date_utc=datetime.now()),
    ]
    db_session.add_all(f_list)
    db_session.commit()
    
    pts_needed = calculate_points_needed_to_guarantee_top_2(db_session, "Argentina", "B")
    assert pts_needed == 7

def test_get_all_third_placed_teams(db_session):
    from backend.services.tournament import get_all_third_placed_teams
    comp = Competition(name="World Cup 3", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()
    
    groups = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
    for idx, g in enumerate(groups):
        for j in range(3):
            t = Team(name=f"Team_{g}_{j}", elo=1500 + idx*10 + j)
            db_session.add(t)
            db_session.flush()
            tt = TournamentTeam(tournament_id=tourney.id, team_id=t.id, group_name=g)
            db_session.add(tt)
            db_session.flush()
            
    db_session.commit()
    
    thirds = get_all_third_placed_teams(db_session)
    assert len(thirds) == 12
    assert thirds[0]["group"] == "L"


def test_resolve_placeholder_name(db_session):
    from backend.services.tournament import resolve_placeholder_name
    
    comp = Competition(name="World Cup Placeholder Test", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()
    
    # 1. Setup teams
    t1 = Team(name="Spain", elo=2000)
    t2 = Team(name="Germany", elo=1900)
    db_session.add_all([t1, t2])
    db_session.flush()
    
    # 2. Add referenced fixture with resolved teams
    f_ref = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Round of 32",
        status="Scheduled",
        api_id="78",
        date_utc=datetime.now()
    )
    db_session.add(f_ref)
    
    # 3. Add referenced fixture with placeholder/unresolved teams
    f_ref_unresolved = Fixture(
        tournament_id=tourney.id,
        home_team_id=None,
        away_team_id=None,
        home_team_placeholder="Winner Group A",
        away_team_placeholder="Runner-up Group B",
        stage="Round of 32",
        status="Scheduled",
        api_id="80",
        date_utc=datetime.now()
    )
    db_session.add(f_ref_unresolved)
    db_session.commit()
    
    # Test case 1: Referenced match has resolved teams
    res1 = resolve_placeholder_name(db_session, "Winner Match 78", tourney.id)
    assert res1 == "Winner Match 78 (Spain or Germany)"
    
    # Test case 2: Referenced match has unresolved placeholder teams (simplified)
    res2 = resolve_placeholder_name(db_session, "Winner Match 80", tourney.id)
    assert res2 == "Winner Match 80 (Winner A or Runner-up B)"
    
    # Test case 3: Referenced match does not exist
    res3 = resolve_placeholder_name(db_session, "Winner Match 999", tourney.id)
    assert res3 == "Winner Match 999"
    
    # Test case 4: Normal group placeholder (does not reference a match)
    res4 = resolve_placeholder_name(db_session, "Winner Group A", tourney.id)
    assert res4 == "Winner Group A"


