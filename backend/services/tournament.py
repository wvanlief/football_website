import json
from datetime import datetime, date
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from backend.database import Fixture, Team, Player
import backend.crud.fixture as crud_fixture
import backend.crud.team as crud_team
import backend.crud.player as crud_player

def get_timezone(tz_str: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_str)
    except Exception:
        return ZoneInfo("UTC")

def enrich_fixture(f: Fixture, db: Session, target_tz: ZoneInfo) -> dict:
    dt = datetime.fromisoformat(f.date)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    dt_tz = dt.astimezone(target_tz)
    
    home_team = crud_team.get_team_by_name(db, f.home_team_name)
    away_team = crud_team.get_team_by_name(db, f.away_team_name)
    
    home_players = crud_player.get_players_by_team(db, f.home_team_name)
    away_players = crud_player.get_players_by_team(db, f.away_team_name)
    
    reasons = []
    try:
        reasons = json.loads(f.reasons_json) if f.reasons_json else []
    except Exception:
        pass
        
    group_letter = home_team.group_name if home_team else None
    display_stage = f"Group {group_letter}" if f.stage == "Group Stage" and group_letter else f.stage
    
    return {
        "id": f.id,
        "home_team": {
            "name": f.home_team_name,
            "elo": home_team.elo if home_team else 1500,
            "form_score": home_team.form_score if home_team else 50.0,
            "win_streak": home_team.win_streak if home_team else 0,
            "players": [{"name": p.name, "position": p.position, "form": p.form_score} for p in home_players]
        },
        "away_team": {
            "name": f.away_team_name,
            "elo": away_team.elo if away_team else 1500,
            "form_score": away_team.form_score if away_team else 50.0,
            "win_streak": away_team.win_streak if away_team else 0,
            "players": [{"name": p.name, "position": p.position, "form": p.form_score} for p in away_players]
        },
        "date": f.date,
        "formatted_time": dt_tz.strftime("%H:%M"),
        "formatted_date": dt_tz.strftime("%B %d, %Y"),
        "formatted_date_short": dt_tz.strftime("%b %d"),
        "stage": display_stage,
        "group_name": group_letter,
        "status": f.status,
        "score": f"{f.home_score} - {f.away_score}" if f.status == "Finished" else None,
        "odds": {
            "home": f.odds_home,
            "draw": f.odds_draw,
            "away": f.odds_away
        },
        "watchability": {
            "overall": f.watchability_score,
            "competitiveness": f.competitiveness_score,
            "odds": f.odds_score,
            "form": f.form_score,
            "narrative": f.narrative_score
        },
        "reasons": reasons
    }

