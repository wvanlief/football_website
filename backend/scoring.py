import os
import json
from sqlalchemy.orm import Session
from backend.database import Team, Player, Fixture

_sim_data_cache = None
_sim_data_mtime = 0

def get_simulation_probabilities():
    global _sim_data_cache, _sim_data_mtime
    file_path = os.path.join(os.path.dirname(__file__), "data", "simulation_results.json")
    if not os.path.exists(file_path):
        return {}
    try:
        mtime = os.path.getmtime(file_path)
        if _sim_data_cache is None or mtime > _sim_data_mtime:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _sim_data_cache = {
                    p["team"]: 100.0 - p["group_exit_pct"]
                    for p in data.get("probabilities", [])
                }
                _sim_data_mtime = mtime
        return _sim_data_cache
    except Exception:
        return {}


DEFAULT_WEIGHTS = {
    "elo": 0.35,         # Proximity and average quality
    "odds": 0.25,        # Betting odds competitiveness
    "form": 0.15,        # Player and team form
    "narrative": 0.25    # Stage and stakes (significantly boosted)
}

def calculate_watchability(
    fixture: Fixture, 
    home_team: Team, 
    away_team: Team, 
    db: Session,
    weights: dict = None
) -> dict:
    """
    Calculates the watchability score for a fixture based on ELO, betting odds, form, and narratives.
    Weights can be customized dynamically.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS
        
    reasons = []
    
    # 1. ELO Score (Proximity & Average Quality)
    elo_diff = abs(home_team.elo - away_team.elo)
    # Proximity: 100 is identical ELO, 500 difference is 0.
    elo_proximity = max(0.0, 100.0 - (elo_diff / 5.0))
    
    # Average Quality: Reward matches between high-ELO teams.
    elo_avg = (home_team.elo + away_team.elo) / 2.0
    elo_quality = min(100.0, max(0.0, (elo_avg - 1400) / 7.0)) # Scale 1400-2100 to 0-100
    
    # ELO combined score: 70% proximity (similar strength), 30% elite clash quality
    elo_score = (elo_proximity * 0.7) + (elo_quality * 0.3)
    
    if elo_diff <= 80:
        reasons.append(f"Highly competitive matchup: ELO ratings are extremely close (diff: {elo_diff}).")
    elif elo_diff <= 180:
        reasons.append(f"Well-matched clash: ELO difference is only {elo_diff} points.")
    elif elo_diff > 350:
        if home_team.elo < away_team.elo and home_team.form_score > 75:
            reasons.append(f"David vs. Goliath: Underdog {home_team.name} in great form challenging {away_team.name}!")
        elif away_team.elo < home_team.elo and away_team.form_score > 75:
            reasons.append(f"David vs. Goliath: Underdog {away_team.name} in great form challenging {home_team.name}!")
        else:
            reasons.append(f"Potential for a massive upset: {max(home_team.name, away_team.name, key=lambda t: home_team.elo if t==home_team.name else away_team.elo)} is heavily favored.")

    if elo_avg > 1950:
        reasons.append(f"Elite tier clash: Average ELO of both teams is exceptionally high ({int(elo_avg)}).")

    # 2. Betting Odds Competitiveness
    # Smaller diff in odds means a highly unpredictable, tight game
    latest_odds = fixture.latest_odds
    odds_diff = abs(latest_odds.odds_home - latest_odds.odds_away)
    # Proximity: 100 when odds are equal, drops as gap increases
    odds_proximity = max(0.0, 100.0 - (odds_diff * 25.0))
    
    # Draw index: Lower draw odds indicate bookies expect a very tight, hard-to-break game
    draw_index = max(0.0, 100.0 - ((latest_odds.odds_draw - 2.5) * 40.0))
    
    odds_score = (odds_proximity * 0.8) + (draw_index * 0.2)
    odds_score = min(100.0, max(0.0, odds_score))
    
    if odds_diff < 0.4:
        reasons.append("Bookmakers predict an extremely tight game with almost even odds.")
    elif odds_diff > 2.5:
        reasons.append("High odds disparity: Expect a lot of goals or a dominant display.")

    # 3. Form Score (Team & Player Form)
    team_form = (home_team.form_score + away_team.form_score) / 2.0
    
    # Query players
    from backend.crud.player import get_players_by_team
    home_players = get_players_by_team(db, home_team.name)
    away_players = get_players_by_team(db, away_team.name)
    all_players = home_players + away_players
    
    if all_players:
        player_form = sum(p.form_score for p in all_players) / len(all_players)
        form_score = (team_form * 0.5) + (player_form * 0.5)
    else:
        form_score = team_form
        
    # Check for hot players
    hot_players = [p for p in all_players if p.form_score >= 85]
    if hot_players:
        reasons.append(f"Players to watch: {', '.join([p.name for p in hot_players[:2]])} are in red-hot form.")
        
    if home_team.win_streak >= 3:
        reasons.append(f"{home_team.name} is on a roll with a {home_team.win_streak}-match win streak.")
    if away_team.win_streak >= 3:
        reasons.append(f"{away_team.name} is on a roll with a {away_team.win_streak}-match win streak.")

    # 4. Narrative & Stage Score
    stage_scores = {
        "Group Stage": 60.0,
        "Round of 16": 75.0,
        "Quarter-final": 88.0,
        "Semi-final": 95.0,
        "Final": 100.0
    }
    stage_score = stage_scores.get(fixture.stage, 60.0)
    
    if fixture.stage != "Group Stage":
        narrative_score = stage_score
        reasons.append(f"High stakes: World Cup {fixture.stage} knockout match (winner takes all).")
    else:
        # Dynamic stakes calculation for Group Stage based on qualification probabilities
        probs = get_simulation_probabilities()
        p_home = probs.get(home_team.name, 50.0)
        p_away = probs.get(away_team.name, 50.0)
        
        # Calculate individual team qualification stakes (0 to 100)
        # Closer to 50% means higher stakes (survival is on the line)
        s_home = 100.0 - 2.0 * abs(p_home - 50.0)
        s_away = 100.0 - 2.0 * abs(p_away - 50.0)
        
        # Combine home and away stakes: weighted towards the higher-stakes team
        # but penalizing if the other team has zero stakes (already qualified/eliminated)
        s_match = 0.7 * max(s_home, s_away) + 0.3 * min(s_home, s_away)
        
        # Scale to stage score (baseline is 10.0, max is 100.0)
        baseline = 10.0
        narrative_score = baseline + (100.0 - baseline) * (s_match / 100.0)
        narrative_score = round(min(100.0, max(0.0, narrative_score)), 1)
        
        from backend.database import TournamentTeam
        tt = db.query(TournamentTeam).filter(
            TournamentTeam.tournament_id == fixture.tournament_id,
            TournamentTeam.team_id == home_team.id
        ).first()
        group_letter = tt.group_name if tt else ""
        reasons.append(f"Crucial World Cup Group {group_letter} clash.")
        
        # Add detailed, context-specific stakes analysis reasons
        if home_team.name in probs and away_team.name in probs:
            is_home_safe = p_home >= 98.0
            is_away_safe = p_away >= 98.0
            is_home_out = p_home <= 2.0
            is_away_out = p_away <= 2.0
            
            if is_home_safe and is_away_safe:
                reasons.append("Qualification settled: Both teams have already secured qualification to the knockout stage.")
            elif is_home_out and is_away_out:
                reasons.append("Dead rubber: Both teams have already been eliminated from tournament progression.")
            elif is_home_safe and is_away_out:
                reasons.append(f"Mixed stakes: {home_team.name} is already qualified, while {away_team.name} has been eliminated.")
            elif is_away_safe and is_home_out:
                reasons.append(f"Mixed stakes: {away_team.name} is already qualified, while {home_team.name} has been eliminated.")
            elif is_home_safe:
                reasons.append(f"{home_team.name} has qualified. {away_team.name} (qualification chance: {p_away:.0f}%) is fighting for survival.")
            elif is_away_safe:
                reasons.append(f"{away_team.name} has qualified. {home_team.name} (qualification chance: {p_home:.0f}%) is fighting for survival.")
            elif is_home_out:
                reasons.append(f"{home_team.name} is eliminated. {away_team.name} (qualification chance: {p_away:.0f}%) must win to progress.")
            elif is_away_out:
                reasons.append(f"{away_team.name} is eliminated. {home_team.name} (qualification chance: {p_home:.0f}%) must win to progress.")
            else:
                # Both are fighting
                if abs(p_home - p_away) <= 15.0:
                    reasons.append(f"High stakes decider: Both teams are actively fighting for qualification (chances: {home_team.name} {p_home:.0f}%, {away_team.name} {p_away:.0f}%).")
                else:
                    reasons.append(f"Crucial battle: {home_team.name} ({p_home:.0f}% chance) and {away_team.name} ({p_away:.0f}% chance) fight for qualification spots.")

    # Apply Weights
    overall_score = (
        (elo_score * weights["elo"]) +
        (odds_score * weights["odds"]) +
        (form_score * weights["form"]) +
        (narrative_score * weights["narrative"])
    )
    
    # Guarantee 0-100 range
    overall_score = round(min(100.0, max(0.0, overall_score)), 1)
    
    return {
        "watchability_score": overall_score,
        "competitiveness_score": round(elo_score, 1),
        "odds_score": round(odds_score, 1),
        "form_score": round(form_score, 1),
        "narrative_score": round(narrative_score, 1),
        "reasons": reasons
    }

def update_fixture_score(fixture: Fixture, db: Session, weights: dict = None) -> Fixture:
    """
    Recalculates and updates the watchability scores for a single fixture.
    """
    home_team = fixture.home_team
    away_team = fixture.away_team
    
    if not home_team or not away_team:
        return fixture
        
    scores = calculate_watchability(fixture, home_team, away_team, db, weights)
    
    fixture.watchability_score = scores["watchability_score"]
    fixture.competitiveness_score = scores["competitiveness_score"]
    fixture.odds_score = scores["odds_score"]
    fixture.form_score = scores["form_score"]
    fixture.narrative_score = scores["narrative_score"]
    fixture.reasons_json = json.dumps(scores["reasons"])
    
    return fixture
