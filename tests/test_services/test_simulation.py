import os
import random
from datetime import datetime
from backend.database import Team, Fixture, Competition, Tournament, TournamentTeam
from backend.services.simulation import (
    apply_simulated_score,
    run_monte_carlo_simulation, 
    simulate_bracket,
    simulate_group_stage,
    get_best_third_placed_teams,
    assign_third_placed_bipartite,
    get_probabilities,
    save_probabilities,
    results_path,
)


def _blank_side() -> dict:
    return {
        "played": 0,
        "won": 0,
        "drawn": 0,
        "lost": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_difference": 0,
        "points": 0,
    }


def test_simulated_away_win_does_not_invent_goals():
    home, away = _blank_side(), _blank_side()
    apply_simulated_score(home, away, 1, 2)
    assert (home["goals_for"], home["goals_against"]) == (1, 2)
    assert (away["goals_for"], away["goals_against"]) == (2, 1)
    assert home["goal_difference"] == home["goals_for"] - home["goals_against"]
    assert away["goal_difference"] == away["goals_for"] - away["goals_against"]
    assert away["points"] == 3
    assert home["lost"] == 1


def test_seeded_simulated_results_keep_goal_difference():
    """Home win, away win, and draw from one seeded sequence."""
    rng = random.Random(180)
    seen = set()
    home, away = _blank_side(), _blank_side()
    for _ in range(40):
        goals_home = rng.randint(0, 4)
        goals_away = rng.randint(0, 4)
        if goals_home > goals_away:
            seen.add("home")
        elif goals_home < goals_away:
            seen.add("away")
        else:
            seen.add("draw")
        apply_simulated_score(home, away, goals_home, goals_away)
        assert home["goal_difference"] == home["goals_for"] - home["goals_against"]
        assert away["goal_difference"] == away["goals_for"] - away["goals_against"]
    assert seen == {"home", "away", "draw"}

def test_simulation_service(db_session, monkeypatch, tmp_path):
    import backend.services.simulation as simulation

    monkeypatch.setattr(simulation, "_DATA_DIR", str(tmp_path))
    simulation._PROBABILITIES_CACHE.clear()
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
    
def test_get_probabilities_caches_and_parameterizes(monkeypatch, tmp_path):
    import backend.services.simulation as simulation

    monkeypatch.setattr(simulation, "_DATA_DIR", str(tmp_path))
    simulation._PROBABILITIES_CACHE.clear()

    payload = {"probabilities": [{"team": "TeamA", "group_exit_pct": 10.0}]}
    save_probabilities(2, payload)

    assert os.path.exists(os.path.join(tmp_path, "simulation_results_2.json"))
    first = get_probabilities(2)
    second = get_probabilities(2)
    assert first is second
    assert first["probabilities"][0]["team"] == "TeamA"

    save_probabilities(1, payload)
    assert os.path.exists(os.path.join(tmp_path, "simulation_results.json"))
    assert results_path(None) == results_path(1)
    wc = get_probabilities(None)
    assert wc["probabilities"][0]["group_exit_pct"] == 10.0

    assert get_probabilities(99) == {}
