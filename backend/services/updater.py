import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import or_

load_dotenv()

from backend.database import (
    Team, Fixture, Tournament, FixtureOdds, EloHistory, get_db
)
from backend.scoring import update_fixture_score
from backend.ingestor import (
    normalize_team_name, calculate_default_odds, update_odds_from_api
)
from backend.services.tournament import run_monte_carlo_simulation

STAGE_MAPPING = {
    "group": "Group Stage",
    "r32": "Round of 32",
    "round_of_32": "Round of 32",
    "r16": "Round of 16",
    "round_of_16": "Round of 16",
    "qf": "Quarter-final",
    "quarter": "Quarter-final",
    "semi": "Semi-final",
    "sf": "Semi-final",
    "third": "Third-place play-off",
    "final": "Final"
}

STADIUM_TIMEZONES = {
    "1": "America/Mexico_City",
    "2": "America/Mexico_City",
    "3": "America/Monterrey",
    "4": "America/Chicago",
    "5": "America/Chicago",
    "6": "America/Chicago",
    "7": "America/New_York",
    "8": "America/New_York",
    "9": "America/New_York",
    "10": "America/New_York",
    "11": "America/New_York",
    "12": "America/Toronto",
    "13": "America/Vancouver",
    "14": "America/Los_Angeles",
    "15": "America/Los_Angeles",
    "16": "America/Los_Angeles",
}

def parse_match_date(date_str: str, stadium_id: str) -> datetime:
    """Parses a local date string and stadium ID into a UTC datetime."""
    try:
        dt_naive = datetime.strptime(date_str, "%m/%d/%Y %H:%M")
        tz_name = STADIUM_TIMEZONES.get(str(stadium_id), "America/New_York")
        dt_localized = dt_naive.replace(tzinfo=ZoneInfo(tz_name))
        return dt_localized.astimezone(timezone.utc)
    except Exception:
        try:
            dt = datetime.strptime(date_str, "%m/%d/%Y %H:%M")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)

def calculate_elo_updates(home_elo: int, away_elo: int, outcome: float) -> tuple[int, int]:
    """
    outcome: 1.0 for home win, 0.5 for draw, 0.0 for away win
    Returns updated (home_elo, away_elo)
    """
    diff = home_elo - away_elo
    p_home = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
    change = round(30.0 * (outcome - p_home))
    return home_elo + change, away_elo - change

def update_team_streaks_and_form(home_team: Team, away_team: Team, outcome: float):
    """Updates the win/draw/loss streaks and form score for both teams based on outcome."""
    if outcome == 1.0: # Home Win
        home_team.win_streak += 1
        home_team.draw_streak = 0
        home_team.loss_streak = 0
        
        away_team.loss_streak += 1
        away_team.win_streak = 0
        away_team.draw_streak = 0
    elif outcome == 0.0: # Away Win
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

    # Form score update based on ELO: min(95.0, max(45.0, 50.0 + (elo - 1500) * 0.05))
    home_team.form_score = round(min(95.0, max(45.0, 50.0 + (home_team.elo - 1500) * 0.05)), 1)
    away_team.form_score = round(min(95.0, max(45.0, 50.0 + (away_team.elo - 1500) * 0.05)), 1)

def recalculate_team_streaks(db: Session):
    """Recalculates win/draw/loss streaks for all teams based on finished fixtures in chronological order."""
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


from backend.utils import fetch_json_with_retry

def fetch_json(url: str) -> list:
    """Helper to fetch JSON content from a URL."""
    return fetch_json_with_retry(url)

def map_api_football_round_to_type_key(round_str: str) -> str:
    if not round_str:
        return "group"
    r = round_str.lower()
    if "group" in r:
        return "group"
    elif "32" in r:
        return "round_of_32"
    elif "16" in r:
        return "round_of_16"
    elif "quarter" in r:
        return "quarter"
    elif "semi" in r:
        return "semi"
    elif "third" in r or "3rd" in r:
        return "third"
    elif "final" in r:
        return "final"
    return "group"

