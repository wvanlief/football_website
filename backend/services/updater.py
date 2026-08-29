import os
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

from backend.database import Team, Fixture, Tournament, Competition, SessionLocal
from backend.scoring import update_fixture_score
from backend.services.ingestion import NameNormalizer
from backend.services.odds import update_odds_from_api, calculate_default_odds
from backend.services.tournament import propagate_knockout_fixtures, invalidate_fixtures_cache

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
from backend.services.settling import settle_result
from backend.utils import fetch_json_with_retry, fetch_url_with_retry, fetch_json


def normalize_team_name(name: str) -> str:
    """Normalizes a team name using the NameNormalizer singleton."""
    return NameNormalizer().normalize(name)

def matches_team_name(db_name: str, api_name: str) -> bool:
    """Checks if two team names match using fuzzy matching logic."""
    return NameNormalizer().match_names(db_name, api_name)

def sync_global_date_results(db: Session, target_date: str) -> tuple:
    """
    Fetches global match fixtures for a specific date using a single API call (GET /fixtures?date=YYYY-MM-DD).
    Updates statuses, scores, and links to database fixtures. Returns (created_count, updated_count).
    """
    print(f"Fetching global results from API-Football for date={target_date}...")
    try:
        res = call_football_api("fixtures", {"date": target_date})
    except Exception as e:
        print(f"Error fetching global results for date {target_date}: {e}")
        return 0, 0

    if not res or not isinstance(res, dict) or "response" not in res:
        print(f"No response data returned for date={target_date}")
        return 0, 0

    items = res.get("response", [])
    print(f"Received {len(items)} global match fixtures for date={target_date}.")

    fixtures_updated = 0
    fixtures_created = 0

    for item in items:
        fixture_info = item.get("fixture", {})
        api_id = str(fixture_info.get("id"))
        status_info = fixture_info.get("status", {})
        status_short = status_info.get("short")
        
        new_status = "Scheduled"
        if status_short in ("FT", "AET", "PEN"):
            new_status = "Finished"
        elif status_short in ("1H", "HT", "2H", "ET", "P"):
            new_status = "Live"
        elif status_short in ("PST", "CANC", "ABD"):
            new_status = "Postponed"

        goals = item.get("goals", {})
        home_goals = goals.get("home")
        away_goals = goals.get("away")

        fixture = db.query(Fixture).filter(Fixture.api_id == api_id).first()
        
        if not fixture:
            teams_info = item.get("teams", {})
            api_home_id = str(teams_info.get("home", {}).get("id"))
            api_away_id = str(teams_info.get("away", {}).get("id"))
            
            home_team = db.query(Team).filter(Team.api_id == api_home_id).first()
            away_team = db.query(Team).filter(Team.api_id == api_away_id).first()
            
            if home_team and away_team and fixture_info.get("date"):
                match_dt = datetime.fromisoformat(fixture_info["date"].replace("Z", "+00:00"))
                match_date_str = match_dt.strftime("%Y-%m-%d")
                incoming_league_id = item.get("league", {}).get("id")
                
                candidates = db.query(Fixture).filter(
                    Fixture.home_team_id == home_team.id,
                    Fixture.away_team_id == away_team.id
                ).all()
                
                for cand in candidates:
                    if cand.date_utc and cand.date_utc.strftime("%Y-%m-%d") == match_date_str:
                        # League Isolation Guardrail: verify candidate competition matches incoming API league
                        cand_api_league = cand.tournament.competition.api_league_id if (cand.tournament and cand.tournament.competition) else None
                        if cand_api_league and incoming_league_id:
                            try:
                                if int(cand_api_league) != int(incoming_league_id):
                                    continue
                            except (ValueError, TypeError):
                                pass
                        fixture = cand
                        break

        if fixture:
            changed = False
            if new_status == "Finished":
                if fixture.status != "Finished" or fixture.home_score != home_goals or fixture.away_score != away_goals:
                    settle_result(fixture, home_goals if home_goals is not None else fixture.home_score, away_goals if away_goals is not None else fixture.away_score)
                    changed = True
            else:
                if fixture.status != new_status:
                    fixture.status = new_status
                    changed = True
                if home_goals is not None and fixture.home_score != home_goals:
                    fixture.home_score = home_goals
                    changed = True
                if away_goals is not None and fixture.away_score != away_goals:
                    fixture.away_score = away_goals
                    changed = True
                
            if changed:
                fixtures_updated += 1
                update_fixture_score(fixture, db)

    db.commit()
    print(f"Global sync for {target_date}: updated {fixtures_updated} fixtures.")
    return fixtures_created, fixtures_updated