def get_grouped_fixtures(db: Session, tz_str: str) -> dict:
    target_tz = get_timezone(tz_str)
    fixtures = crud_fixture.get_all_fixtures(db)
    
    today_fixtures = []
    tomorrow_fixtures = []
    week_fixtures = []
    
    today_date = date(2026, 6, 11)
    tomorrow_date = date(2026, 6, 12)
    max_date = date(2026, 6, 19)
    
    for f in fixtures:
        dt = datetime.fromisoformat(f.date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        dt_tz = dt.astimezone(target_tz)
        match_date = dt_tz.date()
        
        fixture_data = enrich_fixture(f, db, target_tz)
        
        if match_date == today_date:
            today_fixtures.append(fixture_data)
        elif match_date == tomorrow_date:
            tomorrow_fixtures.append(fixture_data)
        elif tomorrow_date < match_date <= max_date:
            week_fixtures.append(fixture_data)
            
    today_fixtures.sort(key=lambda x: x["watchability"]["overall"], reverse=True)
    tomorrow_fixtures.sort(key=lambda x: x["watchability"]["overall"], reverse=True)
    week_fixtures.sort(key=lambda x: x["watchability"]["overall"], reverse=True)
    
    return {
        "today": today_fixtures,
        "tomorrow": tomorrow_fixtures,
        "this_week": week_fixtures[:5]
    }

def get_recommended_fixtures(db: Session, tz_str: str, min_score: float = 75.0) -> list:
    target_tz = get_timezone(tz_str)
    fixtures = crud_fixture.get_recommended_fixtures(db, min_score)
    return [enrich_fixture(f, db, target_tz) for f in fixtures]

def calculate_standings(db: Session, group_letter: str) -> list:
    teams = crud_team.get_teams_by_group(db, group_letter)
    standings = []
    for t in teams:
        standings.append({
            "name": t.name,
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_difference": 0,
            "points": 0,
            "elo": t.elo
        })
        
    team_names = [t.name for t in teams]
    finished_fixtures = crud_fixture.get_finished_group_stage_fixtures_for_teams(db, team_names)
    
    standings_map = {s["name"]: s for s in standings}
    
    for f in finished_fixtures:
        h = standings_map.get(f.home_team_name)
        a = standings_map.get(f.away_team_name)
        if not h or not a:
            continue
            
        h["played"] += 1
        a["played"] += 1
        h["goals_for"] += f.home_score
        h["goals_against"] += f.away_score
        a["goals_for"] += f.away_score
        a["goals_against"] += f.home_score
        
        if f.home_score > f.away_score:
            h["won"] += 1
            h["points"] += 3
            a["lost"] += 1
        elif f.home_score < f.away_score:
            a["won"] += 1
            a["points"] += 3
            h["lost"] += 1
        else:
            h["drawn"] += 1
            h["points"] += 1
            a["drawn"] += 1
            a["points"] += 1
            
    for s in standings:
        s["goal_difference"] = s["goals_for"] - s["goals_against"]
        
    standings.sort(key=lambda x: (x["points"], x["goal_difference"], x["goals_for"], x["elo"]), reverse=True)
    return standings

def get_country_details(db: Session, country_name: str, tz_str: str) -> dict:
    target_tz = get_timezone(tz_str)
    team = crud_team.get_team_by_name(db, country_name)
    if not team:
        return None
        
    group_standings = calculate_standings(db, team.group_name)
    rank = 1
    for index, standing in enumerate(group_standings):
        if standing["name"] == country_name:
            rank = index + 1
            break
            
    players = crud_player.get_top_players_by_team(db, country_name, limit=3)
    players_data = [{"name": p.name, "position": p.position, "form": p.form_score} for p in players]
    
    finished_fixtures = crud_fixture.get_finished_fixtures_for_country(db, country_name)
    finished_fixtures.sort(key=lambda x: x.date, reverse=True)
    
    form_results = []
    for f in finished_fixtures:
        if f.home_team_name == country_name:
            if f.home_score > f.away_score:
                form_results.append("W")
            elif f.home_score < f.away_score:
                form_results.append("L")
            else:
                form_results.append("D")
        else:
            if f.away_score > f.home_score:
                form_results.append("W")
            elif f.away_score < f.home_score:
                form_results.append("L")
            else:
                form_results.append("D")
                
    if len(form_results) < 5:
        remaining = 5 - len(form_results)
        elo = team.elo
        if elo >= 2000:
            pad = ["W", "W", "W", "D", "W"]
        elif elo >= 1850:
            pad = ["W", "D", "W", "L", "W"]
        elif elo >= 1700:
            pad = ["D", "L", "W", "D", "W"]
        else:
            pad = ["L", "L", "D", "W", "L"]
        form_results.extend(pad[:remaining])
        
    form_results = form_results[:5]
    form_results.reverse()
    
    future_fixtures = crud_fixture.get_future_fixtures_for_country(db, country_name)
    future_fixtures.sort(key=lambda x: x.date)
    
    future_matches_data = [enrich_fixture(f, db, target_tz) for f in future_fixtures]
        
    return {
        "name": team.name,
        "elo": team.elo,
        "group_name": team.group_name,
        "group_rank": rank,
        "form": form_results,
        "players": players_data,
        "future_matches": future_matches_data
    }

def get_group_details(db: Session, group_letter: str, tz_str: str) -> dict:
    target_tz = get_timezone(tz_str)
    teams = crud_team.get_teams_by_group(db, group_letter)
    if not teams:
        return None
        
    standings = calculate_standings(db, group_letter)
    team_names = [t.name for t in teams]
    
    fixtures = crud_fixture.get_fixtures_for_group(db, team_names)
    fixtures_data = [enrich_fixture(f, db, target_tz) for f in fixtures]
        
    return {
        "group_letter": group_letter,
        "standings": standings,
        "fixtures": fixtures_data
    }

def simulate_group_stage(db: Session) -> dict:
    teams = crud_team.get_all_teams(db)
    team_stats = {}
    for t in teams:
        team_stats[t.name] = {
            "name": t.name,
            "group_name": t.group_name,
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
        h = team_stats.get(f.home_team_name)
        a = team_stats.get(f.away_team_name)
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

def simulate_bracket(db: Session) -> dict:
    groups_data = simulate_group_stage(db)
    
    winners = {}
    runners_up = {}
    for g, teams in groups_data.items():
        if len(teams) >= 1:
            winners[g] = teams[0]
        if len(teams) >= 2:
            runners_up[g] = teams[1]
            
    best_thirds = get_best_third_placed_teams(groups_data)
    thirds_assignment = assign_third_placed_bipartite(best_thirds)
    
    def play_match(t1_name, t2_name):
        t1 = crud_team.get_team_by_name(db, t1_name)
        t2 = crud_team.get_team_by_name(db, t2_name)
        t1_elo = t1.elo if t1 else 1500
        t2_elo = t2.elo if t2 else 1500
        
        if t1_elo > t2_elo:
            winner = t1_name
        elif t1_elo < t2_elo:
            winner = t2_name
        else:
            t1_form = t1.form_score if t1 else 50.0
            t2_form = t2.form_score if t2 else 50.0
            if t1_form >= t2_form:
                winner = t1_name
            else:
                winner = t2_name
                
        return {
            "team1": {"name": t1_name, "elo": t1_elo, "group_name": t1.group_name if t1 else None},
            "team2": {"name": t2_name, "elo": t2_elo, "group_name": t2.group_name if t2 else None},
            "winner": winner
        }

    r32_matches = []
    
    m1 = play_match(runners_up["A"]["name"], runners_up["B"]["name"])
    m2 = play_match(winners["C"]["name"], runners_up["F"]["name"])
    m3 = play_match(winners["E"]["name"], thirds_assignment["E"]["name"])
    m4 = play_match(winners["F"]["name"], runners_up["C"]["name"])
    m5 = play_match(runners_up["E"]["name"], runners_up["I"]["name"])
    m6 = play_match(winners["I"]["name"], thirds_assignment["I"]["name"])
    m7 = play_match(winners["A"]["name"], thirds_assignment["A"]["name"])
    m8 = play_match(winners["L"]["name"], thirds_assignment["L"]["name"])
    m9 = play_match(winners["G"]["name"], thirds_assignment["G"]["name"])
    m10 = play_match(winners["D"]["name"], thirds_assignment["D"]["name"])
    m11 = play_match(winners["H"]["name"], runners_up["J"]["name"])
    m12 = play_match(runners_up["K"]["name"], runners_up["L"]["name"])
    m13 = play_match(winners["B"]["name"], thirds_assignment["B"]["name"])
    m14 = play_match(runners_up["D"]["name"], runners_up["G"]["name"])
    m15 = play_match(winners["J"]["name"], runners_up["H"]["name"])
    m16 = play_match(winners["K"]["name"], thirds_assignment["K"]["name"])
    
    r32_matches = [m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12, m13, m14, m15, m16]
    
    r16_matches = []
    for i in range(8):
        t1_name = r32_matches[i*2]["winner"]
        t2_name = r32_matches[i*2+1]["winner"]
        r16_matches.append(play_match(t1_name, t2_name))
        
    qf_matches = []
    for i in range(4):
        t1_name = r16_matches[i*2]["winner"]
        t2_name = r16_matches[i*2+1]["winner"]
        qf_matches.append(play_match(t1_name, t2_name))
        
    sf_matches = []
    for i in range(2):
        t1_name = qf_matches[i*2]["winner"]
        t2_name = qf_matches[i*2+1]["winner"]
        sf_matches.append(play_match(t1_name, t2_name))
        
    sf1_loser = sf_matches[0]["team1"]["name"] if sf_matches[0]["winner"] == sf_matches[0]["team2"]["name"] else sf_matches[0]["team2"]["name"]
    sf2_loser = sf_matches[1]["team1"]["name"] if sf_matches[1]["winner"] == sf_matches[1]["team2"]["name"] else sf_matches[1]["team2"]["name"]
    third_match = play_match(sf1_loser, sf2_loser)
    
    final_match = play_match(sf_matches[0]["winner"], sf_matches[1]["winner"])
    
    return {
        "r32": r32_matches,
        "r16": r16_matches,
        "qf": qf_matches,
        "sf": sf_matches,
        "third": third_match,
        "final": final_match,
        "champion": final_match["winner"]
    }
