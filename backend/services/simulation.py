import os
import json
import math
import random
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.database import Team, TournamentTeam, Fixture
import backend.crud.fixture as crud_fixture
import backend.crud.team as crud_team

def simulate_group_stage(db: Session) -> dict:
    teams = crud_team.get_all_teams(db)
    tts = db.query(TournamentTeam).all()
    team_group_map = {tt.team_id: tt.group_name for tt in tts}
    
    team_stats = {}
    for t in teams:
        team_stats[t.name] = {
            "name": t.name,
            "group_name": team_group_map.get(t.id),
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_difference": 0,
            "points": 0,
            "elo": t.elo
        }
        
    fixtures = crud_fixture.get_fixtures_by_stage(db, "Group Stage")
    for f in fixtures:
        h = team_stats.get(f.home_team.name)
        a = team_stats.get(f.away_team.name)
        if not h or not a:
            continue
            
        h["played"] += 1
        a["played"] += 1
        
        if f.status == "Finished":
            h_score = f.home_score
            a_score = f.away_score
            h["goals_for"] += h_score
            h["goals_against"] += a_score
            a["goals_for"] += a_score
            a["goals_against"] += h_score
            
            if h_score > a_score:
                h["won"] += 1
                h["points"] += 3
                a["lost"] += 1
            elif h_score < a_score:
                a["won"] += 1
                a["points"] += 3
                h["lost"] += 1
            else:
                h["drawn"] += 1
                h["points"] += 1
                a["drawn"] += 1
                a["points"] += 1
        else:
            diff = h["elo"] - a["elo"]
            p_home = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
            if p_home > 0.58:
                h["won"] += 1
                h["points"] += 3
                h["goals_for"] += 2
                a["goals_against"] += 2
                a["lost"] += 1
            elif p_home < 0.42:
                a["won"] += 1
                a["points"] += 3
                a["goals_for"] += 2
                h["goals_against"] += 2
                h["lost"] += 1
            else:
                h["drawn"] += 1
                h["points"] += 1
                h["goals_for"] += 1
                h["goals_against"] += 1
                a["drawn"] += 1
                a["points"] += 1
                a["goals_for"] += 1
                a["goals_against"] += 1
                
    for t_name, s in team_stats.items():
        s["goal_difference"] = s["goals_for"] - s["goals_against"]
        
    groups_data = {}
    for t_name, s in team_stats.items():
        g = s["group_name"]
        if g not in groups_data:
            groups_data[g] = []
        groups_data[g].append(s)
        
    for g in groups_data:
        groups_data[g].sort(key=lambda x: (x["points"], x["goal_difference"], x["goals_for"], x["elo"]), reverse=True)
        
    return groups_data


def get_best_third_placed_teams(groups_data: dict) -> list:
    third_placed = []
    for g in groups_data:
        if len(groups_data[g]) >= 3:
            third_placed.append(groups_data[g][2])
            
    third_placed.sort(key=lambda x: (x["points"], x["goal_difference"], x["goals_for"], x["elo"]), reverse=True)
    return third_placed[:8]


def assign_third_placed_bipartite(best_thirds: list) -> dict:
    winners = ["E", "I", "A", "L", "G", "D", "B", "K"]
    allowed = {
        "E": ["A", "B", "C", "D", "F"],
        "I": ["C", "D", "F", "G", "H"],
        "A": ["C", "E", "F", "H", "I"],
        "L": ["E", "H", "I", "J", "K"],
        "G": ["A", "E", "H", "I", "J"],
        "D": ["B", "E", "F", "I", "J"],
        "B": ["E", "F", "G", "I", "J"],
        "K": ["D", "E", "I", "J", "L"]
    }
    
    assignment = {}
    used = set()
    
    def backtrack(idx):
        if idx == len(winners):
            return True
        w = winners[idx]
        for t in best_thirds:
            t_name = t["name"]
            t_group = t["group_name"]
            if t_name not in used:
                if t_group in allowed[w] and t_group != w:
                    assignment[w] = t
                    used.add(t_name)
                    if backtrack(idx + 1):
                        return True
                    used.remove(t_name)
        return False
        
    if backtrack(0):
        return assignment
    else:
        fallback = {}
        for i, w in enumerate(winners):
            fallback[w] = best_thirds[i] if i < len(best_thirds) else best_thirds[0]
        return fallback


