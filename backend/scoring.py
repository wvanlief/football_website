import json
from sqlalchemy.orm import Session
from backend.database import Team, Player, Fixture

DEFAULT_WEIGHTS = {
    "elo": 0.50,         # Heavy weight on ELO proximity and quality
    "odds": 0.30,        # Betting odds competitiveness
    "form": 0.15,        # Player and team form
    "narrative": 0.05    # Stage and streaks
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
    odds_diff = abs(fixture.odds_home - fixture.odds_away)
    # Proximity: 100 when odds are equal, drops as gap increases
    odds_proximity = max(0.0, 100.0 - (odds_diff * 25.0))
    
    # Draw index: Lower draw odds indicate bookies expect a very tight, hard-to-break game
    draw_index = max(0.0, 100.0 - ((fixture.odds_draw - 2.5) * 40.0))
    
    odds_score = (odds_proximity * 0.8) + (draw_index * 0.2)
    odds_score = min(100.0, max(0.0, odds_score))
    
    if odds_diff < 0.4:
        reasons.append("Bookmakers predict an extremely tight game with almost even odds.")
    elif odds_diff > 2.5:
        reasons.append("High odds disparity: Expect a lot of goals or a dominant display.")

    # 3. Form Score (Team & Player Form)
    team_form = (home_team.form_score + away_team.form_score) / 2.0
    
    # Query players
    home_players = db.query(Player).filter(Player.team_name == home_team.name).all()
    away_players = db.query(Player).filter(Player.team_name == away_team.name).all()
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
    
    # Narrative score is stage score + bonus for streaks
    narrative_score = stage_score
    if fixture.stage != "Group Stage":
        reasons.append(f"High stakes: World Cup {fixture.stage} knockout match (winner takes all).")
    else:
        reasons.append(f"Crucial World Cup Group {home_team.group_name} clash.")

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
    home_team = db.query(Team).filter(Team.name == fixture.home_team_name).first()
    away_team = db.query(Team).filter(Team.name == fixture.away_team_name).first()
    
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
