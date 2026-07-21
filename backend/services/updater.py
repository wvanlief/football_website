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
    Team, Fixture, Tournament, Competition, TournamentTeam, FixtureOdds, EloHistory, get_db
)
from backend.scoring import update_fixture_score
from backend.ingestor import (
    normalize_team_name, calculate_default_odds, update_odds_from_api,
    call_football_api, fetch_clubelo_ratings
)
from backend.services.tournament import propagate_knockout_fixtures
from backend.services.simulation import run_monte_carlo_simulation

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
    """
    Recalculates win/draw/loss streaks for all teams based on finished fixtures in chronological order.
    # TODO: Recalculating all finished fixtures crosses tournament boundaries.
    # Consider whether streaks should be tournament-scoped or global in a future iteration.
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


from backend.utils import fetch_json_with_retry

def fetch_json(url: str, use_cache: bool = True) -> list:
    """Helper to fetch JSON content from a URL."""
    return fetch_json_with_retry(url, use_cache=use_cache)

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

def fetch_games_with_fallback(use_cache: bool = True) -> tuple[list, bool]:
    """
    Fetches games list. Returns a tuple: (fetched_matches_list, is_fallback_used).
    Attempts to fetch from primary URL first, and if it fails or returns no matches,
    falls back to API-Sports.
    """
    primary_url = "https://worldcup26.ir/get/games"
    try:
        print("Attempting to fetch games from primary live scoring API...")
        res = fetch_json(primary_url, use_cache=use_cache)
        if res:
            games = res.get("games") if isinstance(res, dict) else res
            if games and len(games) > 0:
                print(f"Successfully fetched {len(games)} games from primary API.")
                return games, False
    except Exception as e:
        print(f"Primary live scoring API failed: {e}")

    # Fallback to API-Sports / API-Football
    api_key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
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
        res = fetch_json_with_retry(fallback_url, headers=headers, use_cache=use_cache)
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
                            dt_utc = datetime.fromisoformat(api_date.replace('Z', '+00:00'))
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
    Main update task. Loops through all active tournaments and updates their
    schedules/results, odds, and ELO ratings.
    """
    tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
    if not tournaments:
        tournaments = db.query(Tournament).all()
    if not tournaments:
        return {"status": "error", "message": "No tournaments found in DB. Please run database seeding first."}

    fixtures_created = 0
    fixtures_updated_results = 0
    now_time = datetime.now(timezone.utc)
    
    # Mapping of competition names to API-Football league IDs
    LEAGUE_MAPPING = {
        "Premier League": 39
    }

    for tourney in tournaments:
        comp = tourney.competition
        print(f"Updating tournament: {comp.name} ({tourney.season_name})")

        # 1. World Cup / International Tournament Logic
        # TODO: Remove name fallbacks once confident in format_engine
        if comp.format_engine == "group_knockout" or "World Cup" in comp.name:

            fetched_matches = []
            is_fallback = False
            try:
                fetched_matches, is_fallback = fetch_games_with_fallback()
            except Exception as e:
                print(f"Error during matches fetch: {e}")
                
            if not fetched_matches:
                print(f"Failed to fetch matches for World Cup. Skipping.")
                continue

            fetched_teams = []
            if not is_fallback:
                try:
                    teams_url = "https://worldcup26.ir/get/teams"
                    res_teams = fetch_json(teams_url)
                    fetched_teams = res_teams.get("teams") if isinstance(res_teams, dict) else res_teams
                except Exception as e:
                    print(f"Warning: Failed to fetch team definitions: {e}. Name matching will be used.")

            external_team_map = {t["id"]: normalize_team_name(t.get("name_en", "")) for t in fetched_teams} if fetched_teams else {}
            db_teams = db.query(Team).filter(Team.team_type == "National").all()
            db_teams_by_name = {team.name: team for team in db_teams}

            resolved_fixtures = set()
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
                    
                is_finished_in_feed = m.get("finished") == "TRUE"
                feed_home_score = int(m["home_score"]) if is_finished_in_feed and m.get("home_score") not in (None, 'null') else None
                feed_away_score = int(m["away_score"]) if is_finished_in_feed and m.get("away_score") not in (None, 'null') else None
                
                if not fixture:
                    h_elo = home_team.elo if home_team else 1700
                    a_elo = away_team.elo if away_team else 1700
                    odds_h, odds_d, odds_a = calculate_default_odds(h_elo, a_elo, neutral_venue=comp.neutral_venue, home_advantage=comp.home_advantage_elo or 100)

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
                    
                    init_odds = FixtureOdds(
                        fixture_id=fixture.id,
                        recorded_at=dt_utc - timedelta(days=2),
                        odds_home=odds_h,
                        odds_draw=odds_d,
                        odds_away=odds_a
                    )
                    db.add(init_odds)
                    fixtures_created += 1
                    
                if home_team and fixture.home_team_id is None:
                    fixture.home_team_id = home_team.id
                    fixture.home_team_placeholder = None
                    resolved_fixtures.add(fixture)
                if away_team and fixture.away_team_id is None:
                    fixture.away_team_id = away_team.id
                    fixture.away_team_placeholder = None
                    resolved_fixtures.add(fixture)
                    
                if fixture.status != "Finished" and is_finished_in_feed:
                    fixture.status = "Finished"
                    fixture.home_score = feed_home_score
                    fixture.away_score = feed_away_score
                    
                    if home_team and away_team:
                        fixture.home_team_id = home_team.id
                        fixture.away_team_id = away_team.id
                        fixture.home_team_placeholder = None
                        fixture.away_team_placeholder = None
                        
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
                        
                        db.add(EloHistory(team_id=home_team.id, recorded_at=now_time, elo_rating=home_elo_new))
                        db.add(EloHistory(team_id=away_team.id, recorded_at=now_time, elo_rating=away_elo_new))
                        
                    fixtures_updated_results += 1
                    
            if resolved_fixtures:
                for fixture in resolved_fixtures:
                    h_elo = fixture.home_team.elo if fixture.home_team else 1700
                    a_elo = fixture.away_team.elo if fixture.away_team else 1700
                    odds_h, odds_d, odds_a = calculate_default_odds(h_elo, a_elo, neutral_venue=comp.neutral_venue, home_advantage=comp.home_advantage_elo or 100)

                    db_odds = FixtureOdds(
                        fixture_id=fixture.id,
                        recorded_at=now_time,
                        odds_home=odds_h,
                        odds_draw=odds_d,
                        odds_away=odds_a
                    )
                    db.add(db_odds)
            
            # Sync national teams Elo
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
                        db.add(EloHistory(team_id=team.id, recorded_at=now_time, elo_rating=fetched_elo))
                        teams_updated += 1
                print(f"Successfully synced national Elo ratings. Updated {teams_updated} teams.")
            except Exception as e:
                print(f"Warning: Failed to sync Elo ratings: {e}")

        # 2. Domestic Leagues Logic (API-Football)
        # TODO: Remove name fallbacks once confident in format_engine
        elif comp.format_engine == "league" or "Premier League" in comp.name:

            league_id = comp.api_league_id
            if not league_id:
                league_id = LEAGUE_MAPPING.get(comp.name, 39)

            try:
                api_season = int(tourney.season_name)
            except ValueError:
                api_season = 2026
                
            print(f"Fetching fixtures from API-Football for league={league_id}, season={api_season}...")
            try:
                res = call_football_api("fixtures", {"league": league_id, "season": api_season})
            except Exception as e:
                print(f"Error calling football API for league fixtures: {e}")
                continue
                
            if not isinstance(res, dict) or "response" not in res:
                print(f"Invalid API response for league fixtures: {res}")
                continue
                
            fixtures_data = res["response"]
            print(f"Syncing {len(fixtures_data)} league fixtures...")

            for item in fixtures_data:
                f_info = item.get("fixture", {})
                t_info = item.get("teams", {})
                goals = item.get("goals", {})
                league_info = item.get("league", {})
                
                api_id = str(f_info.get("id"))
                date_utc_str = f_info.get("date")
                date_utc = datetime.fromisoformat(date_utc_str.replace('Z', '+00:00'))
                round_str = league_info.get("round", "")
                
                matchday_number = None
                if round_str and "Regular Season" in round_str:
                    try:
                        matchday_number = int(round_str.split("-")[-1].strip())
                    except ValueError:
                        pass
                        
                h_api_id = t_info.get("home", {}).get("id")
                a_api_id = t_info.get("away", {}).get("id")
                
                home_team = db.query(Team).filter(Team.api_id == h_api_id).first()
                away_team = db.query(Team).filter(Team.api_id == a_api_id).first()
                
                stage = "Regular Season"
                status_short = f_info.get("status", {}).get("short", "")
                status = "Scheduled"
                if status_short in ("FT", "AET", "PEN"):
                    status = "Finished"
                elif status_short in ("1H", "2H", "HT", "ET", "P", "LIVE"):
                    status = "Live"
                    
                feed_home_score = goals.get("home")
                feed_away_score = goals.get("away")
                
                fixture = db.query(Fixture).filter(
                    Fixture.tournament_id == tourney.id,
                    Fixture.api_id == api_id
                ).first()
                
                if not fixture:
                    h_elo = home_team.elo if home_team else 1700
                    a_elo = away_team.elo if away_team else 1700
                    odds_h, odds_d, odds_a = calculate_default_odds(h_elo, a_elo, neutral_venue=comp.neutral_venue, home_advantage=comp.home_advantage_elo or 100)

                    fixture = Fixture(
                        tournament_id=tourney.id,
                        home_team_id=home_team.id if home_team else None,
                        away_team_id=away_team.id if away_team else None,
                        api_id=api_id,
                        date_utc=date_utc,
                        stage=stage,
                        matchday_number=matchday_number,
                        status=status,
                        home_score=feed_home_score,
                        away_score=feed_away_score,
                        winner_id=None
                    )
                    db.add(fixture)
                    db.flush()
                    
                    init_odds = FixtureOdds(
                        fixture_id=fixture.id,
                        recorded_at=date_utc - timedelta(days=2),
                        odds_home=odds_h,
                        odds_draw=odds_d,
                        odds_away=odds_a
                    )
                    db.add(init_odds)
                    fixtures_created += 1
                else:
                    fixture.date_utc = date_utc
                    fixture.matchday_number = matchday_number
                    
                # Update status and scores
                if fixture.status != "Finished" and status == "Finished":
                    fixture.status = "Finished"
                    fixture.home_score = feed_home_score
                    fixture.away_score = feed_away_score
                    
                    if home_team and away_team:
                        fixture.home_team_id = home_team.id
                        fixture.away_team_id = away_team.id
                        
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
                        
                        db.add(EloHistory(team_id=home_team.id, recorded_at=now_time, elo_rating=home_elo_new))
                        db.add(EloHistory(team_id=away_team.id, recorded_at=now_time, elo_rating=away_elo_new))
                        
                    fixtures_updated_results += 1
                elif fixture.status != "Finished":
                    fixture.status = status
                    fixture.home_score = feed_home_score
                    fixture.away_score = feed_away_score

            # Sync ClubElo ratings once a day
            try:
                last_club_sync = db.query(EloHistory).join(Team).filter(Team.elo_source == "clubelo").order_by(EloHistory.recorded_at.desc()).first()
                if not last_club_sync or last_club_sync.recorded_at.date() < now_time.date():
                    print("Syncing Elo ratings from ClubElo...")
                    club_ratings = fetch_clubelo_ratings()
                    if club_ratings:
                        review_path = "backend/data/elo_name_review.json"
                        if os.path.exists(review_path):
                            with open(review_path, "r", encoding="utf-8") as f:
                                mappings = json.load(f)
                            name_map = {m["api_football_name"]: m["clubelo_name"] for m in mappings}
                        else:
                            name_map = {}

                        db_club_teams = db.query(Team).filter(Team.elo_source == "clubelo").all()
                        teams_updated = 0
                        for team in db_club_teams:
                            clubelo_name = name_map.get(team.name, team.name)
                            fetched_elo = club_ratings.get(clubelo_name)
                            if fetched_elo is not None and team.elo != fetched_elo:
                                team.elo = fetched_elo
                                team.form_score = round(min(95.0, max(45.0, 50.0 + (fetched_elo - 1500) * 0.05)), 1)
                                db.add(EloHistory(team_id=team.id, recorded_at=now_time, elo_rating=fetched_elo))
                                teams_updated += 1
                        print(f"Successfully synced ClubElo ratings. Updated {teams_updated} teams.")
            except Exception as e:
                print(f"Warning: Failed to sync ClubElo ratings: {e}")

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