def simulate_bracket(db: Session, tournament_id: int = None) -> dict:
    file_path = os.path.join(os.path.dirname(__file__), "..", "data", "simulation_results.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
            
    # File not found or corrupt -> generate it
    return run_monte_carlo_simulation(db, tournament_id=tournament_id)


def run_monte_carlo_simulation(db: Session, num_simulations: int = 5000, tournament_id: int = None) -> dict:
    # Try importing numpy for faster poisson random number generation, fallback to pure python Knuth's algorithm
    try:
        import numpy as np
        def poisson_random(lam: float) -> int:
            return int(np.random.poisson(lam))
    except ImportError:
        def poisson_random(lam: float) -> int:
            L = math.exp(-lam)
            k = 0
            p = 1.0
            while p > L:
                k += 1
                p *= random.random()
            return k - 1

    # Load all teams and fixtures
    teams = db.query(Team).all()
    team_dict = {t.name: {"id": t.id, "elo": t.elo, "form_score": t.form_score} for t in teams}
    
    tts = db.query(TournamentTeam).all()
    team_group_map = {tt.team_id: tt.group_name for tt in tts}
    
    db_fixtures = db.query(Fixture).filter(Fixture.stage != "Group Stage").all()
    db_fixture_map = {f.api_id: f for f in db_fixtures if f.api_id}
    
    NEXT_ROUND_LOOKUP = {
        73: (90, "home"), 74: (89, "home"), 75: (90, "away"), 76: (91, "home"),
        77: (89, "away"), 78: (91, "away"), 79: (92, "home"), 80: (92, "away"),
        81: (94, "home"), 82: (94, "away"), 83: (93, "home"), 84: (93, "away"),
        85: (96, "home"), 86: (95, "home"), 87: (96, "away"), 88: (95, "away"),
        89: (97, "home"), 90: (97, "away"), 91: (99, "home"), 92: (99, "away"),
        93: (98, "home"), 94: (98, "away"), 95: (100, "home"), 96: (100, "away"),
        97: (101, "home"), 98: (101, "away"), 99: (102, "home"), 100: (102, "away"),
        101: (104, "home"), 102: (104, "away")
    }
    
    group_fixtures = db.query(Fixture).filter(Fixture.stage == "Group Stage").all()
    
    finished_fixtures = []
    scheduled_fixtures = []
    for f in group_fixtures:
        if not f.home_team or not f.away_team:
            continue
        if f.status == "Finished":
            finished_fixtures.append({
                "home": f.home_team.name,
                "away": f.away_team.name,
                "home_score": f.home_score,
                "away_score": f.away_score
            })
        else:
            scheduled_fixtures.append({
                "home": f.home_team.name,
                "away": f.away_team.name
            })
            
    # Exit stages: "group", "r32", "r16", "qf", "sf", "runner_up", "champion"
    exit_counts = {t.name: {
        "group": 0, "r32": 0, "r16": 0, "qf": 0, "sf": 0, "runner_up": 0, "champion": 0
    } for t in teams}
    
    all_brackets = []
    champion_counts = {}
    
    for sim in range(num_simulations):
        # 1. Initialize ELO and Group Standings
        elo_map = {name: info["elo"] for name, info in team_dict.items()}
        
        team_stats = {name: {
            "name": name,
            "group_name": team_group_map.get(info["id"]),
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_difference": 0,
            "points": 0,
            "elo": info["elo"]
        } for name, info in team_dict.items()}
        
        # 2. Add finished fixtures
        for f in finished_fixtures:
            h = team_stats.get(f["home"])
            a = team_stats.get(f["away"])
            if h and a:
                h["played"] += 1
                a["played"] += 1
                h["goals_for"] += f["home_score"]
                h["goals_against"] += f["away_score"]
                a["goals_for"] += f["away_score"]
                a["goals_against"] += f["home_score"]
                h["goal_difference"] = h["goals_for"] - h["goals_against"]
                a["goal_difference"] = a["goals_for"] - a["goals_against"]
                if f["home_score"] > f["away_score"]:
                    h["won"] += 1
                    h["points"] += 3
                    a["lost"] += 1
                elif f["home_score"] < f["away_score"]:
                    a["won"] += 1
                    a["points"] += 3
                    h["lost"] += 1
                else:
                    h["drawn"] += 1
                    h["points"] += 1
                    a["drawn"] += 1
                    a["points"] += 1
                    
        # 3. Simulate scheduled fixtures
        for f in scheduled_fixtures:
            h_name = f["home"]
            a_name = f["away"]
            h = team_stats.get(h_name)
            a = team_stats.get(a_name)
            if not h or not a:
                continue
                
            elo_h = elo_map.get(h_name, 1500)
            elo_a = elo_map.get(a_name, 1500)
            
            diff = elo_h - elo_a
            p_h = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
            
            lambda_h = 1.35 * (p_h / 0.46)
            lambda_a = 1.35 * ((1.0 - p_h) / 0.46)
            
            g_h = poisson_random(lambda_h)
            g_a = poisson_random(lambda_a)
            
            # ELO updates in memory
            expected_h = p_h
            actual_h = 1.0 if g_h > g_a else 0.5 if g_h == g_a else 0.0
            change = 30.0 * (actual_h - expected_h)
            elo_map[h_name] = elo_h + change
            elo_map[a_name] = elo_a - change
            
            h["played"] += 1
            a["played"] += 1
            h["goals_for"] += g_h
            h["goals_against"] += g_a
            a["goals_for"] += g_a
            a["goals_against"] += g_h
            h["goal_difference"] = h["goals_for"] - h["goals_against"]
            a["goal_difference"] = a["goals_for"] - a["goals_against"]
            
            if g_h > g_a:
                h["won"] += 1
                h["points"] += 3
                a["lost"] += 1
            elif g_h < g_a:
                a["won"] += 1
                a["points"] += 3
                a["goals_for"] += 2
                h["goals_against"] += 2
                h["lost"] += 1
            else:
                h["drawn"] += 1
                h["points"] += 1
                a["drawn"] += 1
                a["points"] += 1
                
        # 4. Process groups
        groups_data = {}
        for t_name, s in team_stats.items():
            g = s["group_name"]
            if g:
                groups_data.setdefault(g, []).append(s)
                
        for g in groups_data:
            groups_data[g].sort(key=lambda x: (x["points"], x["goal_difference"], x["goals_for"], x["elo"]), reverse=True)
            
        winners = {}
        runners_up = {}
        for g, teams_list in groups_data.items():
            if len(teams_list) >= 1:
                winners[g] = teams_list[0]
            if len(teams_list) >= 2:
                runners_up[g] = teams_list[1]
                
        best_thirds = get_best_third_placed_teams(groups_data)
        thirds_assignment = assign_third_placed_bipartite(best_thirds)
        
        # Mark all teams not in winners, runners_up, or thirds_assignment as group stage exit
        advancing_names = set()
        for g in winners:
            advancing_names.add(winners[g]["name"])
        for g in runners_up:
            advancing_names.add(runners_up[g]["name"])
        for g in thirds_assignment:
            advancing_names.add(thirds_assignment[g]["name"])
            
        for name in team_stats:
            if name not in advancing_names:
                exit_counts[name]["group"] += 1
                
        # 5. Knockout Simulator play match helper
        def get_teams_for_match(match_num, simulated_t1, simulated_t2):
            f = db_fixture_map.get(str(match_num))
            t1 = f.home_team.name if (f and f.home_team_id) else simulated_t1
            t2 = f.away_team.name if (f and f.away_team_id) else simulated_t2
            return t1, t2

        def play_knockout_match(simulated_t1, simulated_t2, stage, match_num):
            t1_name, t2_name = get_teams_for_match(match_num, simulated_t1, simulated_t2)
            f = db_fixture_map.get(str(match_num))
            
            if f and f.status == "Finished":
                winner = None
                if f.winner_id == f.home_team_id and f.home_team:
                    winner = f.home_team.name
                elif f.winner_id == f.away_team_id and f.away_team:
                    winner = f.away_team.name
                else:
                    # Look up next round match to see if the team is placed
                    next_lookup = NEXT_ROUND_LOOKUP.get(match_num)
                    if next_lookup:
                        next_match_num, slot = next_lookup
                        next_f = db_fixture_map.get(str(next_match_num))
                        if next_f:
                            next_team = next_f.home_team if slot == "home" else next_f.away_team
                            if next_team:
                                winner = next_team.name
                if not winner:
                    winner = t1_name
                return {
                    "team1": {"name": t1_name, "elo": int(elo_map.get(t1_name, 1500)), "group_name": team_group_map.get(team_dict[t1_name]["id"])},
                    "team2": {"name": t2_name, "elo": int(elo_map.get(t2_name, 1500)), "group_name": team_group_map.get(team_dict[t2_name]["id"])},
                    "winner": winner,
                    "home_score": f.home_score,
                    "away_score": f.away_score,
                    "has_extra_time": f.has_extra_time or False,
                    "has_penalties": f.has_penalties or False,
                    "home_penalty_score": f.home_penalty_score,
                    "away_penalty_score": f.away_penalty_score,
                    "stage": stage,
                    "match_num": match_num
                }

            elo1 = elo_map.get(t1_name, 1500)
            elo2 = elo_map.get(t2_name, 1500)
            diff = elo1 - elo2
            p_t1 = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
            
            lambda_1 = 1.35 * (p_t1 / 0.46)
            lambda_2 = 1.35 * ((1.0 - p_t1) / 0.46)
            
            goals1 = poisson_random(lambda_1)
            goals2 = poisson_random(lambda_2)
            
            # Elo update
            expected_1 = p_t1
            actual_1 = 1.0 if goals1 > goals2 else 0.5 if goals1 == goals2 else 0.0
            change = 30.0 * (actual_1 - expected_1)
            elo_map[t1_name] = elo1 + change
            elo_map[t2_name] = elo2 - change
            
            has_extra_time = False
            has_penalties = False
            p1_score = None
            p2_score = None
            
            if goals1 == goals2:
                has_extra_time = True
                et1 = poisson_random(0.35)
                et2 = poisson_random(0.35)
                goals1 += et1
                goals2 += et2
                
                if goals1 == goals2:
                    has_penalties = True
                    p1 = 0
                    p2 = 0
                    while p1 == p2:
                        p1 = random.randint(3, 5)
                        p2 = random.randint(3, 5)
                        if p1 == p2:
                            p1 += random.randint(0, 3)
                            p2 += random.randint(0, 3)
                    p1_score = p1
                    p2_score = p2
                    winner = t1_name if p1 > p2 else t2_name
                else:
                    winner = t1_name if goals1 > goals2 else t2_name
            else:
                winner = t1_name if goals1 > goals2 else t2_name
                
            return {
                "team1": {"name": t1_name, "elo": int(elo1), "group_name": team_group_map.get(team_dict[t1_name]["id"])},
                "team2": {"name": t2_name, "elo": int(elo2), "group_name": team_group_map.get(team_dict[t2_name]["id"])},
                "winner": winner,
                "home_score": goals1,
                "away_score": goals2,
                "has_extra_time": has_extra_time,
                "has_penalties": has_penalties,
                "home_penalty_score": p1_score,
                "away_penalty_score": p2_score,
                "stage": stage,
                "match_num": match_num
            }

        # Play matches
        m_73 = play_knockout_match(runners_up["A"]["name"], runners_up["B"]["name"], "Round of 32", 73)
        m_74 = play_knockout_match(winners["E"]["name"], thirds_assignment["E"]["name"], "Round of 32", 74)
        m_75 = play_knockout_match(winners["F"]["name"], runners_up["C"]["name"], "Round of 32", 75)
        m_76 = play_knockout_match(winners["C"]["name"], runners_up["F"]["name"], "Round of 32", 76)
        m_77 = play_knockout_match(winners["I"]["name"], thirds_assignment["I"]["name"], "Round of 32", 77)
        m_78 = play_knockout_match(runners_up["E"]["name"], runners_up["I"]["name"], "Round of 32", 78)
        m_79 = play_knockout_match(winners["A"]["name"], thirds_assignment["A"]["name"], "Round of 32", 79)
        m_80 = play_knockout_match(winners["L"]["name"], thirds_assignment["L"]["name"], "Round of 32", 80)
        m_81 = play_knockout_match(winners["D"]["name"], thirds_assignment["D"]["name"], "Round of 32", 81)
        m_82 = play_knockout_match(winners["G"]["name"], thirds_assignment["G"]["name"], "Round of 32", 82)
        m_83 = play_knockout_match(runners_up["K"]["name"], runners_up["L"]["name"], "Round of 32", 83)
        m_84 = play_knockout_match(winners["H"]["name"], runners_up["J"]["name"], "Round of 32", 84)
        m_85 = play_knockout_match(winners["B"]["name"], thirds_assignment["B"]["name"], "Round of 32", 85)
        m_86 = play_knockout_match(winners["J"]["name"], runners_up["H"]["name"], "Round of 32", 86)
        m_87 = play_knockout_match(winners["K"]["name"], thirds_assignment["K"]["name"], "Round of 32", 87)
        m_88 = play_knockout_match(runners_up["D"]["name"], runners_up["G"]["name"], "Round of 32", 88)
        
        # Round of 32 in layout order
        r32_matches = [
            m_74, m_77, m_73, m_75,
            m_83, m_84, m_81, m_82,
            m_76, m_78, m_79, m_80,
            m_86, m_88, m_85, m_87
        ]
        
        # Exits in R32
        for m in r32_matches:
            loser = m["team1"]["name"] if m["winner"] == m["team2"]["name"] else m["team2"]["name"]
            exit_counts[loser]["r32"] += 1
            
        r16_matches = []
        r16_matches.append(play_knockout_match(m_74["winner"], m_77["winner"], "Round of 16", 89))
        r16_matches.append(play_knockout_match(m_73["winner"], m_75["winner"], "Round of 16", 90))
        r16_matches.append(play_knockout_match(m_83["winner"], m_84["winner"], "Round of 16", 93))
        r16_matches.append(play_knockout_match(m_81["winner"], m_82["winner"], "Round of 16", 94))
        r16_matches.append(play_knockout_match(m_76["winner"], m_78["winner"], "Round of 16", 91))
        r16_matches.append(play_knockout_match(m_79["winner"], m_80["winner"], "Round of 16", 92))
        r16_matches.append(play_knockout_match(m_86["winner"], m_88["winner"], "Round of 16", 95))
        r16_matches.append(play_knockout_match(m_85["winner"], m_87["winner"], "Round of 16", 96))
        
        # Exits in R16
        for m in r16_matches:
            loser = m["team1"]["name"] if m["winner"] == m["team2"]["name"] else m["team2"]["name"]
            exit_counts[loser]["r16"] += 1
            
        qf_matches = []
        qf_matches.append(play_knockout_match(r16_matches[0]["winner"], r16_matches[1]["winner"], "Quarter-final", 97))
        qf_matches.append(play_knockout_match(r16_matches[2]["winner"], r16_matches[3]["winner"], "Quarter-final", 98))
        qf_matches.append(play_knockout_match(r16_matches[4]["winner"], r16_matches[5]["winner"], "Quarter-final", 99))
        qf_matches.append(play_knockout_match(r16_matches[6]["winner"], r16_matches[7]["winner"], "Quarter-final", 100))
        
        # Exits in QF
        for m in qf_matches:
            loser = m["team1"]["name"] if m["winner"] == m["team2"]["name"] else m["team2"]["name"]
            exit_counts[loser]["qf"] += 1
            
        sf_matches = []
        sf_matches.append(play_knockout_match(qf_matches[0]["winner"], qf_matches[1]["winner"], "Semi-final", 101))
        sf_matches.append(play_knockout_match(qf_matches[2]["winner"], qf_matches[3]["winner"], "Semi-final", 102))
        
        sf1_loser = sf_matches[0]["team1"]["name"] if sf_matches[0]["winner"] == sf_matches[0]["team2"]["name"] else sf_matches[0]["team2"]["name"]
        sf2_loser = sf_matches[1]["team1"]["name"] if sf_matches[1]["winner"] == sf_matches[1]["team2"]["name"] else sf_matches[1]["team2"]["name"]
        
        third_match = play_knockout_match(sf1_loser, sf2_loser, "Third-place play-off", 103)
        
        # Exits in SF
        exit_counts[sf1_loser]["sf"] += 1
        exit_counts[sf2_loser]["sf"] += 1
        
        final_match = play_knockout_match(sf_matches[0]["winner"], sf_matches[1]["winner"], "Final", 104)
        
        exit_counts[final_match["team1"]["name"] if final_match["winner"] == final_match["team2"]["name"] else final_match["team2"]["name"]]["runner_up"] += 1
        exit_counts[final_match["winner"]]["champion"] += 1
        
        champion = final_match["winner"]
        champion_counts[champion] = champion_counts.get(champion, 0) + 1
        
        bracket = {
            "r32": r32_matches,
            "r16": r16_matches,
            "qf": qf_matches,
            "sf": sf_matches,
            "third": third_match,
            "final": final_match,
            "champion": champion
        }
        all_brackets.append(bracket)
        
    # Aggregate probabilities
    probabilities = []
    for name, info in team_dict.items():
        counts = exit_counts[name]
        probabilities.append({
            "team": name,
            "elo": info["elo"],
            "group_name": team_group_map.get(info["id"]),
            "group_exit_pct": round(counts["group"] / num_simulations * 100, 2),
            "r32_exit_pct": round(counts["r32"] / num_simulations * 100, 2),
            "r16_exit_pct": round(counts["r16"] / num_simulations * 100, 2),
            "qf_exit_pct": round(counts["qf"] / num_simulations * 100, 2),
            "sf_exit_pct": round(counts["sf"] / num_simulations * 100, 2),
            "runner_up_pct": round(counts["runner_up"] / num_simulations * 100, 2),
            "champion_pct": round(counts["champion"] / num_simulations * 100, 2)
        })
        
    # Sort probabilities by champion_pct, then runner_up_pct, then sf_exit_pct, etc.
    probabilities.sort(key=lambda x: (x["champion_pct"], x["runner_up_pct"], x["sf_exit_pct"], x["qf_exit_pct"], x["elo"]), reverse=True)
    
    # Pick the representative bracket
    most_common_champion = max(champion_counts, key=champion_counts.get) if champion_counts else "Unknown"
    
    representative_bracket = None
    for b in all_brackets:
        if b["champion"] == most_common_champion:
            representative_bracket = b
            break
            
    if not representative_bracket and all_brackets:
        representative_bracket = all_brackets[0]
        
    if representative_bracket:
        def enrich_match_details(m, f):
            m["date"] = f.date_utc.isoformat()
            
            # Resolve actual team details if set in the database
            if f.home_team:
                m["team1"]["name"] = f.home_team.name
                m["team1"]["elo"] = f.home_team.elo
                m["team1"]["group_name"] = team_group_map.get(f.home_team.id)
            if f.away_team:
                m["team2"]["name"] = f.away_team.name
                m["team2"]["elo"] = f.away_team.elo
                m["team2"]["group_name"] = team_group_map.get(f.away_team.id)
                
            if f.status == "Finished":
                m["matchup_status"] = "official"
                m["home_score"] = f.home_score
                m["away_score"] = f.away_score
                m["winner"] = f.home_team.name if f.winner_id == f.home_team_id else (f.away_team.name if f.winner_id == f.away_team_id else m["winner"])
                m["team1"]["is_predicted"] = False
                m["team2"]["is_predicted"] = False
                m["has_extra_time"] = f.has_extra_time or False
                m["has_penalties"] = f.has_penalties or False
                m["home_penalty_score"] = f.home_penalty_score
                m["away_penalty_score"] = f.away_penalty_score
            elif f.home_team_id is not None and f.away_team_id is not None:
                m["matchup_status"] = "scheduled"
                m["team1"]["is_predicted"] = False
                m["team2"]["is_predicted"] = False
            else:
                m["matchup_status"] = "predicted"
                m["team1"]["is_predicted"] = (f.home_team_id is None)
                m["team2"]["is_predicted"] = (f.away_team_id is None)
 
        # Build map for fast lookup of db fixtures by api_id
        fixture_lookup = {f.api_id: f for f in db_fixtures if f.api_id}

        # Enrich R32, R16, QF, SF matches
        for round_name in ["r32", "r16", "qf", "sf"]:
            for m in representative_bracket.get(round_name, []):
                match_num = m.get("match_num")
                f = fixture_lookup.get(str(match_num))
                if f:
                    enrich_match_details(m, f)
                    
        # Enrich Third-place match
        m_third = representative_bracket.get("third")
        if m_third:
            f = fixture_lookup.get("103")
            if f:
                enrich_match_details(m_third, f)
                
        # Enrich Final match
    result = {
        "bracket": representative_bracket,
        "probabilities": probabilities,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "num_simulations": num_simulations
    }
    
    # Save to file if default World Cup
    if tournament_id is None or tournament_id == 1:
        file_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(file_dir, exist_ok=True)
        file_path = os.path.join(file_dir, "simulation_results.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
            
    return result


def get_tournament_bracket_tree(db: Session, tournament_id: int) -> dict:
    """
    Builds a dynamic knockout bracket tree for cup tournaments directly from DB fixtures.
    """
    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney:
        return {"bracket": {}, "probabilities": []}
        
    fixtures = db.query(Fixture).filter(Fixture.tournament_id == tournament_id).all()
    stages = {}
    
    for f in fixtures:
        if f.stage in ("Group Stage", "Regular Season", "League Phase"):
            continue
            
        stage_key = f.stage.lower().replace(" ", "_").replace("-", "_")
        stages.setdefault(stage_key, []).append({
            "match_num": f.id,
            "date": f.date_utc.isoformat() if f.date_utc else None,
            "matchup_status": "official" if f.status == "Finished" else ("scheduled" if f.home_team_id else "predicted"),
            "stage": f.stage,
            "team1": {
                "name": f.home_team.name if f.home_team else (f.home_team_placeholder or "TBD"),
                "elo": f.home_team.elo if f.home_team else 1500,
                "logo_url": f.home_team.badge_url if f.home_team else "/static/badges/default.png",
                "is_predicted": f.home_team_id is None
            },
            "team2": {
                "name": f.away_team.name if f.away_team else (f.away_team_placeholder or "TBD"),
                "elo": f.away_team.elo if f.away_team else 1500,
                "logo_url": f.away_team.badge_url if f.away_team else "/static/badges/default.png",
                "is_predicted": f.away_team_id is None
            },
            "home_score": f.home_score,
            "away_score": f.away_score,
            "winner": f.home_team.name if (f.winner_id and f.home_team and f.winner_id == f.home_team_id) else (f.away_team.name if (f.winner_id and f.away_team and f.winner_id == f.away_team_id) else None)
        })
        
    return {
        "bracket": stages,
        "probabilities": [],
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "num_simulations": 1
    }
