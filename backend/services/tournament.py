import json
from datetime import datetime, date
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session, joinedload

from backend.database import Fixture, Team, Player, PlayerContract, TournamentTeam
import backend.crud.fixture as crud_fixture
import backend.crud.team as crud_team
import backend.crud.player as crud_player

def get_timezone(tz_str: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_str)
    except Exception:
        return ZoneInfo("UTC")

def enrich_fixture(f: Fixture, db: Session, target_tz: ZoneInfo, team_players_map: dict = None, team_group_map: dict = None) -> dict:
    dt = f.date_utc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    dt_tz = dt.astimezone(target_tz)
    
    home_team = f.home_team
    away_team = f.away_team
    
    # Get group letter
    group_letter = None
    if team_group_map is not None:
        group_letter = team_group_map.get((f.tournament_id, f.home_team_id))
    else:
        tt = db.query(TournamentTeam).filter(
            TournamentTeam.tournament_id == f.tournament_id,
            TournamentTeam.team_id == f.home_team_id
        ).first()
        if tt:
            group_letter = tt.group_name
            
    # Get players
    if team_players_map is not None:
        home_players = team_players_map.get(f.home_team_id, [])
        away_players = team_players_map.get(f.away_team_id, [])
    else:
        home_players = crud_player.get_players_by_team(db, home_team.name) if home_team else []
        away_players = crud_player.get_players_by_team(db, away_team.name) if away_team else []
        
    reasons = []
    try:
        reasons = json.loads(f.reasons_json) if f.reasons_json else []
    except Exception:
        pass
        
    display_stage = f"Group {group_letter}" if f.stage == "Group Stage" and group_letter else f.stage
    latest_odds = f.latest_odds
    
    return {
        "id": f.id,
        "home_team": {
            "name": home_team.name if home_team else "Unknown",
            "elo": home_team.elo if home_team else 1500,
            "form_score": home_team.form_score if home_team else 50.0,
            "win_streak": home_team.win_streak if home_team else 0,
            "players": [{"name": p.name, "position": p.position, "form": p.form_score} for p in home_players]
        },
        "away_team": {
            "name": away_team.name if away_team else "Unknown",
            "elo": away_team.elo if away_team else 1500,
            "form_score": away_team.form_score if away_team else 50.0,
            "win_streak": away_team.win_streak if away_team else 0,
            "players": [{"name": p.name, "position": p.position, "form": p.form_score} for p in away_players]
        },
        "date": f.date_utc.isoformat(),
        "formatted_time": dt_tz.strftime("%H:%M"),
        "formatted_date": dt_tz.strftime("%B %d, %Y"),
        "formatted_date_short": dt_tz.strftime("%b %d"),
        "stage": display_stage,
        "group_name": group_letter,
        "status": f.status,
        "score": f"{f.home_score} - {f.away_score}" if f.status == "Finished" else None,
        "odds": {
            "home": latest_odds.odds_home,
            "draw": latest_odds.odds_draw,
            "away": latest_odds.odds_away
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
    
    # Preload maps to avoid N+1 queries
    contracts = db.query(PlayerContract).options(joinedload(PlayerContract.player)).filter(
        PlayerContract.type == "Country",
        PlayerContract.is_active == True
    ).all()
    team_players_map = {}
    for c in contracts:
        team_players_map.setdefault(c.team_id, []).append(c.player)
        
    tts = db.query(TournamentTeam).all()
    team_group_map = {}
    for tt in tts:
        team_group_map[(tt.tournament_id, tt.team_id)] = tt.group_name
        
    today_fixtures = []
    tomorrow_fixtures = []
    week_fixtures = []
    
    today_date = date(2026, 6, 11)
    tomorrow_date = date(2026, 6, 12)
    max_date = date(2026, 6, 19)
    
    for f in fixtures:
        dt = f.date_utc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        dt_tz = dt.astimezone(target_tz)
        match_date = dt_tz.date()
        
        fixture_data = enrich_fixture(f, db, target_tz, team_players_map, team_group_map)
        
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
    
    # Preload maps to avoid N+1 queries
    contracts = db.query(PlayerContract).options(joinedload(PlayerContract.player)).filter(
        PlayerContract.type == "Country",
        PlayerContract.is_active == True
    ).all()
    team_players_map = {}
    for c in contracts:
        team_players_map.setdefault(c.team_id, []).append(c.player)
        
    tts = db.query(TournamentTeam).all()
    team_group_map = {}
    for tt in tts:
        team_group_map[(tt.tournament_id, tt.team_id)] = tt.group_name
        
    return [enrich_fixture(f, db, target_tz, team_players_map, team_group_map) for f in fixtures]

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
        h = standings_map.get(f.home_team.name)
        a = standings_map.get(f.away_team.name)
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
        
    tt = db.query(TournamentTeam).filter(TournamentTeam.team_id == team.id).first()
    group_name = tt.group_name if tt else None
    
    group_standings = calculate_standings(db, group_name) if group_name else []
    rank = 1
    for index, standing in enumerate(group_standings):
        if standing["name"] == country_name:
            rank = index + 1
            break
            
    players = crud_player.get_top_players_by_team(db, country_name, limit=3)
    players_data = [{"name": p.name, "position": p.position, "form": p.form_score} for p in players]
    
    finished_fixtures = crud_fixture.get_finished_fixtures_for_country(db, country_name)
    finished_fixtures.sort(key=lambda x: x.date_utc, reverse=True)
    
    form_results = []
    for f in finished_fixtures:
        if f.home_team.name == country_name:
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
    future_fixtures.sort(key=lambda x: x.date_utc)
    
    # Preload maps to avoid N+1 queries
    contracts = db.query(PlayerContract).options(joinedload(PlayerContract.player)).filter(
        PlayerContract.type == "Country",
        PlayerContract.is_active == True
    ).all()
    team_players_map = {}
    for c in contracts:
        team_players_map.setdefault(c.team_id, []).append(c.player)
        
    tts = db.query(TournamentTeam).all()
    team_group_map = {}
    for t_t in tts:
        team_group_map[(t_t.tournament_id, t_t.team_id)] = t_t.group_name

    future_matches_data = [enrich_fixture(f, db, target_tz, team_players_map, team_group_map) for f in future_fixtures]
        
    return {
        "name": team.name,
        "elo": team.elo,
        "group_name": group_name,
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
    
    # Preload maps to avoid N+1 queries
    contracts = db.query(PlayerContract).options(joinedload(PlayerContract.player)).filter(
        PlayerContract.type == "Country",
        PlayerContract.is_active == True
    ).all()
    team_players_map = {}
    for c in contracts:
        team_players_map.setdefault(c.team_id, []).append(c.player)
        
    tts = db.query(TournamentTeam).all()
    team_group_map = {}
    for tt in tts:
        team_group_map[(tt.tournament_id, tt.team_id)] = tt.group_name

    fixtures_data = [enrich_fixture(f, db, target_tz, team_players_map, team_group_map) for f in fixtures]
        
    return {
        "group_letter": group_letter,
        "standings": standings,
        "fixtures": fixtures_data
    }

def simulate_group_stage(db: Session) -> dict:
    from backend.database import TournamentTeam
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

def simulate_bracket(db: Session) -> dict:
    from backend.database import TournamentTeam
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
    
    def play_match(t1_name, t2_name, stage="Knockout Stage"):
        t1 = crud_team.get_team_by_name(db, t1_name)
        t2 = crud_team.get_team_by_name(db, t2_name)
        t1_elo = t1.elo if t1 else 1500
        t2_elo = t2.elo if t2 else 1500
        
        t1_tt = db.query(TournamentTeam).filter(TournamentTeam.team_id == t1.id).first() if t1 else None
        t2_tt = db.query(TournamentTeam).filter(TournamentTeam.team_id == t2.id).first() if t2 else None
        
        import random
        diff = t1_elo - t2_elo
        p_t1 = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
        
        t1_goals = random.choices([0, 1, 2, 3, 4], weights=[0.3, 0.4, 0.2, 0.08, 0.02])[0]
        if p_t1 > 0.6:
            t1_goals += 1
        elif p_t1 < 0.4:
            t1_goals = max(0, t1_goals - 1)
            
        t2_goals = random.choices([0, 1, 2, 3], weights=[0.4, 0.4, 0.15, 0.05])[0]
        if p_t1 < 0.4:
            t2_goals += 1
        elif p_t1 > 0.6:
            t2_goals = max(0, t2_goals - 1)
            
        has_extra_time = False
        has_penalties = False
        home_penalty_score = None
        away_penalty_score = None
        
        if t1_goals == t2_goals:
            has_extra_time = True
            et1 = random.choices([0, 1, 2], weights=[0.7, 0.25, 0.05])[0]
            et2 = random.choices([0, 1, 2], weights=[0.7, 0.25, 0.05])[0]
            t1_goals += et1
            t2_goals += et2
            
            if t1_goals == t2_goals:
                has_penalties = True
                p1 = 0
                p2 = 0
                while p1 == p2:
                    p1 = random.randint(3, 5)
                    p2 = random.randint(3, 5)
                    if p1 == p2:
                        p1 += random.randint(0, 3)
                        p2 += random.randint(0, 3)
                home_penalty_score = p1
                away_penalty_score = p2
                winner = t1_name if p1 > p2 else t2_name
            else:
                winner = t1_name if t1_goals > t2_goals else t2_name
        else:
            winner = t1_name if t1_goals > t2_goals else t2_name
            
        return {
            "team1": {"name": t1_name, "elo": t1_elo, "group_name": t1_tt.group_name if t1_tt else None},
            "team2": {"name": t2_name, "elo": t2_elo, "group_name": t2_tt.group_name if t2_tt else None},
            "winner": winner,
            "home_score": t1_goals,
            "away_score": t2_goals,
            "has_extra_time": has_extra_time,
            "has_penalties": has_penalties,
            "home_penalty_score": home_penalty_score,
            "away_penalty_score": away_penalty_score,
            "stage": stage
        }

    r32_matches = []
    
    m1 = play_match(runners_up["A"]["name"], runners_up["B"]["name"], "Round of 32")
    m2 = play_match(winners["C"]["name"], runners_up["F"]["name"], "Round of 32")
    m3 = play_match(winners["E"]["name"], thirds_assignment["E"]["name"], "Round of 32")
    m4 = play_match(winners["F"]["name"], runners_up["C"]["name"], "Round of 32")
    m5 = play_match(runners_up["E"]["name"], runners_up["I"]["name"], "Round of 32")
    m6 = play_match(winners["I"]["name"], thirds_assignment["I"]["name"], "Round of 32")
    m7 = play_match(winners["A"]["name"], thirds_assignment["A"]["name"], "Round of 32")
    m8 = play_match(winners["L"]["name"], thirds_assignment["L"]["name"], "Round of 32")
    m9 = play_match(winners["G"]["name"], thirds_assignment["G"]["name"], "Round of 32")
    m10 = play_match(winners["D"]["name"], thirds_assignment["D"]["name"], "Round of 32")
    m11 = play_match(winners["H"]["name"], runners_up["J"]["name"], "Round of 32")
    m12 = play_match(runners_up["K"]["name"], runners_up["L"]["name"], "Round of 32")
    m13 = play_match(winners["B"]["name"], thirds_assignment["B"]["name"], "Round of 32")
    m14 = play_match(runners_up["D"]["name"], runners_up["G"]["name"], "Round of 32")
    m15 = play_match(winners["J"]["name"], runners_up["H"]["name"], "Round of 32")
    m16 = play_match(winners["K"]["name"], thirds_assignment["K"]["name"], "Round of 32")
    
    r32_matches = [m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12, m13, m14, m15, m16]
    
    r16_matches = []
    for i in range(8):
        t1_name = r32_matches[i*2]["winner"]
        t2_name = r32_matches[i*2+1]["winner"]
        r16_matches.append(play_match(t1_name, t2_name, "Round of 16"))
        
    qf_matches = []
    for i in range(4):
        t1_name = r16_matches[i*2]["winner"]
        t2_name = r16_matches[i*2+1]["winner"]
        qf_matches.append(play_match(t1_name, t2_name, "Quarter-final"))
        
    sf_matches = []
    for i in range(2):
        t1_name = qf_matches[i*2]["winner"]
        t2_name = qf_matches[i*2+1]["winner"]
        sf_matches.append(play_match(t1_name, t2_name, "Semi-final"))
        
    sf1_loser = sf_matches[0]["team1"]["name"] if sf_matches[0]["winner"] == sf_matches[0]["team2"]["name"] else sf_matches[0]["team2"]["name"]
    sf2_loser = sf_matches[1]["team1"]["name"] if sf_matches[1]["winner"] == sf_matches[1]["team2"]["name"] else sf_matches[1]["team2"]["name"]
    third_match = play_match(sf1_loser, sf2_loser, "Third-place play-off")
    
    final_match = play_match(sf_matches[0]["winner"], sf_matches[1]["winner"], "Final")
    
    return {
        "r32": r32_matches,
        "r16": r16_matches,
        "qf": qf_matches,
        "sf": sf_matches,
        "third": third_match,
        "final": final_match,
        "champion": final_match["winner"]
    }
