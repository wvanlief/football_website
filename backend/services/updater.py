import os
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

from backend.database import Team, Fixture, Tournament, Competition, SessionLocal
from backend.scoring import update_fixture_score
from backend.services.ingestion import NameNormalizer
from backend.services.odds import update_odds_from_api
from backend.services.tournament import propagate_knockout_fixtures
from backend.services.simulation import run_monte_carlo_simulation
from backend.services.standings import recalculate_tournament_team_standings
from backend.services.format_adapters import (
    get_format_adapter,
    STAGE_MAPPING,
    STADIUM_TIMEZONES,
    parse_match_date,
    fetch_games_with_fallback
)

from backend.services.elo import fetch_current_elo_ratings, fetch_clubelo_ratings
from backend.services.seeder import call_football_api
from backend.utils import fetch_json_with_retry, fetch_url_with_retry

def fetch_json(url: str, use_cache: bool = True) -> list:
    return fetch_json_with_retry(url, use_cache=use_cache)

def normalize_team_name(name: str) -> str:
    return NameNormalizer().normalize(name)

def matches_team_name(db_name: str, api_name: str) -> bool:
    return NameNormalizer().match_names(db_name, api_name)

def update_results_and_odds(db: Session) -> dict:
    """
    Main update task. Loops through all active tournaments and delegates format-specific
    updating to format adapters.
    """
    tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
    if not tournaments:
        tournaments = db.query(Tournament).all()
    if not tournaments:
        return {"status": "error", "message": "No tournaments found in DB. Please run database seeding first."}

    fixtures_created = 0
    fixtures_updated_results = 0

    for tourney in tournaments:
        comp = tourney.competition
        print(f"Updating tournament: {comp.name} ({tourney.season_name})")
        adapter = get_format_adapter(comp.format_engine, comp.name)
        
        created, updated = adapter.sync_results(db, tourney)
        fixtures_created += created
        fixtures_updated_results += updated

        # Update Odds history for active tournament fixtures
        try:
            tourney_fixtures = db.query(Fixture).filter(Fixture.tournament_id == tourney.id).all()
            update_odds_from_api(tourney_fixtures, db, sport_key=comp.odds_api_sport_key or "soccer_fifa_world_cup")
        except Exception as e:
            print(f"Warning: Failed to update odds from API: {e}")

    try:
        propagate_knockout_fixtures(db)
    except Exception as e:
        print(f"Warning: propagate_knockout_fixtures failed: {e}")
        
    db.commit()

    for tourney in tournaments:
        try:
            recalculate_tournament_team_standings(db, tourney.id)
            if tourney.competition and tourney.competition.format_engine == "nations_league":
                from backend.services.tournament import evaluate_nations_league_promotions
                evaluate_nations_league_promotions(db, tourney.id)
        except Exception as e:
            print(f"Warning: Failed to recalculate standings/promotions for tournament {tourney.id}: {e}")
    db.commit()

    all_current_fixtures = db.query(Fixture).all()
    for fixture in all_current_fixtures:
        try:
            update_fixture_score(fixture, db)
        except Exception as e:
            pass
    db.commit()

    simulation_status = "Simulation paused for Phase 3"
    has_wc = any(t.competition.format_engine == "group_knockout" or "World Cup" in t.competition.name for t in tournaments)
    if has_wc:
        print("Triggering tournament Monte Carlo simulation for World Cup...")
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
    Lightweight updater for live scores. Only queries when matches are scheduled/live.
    """
    now_time = datetime.now(timezone.utc)
    
    window_start = now_time - timedelta(hours=3)
    window_end = now_time + timedelta(minutes=15)
    
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
    
    tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
    if not tournaments:
        tournaments = db.query(Tournament).all()
        
    fixtures_updated = 0
    fixtures_finished = 0
    
    for tourney in tournaments:
        comp = tourney.competition
        adapter = get_format_adapter(comp.format_engine, comp.name)
        updated, finished = adapter.sync_live_scores(db, tourney)
        fixtures_updated += updated
        fixtures_finished += finished

    if fixtures_finished > 0 or fixtures_updated > 0:
        try:
            propagate_knockout_fixtures(db)
        except Exception as e:
            pass
        db.commit()
        
        if fixtures_finished > 0:
            for tourney in tournaments:
                try:
                    recalculate_tournament_team_standings(db, tourney.id)
                    if tourney.competition and tourney.competition.format_engine == "nations_league":
                        from backend.services.tournament import evaluate_nations_league_promotions
                        evaluate_nations_league_promotions(db, tourney.id)
                except Exception as e:
                    pass
            db.commit()

    simulation_status = "Simulation paused for Phase 3"
    if fixtures_finished > 0:
        has_wc = any(t.competition.format_engine == "group_knockout" or "World Cup" in t.competition.name for t in tournaments)
        if has_wc:
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