def fetch_games_with_fallback() -> tuple[list, bool]:
    """
    Fetches games list. Returns a tuple: (fetched_matches_list, is_fallback_used).
    Attempts to fetch from primary URL first, and if it fails or returns no matches,
    falls back to API-Sports.
    """
    primary_url = "https://worldcup26.ir/get/games"
    try:
        print("Attempting to fetch games from primary live scoring API...")
        res = fetch_json(primary_url)
        if res:
            games = res.get("games") if isinstance(res, dict) else res
            if games and len(games) > 0:
                print(f"Successfully fetched {len(games)} games from primary API.")
                return games, False
    except Exception as e:
        print(f"Primary live scoring API failed: {e}")

    # Fallback to API-Sports / API-Football
    api_key = os.getenv("FOOTBALL_API_KEY")
    if not api_key:
        print("No FOOTBALL_API_KEY configured in environment. Cannot use fallback API.")
        return [], False

    fallback_url = "https://v3.football.api-sports.io/fixtures?league=1&season=2026"
    headers = {
        "x-apisports-key": api_key,
        "User-Agent": "Mozilla/5.0"
    }
    try:
        print("Attempting to fetch games from fallback API (API-Sports)...")
        res = fetch_json_with_retry(fallback_url, headers=headers)
        if isinstance(res, dict) and "response" in res:
            fixtures = res["response"]
            if fixtures:
                print(f"Successfully fetched {len(fixtures)} games from fallback API.")
                # Convert API-Sports format to primary API format
                converted_games = []
                for f in fixtures:
                    fixture_info = f.get("fixture", {})
                    teams_info = f.get("teams", {})
                    goals_info = f.get("goals", {})
                    league_info = f.get("league", {})
                    
                    status_short = fixture_info.get("status", {}).get("short", "")
                    finished = "TRUE" if status_short in ("FT", "AET", "PEN") else "FALSE"
                    
                    # Convert UTC date to local format for parse_match_date
                    api_date = fixture_info.get("date")
                    local_date_str = ""
                    if api_date:
                        try:
                            # e.g., "2026-06-11T13:00:00+00:00"
                            dt_utc = datetime.fromisoformat(api_date.replace('Z', '+00:00'))
                            # Use stadium 7 (New York) as a default stadium time zone for conversion
                            stadium_tz = ZoneInfo(STADIUM_TIMEZONES.get("7", "America/New_York"))
                            dt_local = dt_utc.astimezone(stadium_tz)
                            local_date_str = dt_local.strftime("%m/%d/%Y %H:%M")
                        except Exception as date_err:
                            print(f"Error parsing date {api_date}: {date_err}")
                    
                    round_str = league_info.get("round", "")
                    type_key = map_api_football_round_to_type_key(round_str)
                    
                    m = {
                        "id": str(fixture_info.get("id")),
                        "home_team_name_en": teams_info.get("home", {}).get("name"),
                        "away_team_name_en": teams_info.get("away", {}).get("name"),
                        "home_team_id": None,
                        "away_team_id": None,
                        "type": type_key,
                        "finished": finished,
                        "home_score": str(goals_info.get("home")) if goals_info.get("home") is not None else "null",
                        "away_score": str(goals_info.get("away")) if goals_info.get("away") is not None else "null",
                        "local_date": local_date_str,
                        "stadium_id": "7"
                    }
                    converted_games.append(m)
                return converted_games, True
    except Exception as e:
        print(f"Fallback API failed: {e}")
        
    return [], False

