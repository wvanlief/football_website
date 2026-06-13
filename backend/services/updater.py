import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from sqlalchemy import or_

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
    "round_of_32": "Round of 32",
    "round_of_16": "Round of 16",
    "quarter": "Quarter-final",
    "semi": "Semi-final",
    "third": "Third-place play-off",
    "final": "Final"
}

STADIUM_TIMEZONES = {
    "1": "America/Mexico_City",
    "2": "America/Mexico_City",
    "3": "America/Monterrey",
    "4": "America/Vancouver",
    "5": "America/Los_Angeles",
    "6": "America/Los_Angeles",
    "7": "America/Los_Angeles",
    "8": "America/Chicago",
    "9": "America/Chicago",
    "10": "America/Chicago",
    "11": "America/New_York",
    "12": "America/New_York",
    "13": "America/New_York",
    "14": "America/New_York",
    "15": "America/New_York",
    "16": "America/New_York",
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

def fetch_json(url: str) -> list:
    """Helper to fetch JSON content from a URL."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode())

def update_results_and_odds(db: Session) -> dict:
    """
    Main update task. Fetches official schedules/results and odds, updates database schemas,
    re-evaluates watchability indices, and runs simulations.
    """
    # 1. Fetch external configurations
    try:
        print("Fetching official schedule/results from API...")
        matches_url = "https://worldcup26.ir/get/games"
        res_matches = fetch_json(matches_url)
        fetched_matches = res_matches.get("games") if isinstance(res_matches, dict) else res_matches
        
        print("Fetching team mapping definitions from API...")
        teams_url = "https://worldcup26.ir/get/teams"
        res_teams = fetch_json(teams_url)
        fetched_teams = res_teams.get("teams") if isinstance(res_teams, dict) else res_teams
    except Exception as e:
        print(f"Error fetching external database files: {e}")
        return {"status": "error", "message": f"Failed to fetch schedule files: {str(e)}"}

    # 2. Get active tournament
    tourney = db.query(Tournament).filter(Tournament.status == "Active").first()
    if not tourney:
        tourney = db.query(Tournament).first()
    if not tourney:
        return {"status": "error", "message": "No active tournament found in DB. Please run database seeding first."}

    # 3. Create dictionaries for fast resolution
    external_team_map = {t["id"]: normalize_team_name(t.get("name_en", "")) for t in fetched_teams}
    db_teams = db.query(Team).all()
    db_teams_by_name = {team.name: team for team in db_teams}
    
    # Track statistics
    fixtures_created = 0
    fixtures_updated_results = 0
    now_time = datetime.now(timezone.utc)
    
    # 4. Iterate over matches JSON
    for m in fetched_matches:
        h_name = external_team_map.get(m.get("home_team_id"))
        a_name = external_team_map.get(m.get("away_team_id"))
        
        # Skip placeholders
        if not h_name or not a_name:
            continue
            
        home_team = db_teams_by_name.get(h_name)
        away_team = db_teams_by_name.get(a_name)
        
        if not home_team or not away_team:
            continue
            
        stage = STAGE_MAPPING.get(m.get("type"), "Group Stage")
        dt_utc = parse_match_date(m.get("local_date"), m.get("stadium_id"))
        
        # Search for fixture in DB
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
        feed_home_score = int(m["home_score"]) if is_finished_in_feed and m.get("home_score") is not None else None
        feed_away_score = int(m["away_score"]) if is_finished_in_feed and m.get("away_score") is not None else None
        
        # Create a new fixture if it's missing (e.g. newly determined knockout matches)
        if not fixture:
            odds_h, odds_d, odds_a = calculate_default_odds(home_team.elo, away_team.elo)
            fixture = Fixture(
                tournament_id=tourney.id,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                date_utc=dt_utc,
                stage=stage,
                status="Finished" if is_finished_in_feed else "Scheduled",
                home_score=feed_home_score,
                away_score=feed_away_score,
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
            
        # Update existing scheduled fixture if it's now finished in feed
        if fixture.status != "Finished" and is_finished_in_feed:
            fixture.status = "Finished"
            fixture.home_score = feed_home_score
            fixture.away_score = feed_away_score
            
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
            db_home_elo_hist = EloHistory(
                team_id=home_team.id,
                recorded_at=now_time,
                elo_rating=home_elo_new
            )
            db_away_elo_hist = EloHistory(
                team_id=away_team.id,
                recorded_at=now_time,
                elo_rating=away_elo_new
            )
            db.add(db_home_elo_hist)
            db.add(db_away_elo_hist)
            
            fixtures_updated_results += 1
            
    db.commit()
    
    # 5. Fetch and update odds history from API if key is present
    all_current_fixtures = db.query(Fixture).all()
    update_odds_from_api(all_current_fixtures, db)
    db.commit()
    
    # 6. Recalculate watchability scores for all matches
    for fixture in all_current_fixtures:
        update_fixture_score(fixture, db)
    db.commit()
    
    # 6.5 Sync team Elo ratings with eloratings.net
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
    
    # 7. Trigger the Monte Carlo bracket simulation using the new scores and ELO ratings
    print("Triggering tournament Monte Carlo simulation...")
    try:
        run_monte_carlo_simulation(db)
        simulation_status = "Successfully updated and simulation completed."
    except Exception as e:
        simulation_status = f"Simulation failed with error: {str(e)}"
        
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
    try:
        matches_url = "https://worldcup26.ir/get/games"
        res_matches = fetch_json(matches_url)
        fetched_matches = res_matches.get("games") if isinstance(res_matches, dict) else res_matches
        
        # Try fetching teams to resolve external ID mapping. If it fails, fallback to name fields in games feed.
        try:
            teams_url = "https://worldcup26.ir/get/teams"
            res_teams = fetch_json(teams_url)
            fetched_teams = res_teams.get("teams") if isinstance(res_teams, dict) else res_teams
            external_team_map = {t["id"]: normalize_team_name(t.get("name_en", "")) for t in fetched_teams}
        except Exception:
            external_team_map = {}
    except Exception as e:
        print(f"Error fetching live scores feed: {e}")
        return {"status": "error", "message": f"Failed to fetch scores: {str(e)}"}
        
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
        h_name = external_team_map.get(h_id) if external_team_map else normalize_team_name(m.get("home_team_name_en", ""))
        a_name = external_team_map.get(a_id) if external_team_map else normalize_team_name(m.get("away_team_name_en", ""))
        
        if not h_name or not a_name:
            continue
            
        home_team = db_teams_by_name.get(h_name)
        away_team = db_teams_by_name.get(a_name)
        
        if not home_team or not away_team:
            continue
            
        stage = STAGE_MAPPING.get(m.get("type"), "Group Stage")
        
        # Query the fixture
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
            
        # If already finished, no need to update scores live
        if fixture.status == "Finished":
            continue
            
        is_finished_in_feed = m.get("finished") == "TRUE"
        feed_home_score = int(m["home_score"]) if m.get("home_score") is not None else None
        feed_away_score = int(m["away_score"]) if m.get("away_score") is not None else None
        
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

