import os
import json
from datetime import datetime
from backend.database import Team, Fixture, Competition, Tournament, TournamentTeam
from backend.services.tournament import run_monte_carlo_simulation, simulate_bracket

def test_monte_carlo_simulation(db_session):
    comp = Competition(name="World Cup", type="International")
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
            # Give teams slightly different Elo ratings
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
    
    # Run the Monte Carlo simulation (using a small number of simulations for speed in tests)
    result = run_monte_carlo_simulation(db_session, num_simulations=10)
    
    assert "bracket" in result
    assert "probabilities" in result
    assert "last_updated" in result
    assert "num_simulations" in result
    assert result["num_simulations"] == 10
    
    # Check probabilities structure
    assert len(result["probabilities"]) == 48
    prob_team_0 = next(p for p in result["probabilities"] if p["team"] == teams_list[0].name)
    assert prob_team_0["elo"] == teams_list[0].elo
    
    # Check bracket structure
    bracket = result["bracket"]
    assert len(bracket["r32"]) == 16
    assert len(bracket["r16"]) == 8
    assert len(bracket["qf"]) == 4
    assert len(bracket["sf"]) == 2
    assert "third" in bracket
    assert "final" in bracket
    assert "champion" in bracket
    
    # Verify file was written
    file_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend", "data", "simulation_results.json")
    assert os.path.exists(file_path)
    
    # Clean up file after test
    try:
        os.remove(file_path)
    except Exception:
        pass