def update_results_and_odds(db: Session) -> dict:
    """
    Main update task. Fetches official schedules/results and odds, updates database schemas,
    re-evaluates watchability indices, and runs simulations.
    """
    # 1. Fetch external configurations
    fetched_matches = []
    fetched_teams = []
    is_fallback = False
    
    try:
        fetched_matches, is_fallback = fetch_games_with_fallback()
    except Exception as e:
        print(f"Error during matches fetch: {e}")
        
    if not fetched_matches:
        return {"status": "error", "message": "Failed to fetch schedule/results from primary and fallback APIs."}
        
    if not is_fallback:
        try:
            print("Fetching team mapping definitions from API...")
            teams_url = "https://worldcup26.ir/get/teams"
            res_teams = fetch_json(teams_url)
            fetched_teams = res_teams.get("teams") if isinstance(res_teams, dict) else res_teams
        except Exception as e:
            print(f"Warning: Failed to fetch team definitions: {e}. Name matching will be used.")
            fetched_teams = []

    # 2. Get active tournament
    tourney = db.query(Tournament).filter(Tournament.status == "Active").first()
    if not tourney:
        tourney = db.query(Tournament).first()
    if not tourney:
        return {"status": "error", "message": "No active tournament found in DB. Please run database seeding first."}

    # 3. Create dictionaries for fast resolution
    external_team_map = {t["id"]: normalize_team_name(t.get("name_en", "")) for t in fetched_teams} if fetched_teams else {}
    db_teams = db.query(Team).all()
    db_teams_by_name = {team.name: team for team in db_teams}
    
    # Track statistics
    fixtures_created = 0
    fixtures_updated_results = 0
    now_time = datetime.now(timezone.utc)
    
    # 4. Iterate over matches JSON
    for m in fetched_matches:
        h_name = external_team_map.get(m.get("home_team_id")) if external_team_map else None
        if not h_name:
            h_name = normalize_team_name(m.get("home_team_name_en") or m.get("home_team_label") or "")
            
        a_name = external_team_map.get(m.get("away_team_id")) if external_team_map else None
        if not a_name:
            a_name = normalize_team_name(m.get("away_team_name_en") or m.get("away_team_label") or "")
        
        home_team = db_teams_by_name.get(h_name)
        away_team = db_teams_by_name.get(a_name)
        
        stage = STAGE_MAPPING.get(m.get("type"), "Group Stage")
        dt_utc = parse_match_date(m.get("local_date"), m.get("stadium_id"))
        api_match_id = str(m.get("id"))
        
        fixture = None
        if api_match_id:
            fixture = db.query(Fixture).filter(
                Fixture.tournament_id == tourney.id,
                Fixture.api_id == api_match_id
            ).first()
            
        if not fixture and home_team and away_team:
            fixture = db.query(Fixture).filter(
                Fixture.tournament_id == tourney.id,
                Fixture.stage == stage,
                or_(
                    (Fixture.home_team_id == home_team.id) & (Fixture.away_team_id == away_team.id),
                    (Fixture.home_team_id == away_team.id) & (Fixture.away_team_id == home_team.id)
                )
            ).first()
            
        # Determine status and outcomes
        is_finished_in_feed = m.get("finished") == "TRUE"
        feed_home_score = int(m["home_score"]) if is_finished_in_feed and m.get("home_score") not in (None, 'null') else None
        feed_away_score = int(m["away_score"]) if is_finished_in_feed and m.get("away_score") not in (None, 'null') else None
        
        # Create a new fixture if it's missing (e.g. newly determined knockout matches)
        if not fixture:
            h_elo = home_team.elo if home_team else 1700
            a_elo = away_team.elo if away_team else 1700
            odds_h, odds_d, odds_a = calculate_default_odds(h_elo, a_elo)
            fixture = Fixture(
                tournament_id=tourney.id,
                home_team_id=home_team.id if home_team else None,
                away_team_id=away_team.id if away_team else None,
                home_team_placeholder=h_name if not home_team else None,
                away_team_placeholder=a_name if not away_team else None,
                api_id=api_match_id,
                date_utc=dt_utc,
                stage=stage,
                status="Scheduled",
                home_score=None,
                away_score=None,
                winner_id=None
            )
            db.add(fixture)
            db.flush()
            
            # Seed initial odds record
            init_odds = FixtureOdds(
                fixture_id=fixture.id,
                recorded_at=dt_utc - timedelta(days=2),
                odds_home=odds_h,
                odds_draw=odds_d,
                odds_away=odds_a
            )
            db.add(init_odds)
            fixtures_created += 1
            
        # Update team ids if they were placeholders and now we resolved them
        if home_team and fixture.home_team_id is None:
            fixture.home_team_id = home_team.id
            fixture.home_team_placeholder = None
        if away_team and fixture.away_team_id is None:
            fixture.away_team_id = away_team.id
            fixture.away_team_placeholder = None
            
        # Update existing scheduled fixture if it's now finished in feed
        if fixture.status != "Finished" and is_finished_in_feed:
            fixture.status = "Finished"
            fixture.home_score = feed_home_score
            fixture.away_score = feed_away_score
            
            if home_team and away_team:
                fixture.home_team_id = home_team.id
                fixture.away_team_id = away_team.id
                fixture.home_team_placeholder = None
                fixture.away_team_placeholder = None
                
                # Determine outcome relative to home team
                if feed_home_score > feed_away_score:
                    outcome = 1.0
                    fixture.winner_id = home_team.id
                elif feed_home_score < feed_away_score:
                    outcome = 0.0
                    fixture.winner_id = away_team.id
                else:
                    outcome = 0.5
                    fixture.winner_id = None
                    
                # Perform ELO update
                home_elo_old = home_team.elo
                away_elo_old = away_team.elo
                
                home_elo_new, away_elo_new = calculate_elo_updates(home_elo_old, away_elo_old, outcome)
                
                home_team.elo = home_elo_new
                away_team.elo = away_elo_new
                
                # Update streaks and form
                update_team_streaks_and_form(home_team, away_team, outcome)
                
                # Save historical records
                db.add(EloHistory(team_id=home_team.id, recorded_at=now_time, elo_rating=home_elo_new))
                db.add(EloHistory(team_id=away_team.id, recorded_at=now_time, elo_rating=away_elo_new))
                
            fixtures_updated_results += 1
            
    db.commit()
    
    # 5. Fetch and update odds history from API if key is present
    all_current_fixtures = db.query(Fixture).all()
    update_odds_from_api(all_current_fixtures, db)
    db.commit()
    
    # 5.5 Sync team Elo ratings with eloratings.net
    try:
        print("Syncing Elo ratings from eloratings.net...")
        from backend.ingestor import fetch_current_elo_ratings
        live_elo = fetch_current_elo_ratings()
        
        teams_updated = 0
        for team in db_teams:
            fetched_elo = live_elo.get(team.name)
            if fetched_elo is not None and team.elo != fetched_elo:
                team.elo = fetched_elo
                team.form_score = round(min(95.0, max(45.0, 50.0 + (fetched_elo - 1500) * 0.05)), 1)
                
                # Save Elo history record
                db_elo_hist = EloHistory(
                    team_id=team.id,
                    recorded_at=now_time,
                    elo_rating=fetched_elo
                )
                db.add(db_elo_hist)
                teams_updated += 1
        db.commit()
        print(f"Successfully synced Elo ratings from eloratings.net. Updated {teams_updated} teams.")
    except Exception as e:
        print(f"Warning: Failed to sync Elo ratings from eloratings.net: {e}. Keeping current ratings.")
    
    # 6. Trigger the Monte Carlo bracket simulation using the new scores and ELO ratings
    print("Triggering tournament Monte Carlo simulation...")
    try:
        run_monte_carlo_simulation(db)
        simulation_status = "Successfully updated and simulation completed."
    except Exception as e:
        simulation_status = f"Simulation failed with error: {str(e)}"
        
    # 7. Recalculate watchability scores for all matches using the latest simulation results
    for fixture in all_current_fixtures:
        update_fixture_score(fixture, db)
    db.commit()
    
    return {
        "status": "success",
        "fixtures_created": fixtures_created,
        "fixtures_updated_results": fixtures_updated_results,
        "simulation": simulation_status
    }

