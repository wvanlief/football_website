import itertools
from typing import Optional, Any
from sqlalchemy.orm import Session

from backend.database import Team, TournamentTeam, Fixture, Tournament, Competition
import backend.crud.fixture as crud_fixture
import backend.crud.team as crud_team

def recalculate_tournament_team_standings(db: Session, tournament_id: int):
    """
    Recalculates and updates the TournamentTeam standings cache for all teams in a tournament
    based on finished fixtures.
    """
    tt_records = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == tournament_id).all()
    if not tt_records:
        return
        
    tt_map = {tt.team_id: tt for tt in tt_records}
    
    # Reset columns
    for tt in tt_records:
        tt.points = 0
        tt.wins = 0
        tt.draws = 0
        tt.losses = 0
        tt.goals_for = 0
        tt.goals_against = 0
        
    finished_fixtures = db.query(Fixture).filter(
        Fixture.tournament_id == tournament_id,
        Fixture.status == "Finished",
        Fixture.home_team_id.isnot(None),
        Fixture.away_team_id.isnot(None)
    ).all()
    
    for f in finished_fixtures:
        home_tt = tt_map.get(f.home_team_id)
        away_tt = tt_map.get(f.away_team_id)
        if not home_tt or not away_tt:
            continue
            
        home_score = f.home_score if f.home_score is not None else 0
        away_score = f.away_score if f.away_score is not None else 0
        
        home_tt.goals_for += home_score
        home_tt.goals_against += away_score
        away_tt.goals_for += away_score
        away_tt.goals_against += home_score
        
        is_league = home_tt.tournament.competition.format_engine == "league"
        is_group_stage = f.stage == "Group Stage"
        
        if is_league or is_group_stage:
            home_tt.wins += 1 if home_score > away_score else 0
            home_tt.losses += 1 if home_score < away_score else 0
            home_tt.draws += 1 if home_score == away_score else 0
            home_tt.points += 3 if home_score > away_score else (1 if home_score == away_score else 0)
            
            away_tt.wins += 1 if away_score > home_score else 0
            away_tt.losses += 1 if away_score < home_score else 0
            away_tt.draws += 1 if away_score == home_score else 0
            away_tt.points += 3 if away_score > home_score else (1 if away_score == home_score else 0)
    db.flush()


def recalculate_team_streaks(db: Session):
    """
    Recalculates win/draw/loss streaks for all teams based on finished fixtures in chronological order.
    """
    teams = db.query(Team).all()
    for team in teams:
        team.win_streak = 0
        team.draw_streak = 0
        team.loss_streak = 0
    db.flush()

    finished_fixtures = db.query(Fixture).filter(Fixture.status == "Finished").order_by(Fixture.date_utc.asc()).all()
    for f in finished_fixtures:
        home_team = f.home_team
        away_team = f.away_team
        if not home_team or not away_team:
            continue
            
        if f.home_score > f.away_score:
            home_team.win_streak += 1
            home_team.draw_streak = 0
            home_team.loss_streak = 0
            
            away_team.loss_streak += 1
            away_team.win_streak = 0
            away_team.draw_streak = 0
        elif f.home_score < f.away_score:
            away_team.win_streak += 1
            away_team.draw_streak = 0
            away_team.loss_streak = 0
            
            home_team.loss_streak += 1
            home_team.win_streak = 0
            home_team.draw_streak = 0
        else: # Draw
            home_team.draw_streak += 1
            home_team.win_streak = 0
            home_team.loss_streak = 0
            
            away_team.draw_streak += 1
            away_team.win_streak = 0
            away_team.loss_streak = 0
    db.flush()


def recalculate_standings(db: Session, tournament_id: int):
    """
    Consolidated entry point to recalculate tournament standings cache and refresh streaks.
    """
    recalculate_tournament_team_standings(db, tournament_id)
    recalculate_team_streaks(db)


