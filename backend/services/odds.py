import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.database import FixtureOdds
from backend.utils import fetch_json_with_retry
from backend.services.ingestion import NameNormalizer

def calculate_default_odds(home_elo: int, away_elo: int, neutral_venue: bool = True, home_advantage: int = 100) -> tuple[float, float, float]:
    """
    Calculates default 1X2 betting odds based on home and away ELO ratings.
    """
    if not neutral_venue:
        home_elo += home_advantage

    diff = home_elo - away_elo
    prob_home_expected = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
    prob_away_expected = 1.0 - prob_home_expected
    
    prob_draw = 0.25
    prob_home = prob_home_expected * 0.75
    prob_away = prob_away_expected * 0.75
    
    odds_home = round(1.05 / max(0.05, prob_home), 2)
    odds_draw = round(1.05 / max(0.05, prob_draw), 2)
    odds_away = round(1.05 / max(0.05, prob_away), 2)
    
    return odds_home, odds_draw, odds_away

def update_odds_from_api(fixtures: list, db: Session, sport_key: str = "soccer_fifa_world_cup"):
    """
    Fetches latest match odds from The Odds API and records them in FixtureOdds history.
    """
    if not sport_key:
        print("Odds API sport key is None. Skipping Odds API update.")
        return
    api_key = os.getenv("THE_ODDS_API_KEY")
    if not api_key:
        print("No THE_ODDS_API_KEY found in environment. Skipping Odds API update.")
        return
        
    normalizer = NameNormalizer()
    print(f"Fetching odds from The Odds API for {sport_key}...")
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={api_key}&regions=eu&markets=h2h"
    try:
        odds_data = fetch_json_with_retry(url, provider="the_odds_api")
            
        odds_lookup = {}
        for match in odds_data:
            home = normalizer.normalize(match.get("home_team", ""))
            away = normalizer.normalize(match.get("away_team", ""))
            
            bookmakers = match.get("bookmakers", [])
            if not bookmakers:
                continue
                
            markets = bookmakers[0].get("markets", [])
            if not markets:
                continue
                
            outcomes = markets[0].get("outcomes", [])
            if len(outcomes) < 3:
                continue
                
            try:
                h_odds = next(o["price"] for o in outcomes if normalizer.normalize(o["name"]) == home)
                a_odds = next(o["price"] for o in outcomes if normalizer.normalize(o["name"]) == away)
                d_odds = next(o["price"] for o in outcomes if o["name"].lower() == "draw")
                
                odds_lookup[(home, away)] = (h_odds, d_odds, a_odds)
            except Exception:
                pass
                
        count = 0
        now_time = datetime.now(timezone.utc)
        for f in fixtures:
            if not f.home_team or not f.away_team:
                continue
            home_name = f.home_team.name
            away_name = f.away_team.name
            key = (home_name, away_name)
            rev_key = (away_name, home_name)
            
            odds_found = None
            if key in odds_lookup:
                odds_found = odds_lookup[key]
            elif rev_key in odds_lookup:
                odds_found = (odds_lookup[rev_key][2], odds_lookup[rev_key][1], odds_lookup[rev_key][0])
                
            if odds_found:
                db_odds = FixtureOdds(
                    fixture_id=f.id,
                    recorded_at=now_time,
                    odds_home=odds_found[0],
                    odds_draw=odds_found[1],
                    odds_away=odds_found[2]
                )
                db.add(db_odds)
                count += 1
                
        print(f"Successfully updated historicized odds for {count} matches from The Odds API.")
    except Exception as e:
        print(f"Error fetching/updating odds from The Odds API: {e}")