def update_live_scores(db: Session, force: bool = False) -> dict:
    """
    Lightweight updater for live scores. Only queries the results feed when games are scheduled/live.
    Exits early if no matches are active to avoid network/CPU usage.
    """
    now_time = datetime.now(timezone.utc)
    
    # Define match window: starting within 15 minutes or started in the last 3 hours
    window_start = now_time - timedelta(hours=3)
    window_end = now_time + timedelta(minutes=15)
    
    # Check if there are active match windows
    active_fixtures = db.query(Fixture).filter(
        Fixture.status != "Finished",
        Fixture.date_utc >= window_start,
        Fixture.date_utc <= window_end
    ).all()
    
    live_fixtures = db.query(Fixture).filter(Fixture.status == "Live").all()
    
    is_active_window = len(active_fixtures) > 0 or len(live_fixtures) > 0
    
    if not is_active_window and not force:
        print("No active match window. Skipping live update.")
        return {"status": "skipped", "message": "No active match window."}
        
    print(f"Active match window detected ({len(active_fixtures)} scheduled soon/ongoing, {len(live_fixtures)} live). Fetching scores...")
    
    # Fetch games data
    fetched_matches = []
    is_fallback = False
    try:
        fetched_matches, is_fallback = fetch_games_with_fallback()
    except Exception as e:
        print(f"Error fetching live scores feed: {e}")
        return {"status": "error", "message": f"Failed to fetch scores: {str(e)}"}
        
    if not fetched_matches:
        return {"status": "error", "message": "Failed to fetch live scores from both primary and fallback APIs."}
        
    external_team_map = {}
    if not is_fallback:
        try:
            teams_url = "https://worldcup26.ir/get/teams"
            res_teams = fetch_json(teams_url)
            fetched_teams = res_teams.get("teams") if isinstance(res_teams, dict) else res_teams
            external_team_map = {t["id"]: normalize_team_name(t.get("name_en", "")) for t in fetched_teams}
        except Exception as e:
            print(f"Warning: Failed to fetch team definitions: {e}. Name matching will be used.")
        
    # Get active tournament
    tourney = db.query(Tournament).filter(Tournament.status == "Active").first()
    if not tourney:
        tourney = db.query(Tournament).first()
    if not tourney:
        return {"status": "error", "message": "No active tournament found."}
        
    db_teams = db.query(Team).all()
    db_teams_by_name = {team.name: team for team in db_teams}
    
    fixtures_updated = 0
    fixtures_finished = 0
    run_simulation = False
    
    for m in fetched_matches:
        # Resolve names
        h_id = m.get("home_team_id")
        a_id = m.get("away_team_id")
        h_name = external_team_map.get(h_id) if external_team_map else normalize_team_name(m.get("home_team_name_en") or m.get("home_team_label") or "")
        a_name = external_team_map.get(a_id) if external_team_map else normalize_team_name(m.get("away_team_name_en") or m.get("away_team_label") or "")
        
        home_team = db_teams_by_name.get(h_name)
        away_team = db_teams_by_name.get(a_name)
        
        stage = STAGE_MAPPING.get(m.get("type"), "Group Stage")
        api_match_id = str(m.get("id"))
        
        fixture = None
        if api_match_id:
            fixture = db.query(Fixture).filter(
                Fixture.tournament_id == tourney.id,
                Fixture.api_id == api_match_id
            ).first()
            
        if not fixture and home_team and away_team:
            # Query the fixture by teams (retro-compatibility)
            fixture = db.query(Fixture).filter(
                Fixture.tournament_id == tourney.id,
                Fixture.stage == stage,
                or_(
                    (Fixture.home_team_id == home_team.id) & (Fixture.away_team_id == away_team.id),
                    (Fixture.home_team_id == away_team.id) & (Fixture.away_team_id == home_team.id)
                )
            ).first()
            
        if not fixture:
            continue
            
        # Update team ids if they were placeholders and now we resolved them
        if home_team and fixture.home_team_id is None:
            fixture.home_team_id = home_team.id
            fixture.home_team_placeholder = None
        if away_team and fixture.away_team_id is None:
            fixture.away_team_id = away_team.id
            fixture.away_team_placeholder = None
            
        # If already finished, no need to update scores live
        if fixture.status == "Finished":
            continue
            
        is_finished_in_feed = m.get("finished") == "TRUE"
        feed_home_score = int(m["home_score"]) if m.get("home_score") not in (None, 'null') else None
        feed_away_score = int(m["away_score"]) if m.get("away_score") not in (None, 'null') else None
        
        if is_finished_in_feed:
            # Match has finished!
            fixture.status = "Finished"
            fixture.home_score = feed_home_score
            fixture.away_score = feed_away_score
            
            # Determine winner & ELO updates
            if feed_home_score > feed_away_score:
                outcome = 1.0
                fixture.winner_id = home_team.id
            elif feed_home_score < feed_away_score:
                outcome = 0.0
                fixture.winner_id = away_team.id
            else:
                outcome = 0.5
                fixture.winner_id = None
                
            home_elo_old = home_team.elo
            away_elo_old = away_team.elo
            home_elo_new, away_elo_new = calculate_elo_updates(home_elo_old, away_elo_old, outcome)
            
            home_team.elo = home_elo_new
            away_team.elo = away_elo_new
            
            update_team_streaks_and_form(home_team, away_team, outcome)
            
            # Save ELO history
            db.add(EloHistory(team_id=home_team.id, recorded_at=now_time, elo_rating=home_elo_new))
            db.add(EloHistory(team_id=away_team.id, recorded_at=now_time, elo_rating=away_elo_new))
            
            # Recalculate watchability score
            update_fixture_score(fixture, db)
            
            fixtures_finished += 1
            run_simulation = True # Since a game finished, run bracket simulations
        else:
            # Make fixture.date_utc timezone aware
            f_date_aware = fixture.date_utc.replace(tzinfo=timezone.utc) if fixture.date_utc.tzinfo is None else fixture.date_utc
            is_in_progress = (f_date_aware - timedelta(minutes=5)) <= now_time <= (f_date_aware + timedelta(hours=3))

            
            if is_in_progress and feed_home_score is not None and feed_away_score is not None:
                fixture.status = "Live"
                fixture.home_score = feed_home_score
                fixture.away_score = feed_away_score
                fixtures_updated += 1
            else:
                # Keep as Scheduled, do not save placeholder zero scores in the DB
                fixture.status = "Scheduled"
                fixture.home_score = None
                fixture.away_score = None

                
    if fixtures_finished > 0 or fixtures_updated > 0:
        db.commit()
        
    simulation_status = "Skipped"
    if run_simulation:
        print("A match has finished. Triggering tournament Monte Carlo simulation...")
        try:
            run_monte_carlo_simulation(db)
            simulation_status = "Successfully updated and simulation completed."
        except Exception as e:
            simulation_status = f"Simulation failed with error: {str(e)}"
            
    return {
        "status": "success",
        "fixtures_updated_live": fixtures_updated,
        "fixtures_finished": fixtures_finished,
        "simulation": simulation_status
    }

if __name__ == "__main__":
    import argparse
    from backend.database import SessionLocal
    
    parser = argparse.ArgumentParser(description="findfootball.games Database Ingestion and Update Task")
    parser.add_argument("--live", action="store_true", help="Run lightweight live-score update only")
    parser.add_argument("--force", action="store_true", help="Force updates even outside active match windows")
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        if args.live:
            print("Running live-score updater...")
            result = update_live_scores(db, force=args.force)
            print(json.dumps(result, indent=2))
        else:
            print("Running full results and odds updater...")
            result = update_results_and_odds(db)
            print(json.dumps(result, indent=2))
    finally:
        db.close()