def calculate_standings(db: Session, group_letter: str, tournament_id: int = None) -> list:
    if tournament_id is None:
        active_tourney = db.query(Tournament).filter(Tournament.status == "Active").first()
        tournament_id = active_tourney.id if active_tourney else None
        
    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    comp = tourney.competition if tourney else None
    
    stage = "Group Stage"
    if comp:
        if comp.format_engine == "league" or comp.type == "League":
            stage = "Regular Season"
        elif comp.format_engine == "league_phase_knockout":
            stage = "League Phase"
        
    if group_letter and group_letter.lower() == "standings":
        teams = crud_team.get_all_teams(db, tournament_id=tournament_id)
    else:
        teams = crud_team.get_teams_by_group(db, group_letter, tournament_id=tournament_id)
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
            "elo": t.elo,
            "logo_url": t.badge_url
        })
        
    team_names = [t.name for t in teams]
    finished_fixtures = crud_fixture.get_finished_group_stage_fixtures_for_teams(db, team_names, tournament_id=tournament_id, stage=stage)
    
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


def calculate_points_needed_to_guarantee_top_2(db: Session, team_name: str, group_letter: str, tournament_id: int = None) -> int:
    if tournament_id is None:
        active_tourney = db.query(Tournament).filter(Tournament.status == "Active").first()
        tournament_id = active_tourney.id if active_tourney else None
        
    # Get all teams in this group
    tts = db.query(TournamentTeam).filter(
        TournamentTeam.group_name == group_letter,
        TournamentTeam.tournament_id == tournament_id
    ).all()
    group_team_ids = [tt.team_id for tt in tts]
    
    if not group_team_ids:
        return 0
        
    teams = db.query(Team).filter(Team.id.in_(group_team_ids)).all()
    team_name_map = {t.id: t.name for t in teams}
    team_names = list(team_name_map.values())
    
    if team_name not in team_names:
        return 0
        
    # Get all Group Stage fixtures for these teams
    fixtures = crud_fixture.get_fixtures_for_group(db, team_names, tournament_id=tournament_id)
    
    # Classify fixtures
    finished_fixtures = []
    scheduled_fixtures = []
    
    for f in fixtures:
        h_name = f.home_team.name
        a_name = f.away_team.name
        if h_name not in team_names or a_name not in team_names:
            continue
            
        if f.status == "Finished":
            finished_fixtures.append({
                "home": h_name,
                "away": a_name,
                "home_score": f.home_score,
                "away_score": f.away_score
            })
        else:
            scheduled_fixtures.append({
                "home": h_name,
                "away": a_name
            })
            
    # Calculate starting points for each team
    current_points = {name: 0 for name in team_names}
    for f in finished_fixtures:
        h = f["home"]
        a = f["away"]
        h_score = f["home_score"]
        a_score = f["away_score"]
        if h_score > a_score:
            current_points[h] += 3
        elif h_score < a_score:
            current_points[a] += 3
        else:
            current_points[h] += 1
            current_points[a] += 1
            
    # If no scheduled fixtures left, points needed is 0
    num_remaining = len(scheduled_fixtures)
    if num_remaining == 0:
        return 0
        
    # Check how many matches the target team has left
    target_remaining = sum(1 for f in scheduled_fixtures if team_name in (f["home"], f["away"]))
    if target_remaining == 0:
        return 0
        
    # The max possible points target team can reach
    max_possible_points = current_points[team_name] + 3 * target_remaining
    
    safe_points = None
    
    for P in range(current_points[team_name], max_possible_points + 1):
        is_safe = True
        has_valid_scenario = False
        
        # Enumerate all 3^num_remaining outcomes
        for match_results in itertools.product([(3, 0), (1, 1), (0, 3)], repeat=num_remaining):
            pts = current_points.copy()
            for idx, (p_home, p_away) in enumerate(match_results):
                f = scheduled_fixtures[idx]
                pts[f["home"]] += p_home
                pts[f["away"]] += p_away
                
            if pts[team_name] < P:
                continue
                
            has_valid_scenario = True
            
            # Determine rank under worst-case tiebreaker
            # Sort teams. In case of ties, put team_name below others
            sorted_teams = sorted(
                team_names,
                key=lambda t: (pts[t], 0 if t == team_name else 1),
                reverse=True
            )
            
            rank = sorted_teams.index(team_name) + 1
            if rank > 2:
                is_safe = False
                break
                
        if is_safe and has_valid_scenario:
            safe_points = P
            break
            
    if safe_points is not None:
        return max(0, safe_points - current_points[team_name])
    else:
        return 3 * target_remaining