def matches_team_name(db_name: str, api_name: str) -> bool:
    if not db_name or not api_name:
        return False
    db_lower = db_name.lower().strip()
    api_lower = api_name.lower().strip()
    
    if db_lower in api_lower or api_lower in db_lower:
        return True
        
    # Handle Wolverhampton / Wolves special case
    if "wolves" in db_lower and "wolverhampton" in api_lower:
        return True
    if "wolverhampton" in db_lower and "wolves" in api_lower:
        return True
        
    # Handle Nottingham Forest / Forest
    if "nottingham" in db_lower and "forest" in api_lower:
        return True
        
    return False

def update_live_scores(db: Session, force: bool = False) -> dict:
    """
    Lightweight updater for live scores. Only queries when matches are scheduled/live.
    """
    now_time = datetime.now(timezone.utc)
    
    # Check if we have active match windows across all active tournaments
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
        
        # 1. World Cup / International Tournament Logic
        # TODO: Remove name fallbacks once confident in format_engine
        if comp.format_engine == "group_knockout" or "World Cup" in comp.name:

            fetched_matches = []
            try:
                fetched_matches, _ = fetch_games_with_fallback(use_cache=False)
            except Exception as e:
                print(f"Error fetching live scores: {e}")
                continue
                
            if not fetched_matches:
                continue

            external_team_map = {}
            try:
                teams_url = "https://worldcup26.ir/get/teams"
                res_teams = fetch_json(teams_url)
                fetched_teams = res_teams.get("teams") if isinstance(res_teams, dict) else res_teams
                external_team_map = {t["id"]: normalize_team_name(t.get("name_en", "")) for t in fetched_teams}
            except Exception as e:
                pass

            db_teams = db.query(Team).filter(Team.team_type == "National").all()
            db_teams_by_name = {team.name: team for team in db_teams}
            
            for m in fetched_matches:
                h_name = external_team_map.get(m.get("home_team_id")) if external_team_map else normalize_team_name(m.get("home_team_name_en") or m.get("home_team_label") or "")
                a_name = external_team_map.get(m.get("away_team_id")) if external_team_map else normalize_team_name(m.get("away_team_name_en") or m.get("away_team_label") or "")
                
                home_team = db_teams_by_name.get(h_name)
                away_team = db_teams_by_name.get(a_name)
                
                api_match_id = str(m.get("id"))
                fixture = db.query(Fixture).filter(
                    Fixture.tournament_id == tourney.id,
                    Fixture.api_id == api_match_id
                ).first()
                
                if not fixture and home_team and away_team:
                    stage = STAGE_MAPPING.get(m.get("type"), "Group Stage")
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
                    
                if fixture.status == "Finished":
                    continue
                    
                is_finished_in_feed = m.get("finished") == "TRUE"
                feed_home_score = int(m["home_score"]) if m.get("home_score") not in (None, 'null') else None
                feed_away_score = int(m["away_score"]) if m.get("away_score") not in (None, 'null') else None
                
                if is_finished_in_feed:
                    fixture.status = "Finished"
                    fixture.home_score = feed_home_score
                    fixture.away_score = feed_away_score
                    
                    if home_team and away_team:
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
                        db.add(EloHistory(team_id=home_team.id, recorded_at=now_time, elo_rating=home_elo_new))
                        db.add(EloHistory(team_id=away_team.id, recorded_at=now_time, elo_rating=away_elo_new))
                        update_fixture_score(fixture, db)
                        
                    fixtures_finished += 1
                else:
                    f_date_aware = fixture.date_utc.replace(tzinfo=timezone.utc) if fixture.date_utc.tzinfo is None else fixture.date_utc
                    is_in_progress = (f_date_aware - timedelta(minutes=5)) <= now_time <= (f_date_aware + timedelta(hours=3))
                    
                    if is_in_progress and feed_home_score is not None and feed_away_score is not None:
                        fixture.status = "Live"
                        fixture.home_score = feed_home_score
                        fixture.away_score = feed_away_score
                        fixtures_updated += 1
                    else:
                        fixture.status = "Scheduled"
                        fixture.home_score = None
                        fixture.away_score = None

        # 2. Domestic Leagues Logic (Football-Data.org)
        # TODO: Remove name fallbacks once confident in format_engine
        elif comp.format_engine == "league" or "Premier League" in comp.name:

            api_key = os.getenv("FOOTBALL_DATA_API_KEY")
            if not api_key:
                print("Warning: FOOTBALL_DATA_API_KEY is not configured in the environment. Skipping live scores.")
                continue
                
            print("Fetching live matches from Football-Data.org...")
            url = "https://api.football-data.org/v4/matches"
            headers = {"X-Auth-Token": api_key}
            try:
                res = fetch_json_with_retry(url, headers=headers, use_cache=False)
            except Exception as e:
                print(f"Error fetching live scores from Football-Data.org: {e}")
                continue
                
            api_matches = res.get("matches", [])
            print(f"Football-Data.org returned {len(api_matches)} matches today.")
            
            db_tourney_fixtures = db.query(Fixture).filter(
                Fixture.tournament_id == tourney.id,
                Fixture.status != "Finished"
            ).all()
            
            for m in api_matches:
                api_home = m.get("homeTeam", {}).get("name")
                api_away = m.get("awayTeam", {}).get("name")
                api_status = m.get("status")
                
                matching_fixture = None
                for f in db_tourney_fixtures:
                    if f.home_team and f.away_team:
                        if matches_team_name(f.home_team.name, api_home) and matches_team_name(f.away_team.name, api_away):
                            matching_fixture = f
                            break
                            
                if not matching_fixture:
                    continue
                    
                score_info = m.get("score", {}).get("fullTime", {})
                feed_home_score = score_info.get("home")
                feed_away_score = score_info.get("away")
                
                home_team = matching_fixture.home_team
                away_team = matching_fixture.away_team
                
                if api_status == "FINISHED":
                    matching_fixture.status = "Finished"
                    matching_fixture.home_score = feed_home_score
                    matching_fixture.away_score = feed_away_score
                    
                    if home_team and away_team:
                        if feed_home_score > feed_away_score:
                            outcome = 1.0
                            matching_fixture.winner_id = home_team.id
                        elif feed_home_score < feed_away_score:
                            outcome = 0.0
                            matching_fixture.winner_id = away_team.id
                        else:
                            outcome = 0.5
                            matching_fixture.winner_id = None
                            
                        home_elo_old = home_team.elo
                        away_elo_old = away_team.elo
                        home_elo_new, away_elo_new = calculate_elo_updates(home_elo_old, away_elo_old, outcome)
                        
                        home_team.elo = home_elo_new
                        away_team.elo = away_elo_new
                        update_team_streaks_and_form(home_team, away_team, outcome)
                        db.add(EloHistory(team_id=home_team.id, recorded_at=now_time, elo_rating=home_elo_new))
                        db.add(EloHistory(team_id=away_team.id, recorded_at=now_time, elo_rating=away_elo_new))
                        update_fixture_score(matching_fixture, db)
                        
                    fixtures_finished += 1
                elif api_status in ("IN_PLAY", "PAUSED"):
                    matching_fixture.status = "Live"
                    matching_fixture.home_score = feed_home_score
                    matching_fixture.away_score = feed_away_score
                    fixtures_updated += 1
                else:
                    matching_fixture.status = "Scheduled"
                    matching_fixture.home_score = None
                    matching_fixture.away_score = None
                    
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