def sync_global_live_scores(db: Session) -> tuple:
    """
    Fetches all live match scores globally in a single API call (GET /fixtures?live=all).
    Returns (updated_count, finished_count).
    """
    print("Fetching global live matches from API-Football (GET /fixtures?live=all)...")
    try:
        res = call_football_api("fixtures", {"live": "all"})
    except Exception as e:
        print(f"Error fetching live matches: {e}")
        return 0, 0

    if not res or not isinstance(res, dict) or "response" not in res:
        return 0, 0

    items = res.get("response", [])
    print(f"Received {len(items)} global live matches.")

    fixtures_updated = 0
    fixtures_finished = 0

    for item in items:
        fixture_info = item.get("fixture", {})
        api_id = str(fixture_info.get("id"))
        status_info = fixture_info.get("status", {})
        status_short = status_info.get("short")

        new_status = "Live"
        if status_short in ("FT", "AET", "PEN"):
            new_status = "Finished"

        goals = item.get("goals", {})
        home_goals = goals.get("home")
        away_goals = goals.get("away")

        fixture = db.query(Fixture).filter(Fixture.api_id == api_id).first()
        if fixture:
            changed = False
            if new_status == "Finished":
                if fixture.status != "Finished":
                    fixtures_finished += 1
                if fixture.status != "Finished" or fixture.home_score != home_goals or fixture.away_score != away_goals:
                    settle_result(fixture, home_goals if home_goals is not None else fixture.home_score, away_goals if away_goals is not None else fixture.away_score)
                    changed = True
            else:
                if fixture.status != new_status:
                    fixture.status = new_status
                    changed = True
                if home_goals is not None and fixture.home_score != home_goals:
                    fixture.home_score = home_goals
                    changed = True
                if away_goals is not None and fixture.away_score != away_goals:
                    fixture.away_score = away_goals
                    changed = True
                
            if changed:
                fixtures_updated += 1
                update_fixture_score(fixture, db)

    db.commit()
    return fixtures_updated, fixtures_finished

def update_results_and_odds(db: Session) -> dict:
    """
    Main daily update task that fetches results for today and yesterday via global API calls,
    updates odds history, recalculates standings, and rebuilds cached feeds.
    """
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    c1, u1 = sync_global_date_results(db, yesterday_str)
    c2, u2 = sync_global_date_results(db, today_str)

    fixtures_created = c1 + c2
    fixtures_updated_results = u1 + u2

    # Fallback to tournament adapters if global date sync did not find/update fixtures
    if fixtures_created == 0 and fixtures_updated_results == 0:
        tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
        for tourney in tournaments:
            adapter = get_format_adapter(tourney.competition.format_engine if tourney.competition else "", tourney.competition.name if tourney.competition else "")
            c, u = adapter.sync_results(db, tourney)
            fixtures_created += c
            fixtures_updated_results += u

    tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
    if not tournaments:
        tournaments = db.query(Tournament).all()

    for tourney in tournaments:
        comp = tourney.competition
        if comp and comp.odds_api_sport_key:
            try:
                tourney_fixtures = db.query(Fixture).filter(Fixture.tournament_id == tourney.id).all()
                update_odds_from_api(tourney_fixtures, db, sport_key=comp.odds_api_sport_key)
            except Exception as e:
                print(f"Warning: Failed to update odds for tournament {tourney.id}: {e}")

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

    simulation_status = "Simulation temporarily disabled"

    try:
        from backend.services.feed_builder import build_fixtures_feed_cache
        build_fixtures_feed_cache(db)
    except Exception as e:
        print(f"Warning: Failed to rebuild feed cache: {e}")

    return {
        "status": "success",
        "fixtures_created": fixtures_created,
        "fixtures_updated_results": fixtures_updated_results,
        "simulation": simulation_status
    }

def update_live_scores(db: Session, force: bool = False) -> dict:
    """
    Lightweight updater for live scores that only queries the API when matches are scheduled or live,
    unless forced. Returns status and counts of updated/finished fixtures.
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
        print("No active match window detected in DB. Skipping live API call.")
        return {"status": "skipped", "message": "No active match window."}
        
    print(f"Active match window detected ({len(active_fixtures)} scheduled soon/ongoing, {len(live_fixtures)} live). Fetching global live scores...")
    
    updated, finished = sync_global_live_scores(db)

    # Fallback to tournament adapters if global sync did not update any fixtures
    if updated == 0 and finished == 0:
        tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
        for tourney in tournaments:
            adapter = get_format_adapter(tourney.competition.format_engine if tourney.competition else "", tourney.competition.name if tourney.competition else "")
            u, f = adapter.sync_live_scores(db, tourney)
            updated += u
            finished += f

    if finished > 0 or updated > 0:
        try:
            propagate_knockout_fixtures(db)
        except Exception as e:
            pass
        db.commit()
        
        tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
        for tourney in tournaments:
            try:
                recalculate_tournament_team_standings(db, tourney.id)
                if tourney.competition and tourney.competition.format_engine == "nations_league":
                    from backend.services.tournament import evaluate_nations_league_promotions
                    evaluate_nations_league_promotions(db, tourney.id)
            except Exception as e:
                pass
        db.commit()

    simulation_status = "Simulation temporarily disabled"

    return {
        "status": "success",
        "fixtures_updated_live": updated,
        "fixtures_finished": finished,
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
