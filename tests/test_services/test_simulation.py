import os
from datetime import datetime
from backend.database import Team, Fixture, Competition, Tournament, TournamentTeam
from backend.services.simulation import (
    run_monte_carlo_simulation, 
    simulate_bracket,
    simulate_group_stage,
    get_best_third_placed_teams,
    assign_third_placed_bipartite
)

def test_simulation_service(db_session):
    comp = Competition(name="Simulation Cup", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()

    # Setup 48 teams (A to L groups) to ensure the tournament simulation runs successfully
    groups = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
    teams_list = []
    
    for i, g in enumerate(groups):
        for j in range(4):
            team_name = f"Team_{g}_{j}"
            t = Team(name=team_name, elo=1500 + (i * 10) + j, form_score=50.0)
            db_session.add(t)
            db_session.flush()
            teams_list.append(t)
            
            tt = TournamentTeam(tournament_id=tourney.id, team_id=t.id, group_name=g)
            db_session.add(tt)
            db_session.flush()
            
    # Add one finished group stage fixture
    f1 = Fixture(
        tournament_id=tourney.id,
        home_team_id=teams_list[0].id,
        away_team_id=teams_list[1].id,
        stage="Group Stage",
        status="Finished",
        home_score=3,
        away_score=0,
        date_utc=datetime.now()
    )
    # Add a scheduled group stage fixture
    f2 = Fixture(
        tournament_id=tourney.id,
        home_team_id=teams_list[2].id,
        away_team_id=teams_list[3].id,
        stage="Group Stage",
        status="Scheduled",
        date_utc=datetime.now()
    )
    db_session.add_all([f1, f2])
    db_session.commit()
    
    # Test simulate_group_stage
    groups_data = simulate_group_stage(db_session)
    assert len(groups_data) == 12
    assert "A" in groups_data
    
    # Test get_best_third_placed_teams
    best_thirds = get_best_third_placed_teams(groups_data)
    assert len(best_thirds) <= 8
    
    # Test assign_third_placed_bipartite
    thirds_assignment = assign_third_placed_bipartite(best_thirds)
    assert isinstance(thirds_assignment, dict)
    
    # Test run_monte_carlo_simulation
    result = run_monte_carlo_simulation(db_session, num_simulations=10)
    assert "bracket" in result
    assert "probabilities" in result
    assert result["num_simulations"] == 10
    
    # Test simulate_bracket
    bracket_res = simulate_bracket(db_session)
    assert "bracket" in bracket_res
    
    # Clean up file after test
    file_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend", "data", "simulation_results.json")
    try:
        os.remove(file_path)
    except Exception:
        pass
