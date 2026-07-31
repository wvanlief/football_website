import os
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.database import Team, Fixture, Tournament, Competition, FixtureOdds, EloHistory
from backend.services.ingestion import NameNormalizer
from backend.services.odds import calculate_default_odds
from backend.services.settling import settle_result
from backend.scoring import update_fixture_score
import backend.ingestor as ingestor_module
import backend.services.updater as updater_module

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
    "1": "America/Mexico_City", "2": "America/Mexico_City", "3": "America/Monterrey",
    "4": "America/Chicago", "5": "America/Chicago", "6": "America/Chicago",
    "7": "America/New_York", "8": "America/New_York", "9": "America/New_York",
    "10": "America/New_York", "11": "America/New_York", "12": "America/Toronto",
    "13": "America/Vancouver", "14": "America/Los_Angeles", "15": "America/Los_Angeles",
    "16": "America/Los_Angeles",
}

LEAGUE_MAPPING = {
    "Premier League": 39
}

def parse_match_date(date_str: str, stadium_id: str) -> datetime:
    """Parses a local date string and stadium ID into a UTC datetime."""
    if not date_str or not isinstance(date_str, str):
        return datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
    try:
        dt_naive = datetime.strptime(date_str, "%m/%d/%Y %H:%M")
        tz_name = STADIUM_TIMEZONES.get(str(stadium_id), "America/New_York")
        dt_localized = dt_naive.replace(tzinfo=ZoneInfo(tz_name))
        return dt_localized.astimezone(timezone.utc)
    except Exception:
        try:
            dt = datetime.strptime(date_str, "%m/%d/%Y %H:%M")
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            return datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)


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

def fetch_json(url: str, use_cache: bool = True) -> list:
    return fetch_json_with_retry(url, use_cache=use_cache)

def fetch_games_with_fallback(use_cache: bool = True) -> tuple[list, bool]:
    is_testing = os.getenv("TESTING") == "True"
    api_key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
    
    if is_testing or not api_key:
        try:
            res = updater_module.fetch_json("https://api.football-data.org/v4/games", use_cache=use_cache)
            if res:
                games = res.get("games") if isinstance(res, dict) else res
                if games and len(games) > 0:
                    return games, False
        except Exception:
            pass
        if not api_key:
            print("No FOOTBALL_API_KEY configured in environment. Skipping API-Sports fetch.")
            return [], False

    fallback_url = "https://v3.football.api-sports.io/fixtures?league=1&season=2026"
    headers = {
        "x-apisports-key": api_key,
        "User-Agent": "Mozilla/5.0"
    }
    try:
        print("Attempting to fetch games from API-Sports (World Cup 2026)...")
        res = updater_module.fetch_json_with_retry(fallback_url, headers=headers, use_cache=use_cache)
        if isinstance(res, dict) and "response" in res:
            fixtures = res["response"]
            if fixtures:
                print(f"Successfully fetched {len(fixtures)} games from API-Sports.")
                converted_games = []
                for f in fixtures:
                    fixture_info = f.get("fixture", {})
                    teams_info = f.get("teams", {})
                    goals_info = f.get("goals", {})
                    league_info = f.get("league", {})
                    
                    status_short = fixture_info.get("status", {}).get("short", "")
                    finished = "TRUE" if status_short in ("FT", "AET", "PEN") else "FALSE"
                    
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
        print(f"API-Sports fetch failed: {e}")

    return [], False



class BaseFormatAdapter:
    """Abstract base adapter for format-specific result and live score updates."""
    def sync_results(self, db: Session, tourney: Tournament) -> tuple[int, int]:
        """Syncs results for a tournament. Returns (fixtures_created, fixtures_updated)."""
        raise NotImplementedError

    def sync_live_scores(self, db: Session, tourney: Tournament) -> tuple[int, int]:
        """Syncs live scores for a tournament. Returns (fixtures_updated_live, fixtures_finished)."""
        raise NotImplementedError

class GroupKnockoutAdapter(BaseFormatAdapter):
    """Adapter for World Cup and group-knockout international tournaments."""
    def sync_results(self, db: Session, tourney: Tournament) -> tuple[int, int]:
        comp = tourney.competition
        normalizer = NameNormalizer()
        now_time = datetime.now(timezone.utc)
        fixtures_created = 0
        fixtures_updated_results = 0

        fetched_matches = []
        is_fallback = False
        try:
            fetched_matches, is_fallback = fetch_games_with_fallback()
        except Exception as e:
            print(f"Error during matches fetch: {e}")
            
        if not fetched_matches:
            print("Failed to fetch matches for World Cup. Skipping.")
            return 0, 0

        fetched_teams = []
        try:
            res_teams = updater_module.fetch_json("https://api.football-data.org/v4/teams")
            fetched_teams = res_teams.get("teams") if isinstance(res_teams, dict) else (res_teams if isinstance(res_teams, list) else [])
        except Exception:
            pass

        external_team_map = {t["id"]: normalizer.normalize(t.get("name_en", "")) for t in fetched_teams} if fetched_teams else {}
        db_teams = db.query(Team).filter(Team.team_type == "National").all()
        db_teams_by_name = {team.name: team for team in db_teams}

        resolved_fixtures = set()
        for m in fetched_matches:
            h_name = external_team_map.get(m.get("home_team_id")) if external_team_map else None
            if not h_name:
                h_name = normalizer.normalize(m.get("home_team_name_en") or m.get("home_team_label") or "")
                
            a_name = external_team_map.get(m.get("away_team_id")) if external_team_map else None
            if not a_name:
                a_name = normalizer.normalize(m.get("away_team_name_en") or m.get("away_team_label") or "")
            
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
                settle_result(fixture, feed_home_score, feed_away_score)
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
        
        try:
            print("Syncing Elo ratings from eloratings.net...")
            live_elo = ingestor_module.fetch_current_elo_ratings()
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

        return fixtures_created, fixtures_updated_results

    def sync_live_scores(self, db: Session, tourney: Tournament) -> tuple[int, int]:
        normalizer = NameNormalizer()
        now_time = datetime.now(timezone.utc)
        fixtures_updated = 0
        fixtures_finished = 0

        fetched_matches = []
        try:
            fetched_matches, _ = fetch_games_with_fallback(use_cache=False)
        except Exception as e:
            print(f"Error fetching live scores: {e}")
            return 0, 0
            
        if not fetched_matches:
            return 0, 0

        external_team_map = {}
        try:
            res_teams = updater_module.fetch_json("https://api.football-data.org/v4/teams")
            fetched_teams = res_teams.get("teams") if isinstance(res_teams, dict) else (res_teams if isinstance(res_teams, list) else [])
            if fetched_teams:
                external_team_map = {t["id"]: normalizer.normalize(t.get("name_en", "")) for t in fetched_teams if isinstance(t, dict) and "id" in t}
        except Exception:
            pass

        db_teams = db.query(Team).filter(Team.team_type == "National").all()
        db_teams_by_name = {team.name: team for team in db_teams}
        
        for m in fetched_matches:
            h_name = external_team_map.get(m.get("home_team_id")) if external_team_map else normalizer.normalize(m.get("home_team_name_en") or m.get("home_team_label") or "")
            a_name = external_team_map.get(m.get("away_team_id")) if external_team_map else normalizer.normalize(m.get("away_team_name_en") or m.get("away_team_label") or "")
            
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
                
            if not fixture or fixture.status == "Finished":
                continue
                
            is_finished_in_feed = m.get("finished") == "TRUE"
            feed_home_score = int(m["home_score"]) if m.get("home_score") not in (None, 'null') else None
            feed_away_score = int(m["away_score"]) if m.get("away_score") not in (None, 'null') else None
            
            if is_finished_in_feed:
                settle_result(fixture, feed_home_score, feed_away_score)
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

        return fixtures_updated, fixtures_finished

class LeagueFormatAdapter(BaseFormatAdapter):
    """Adapter for domestic leagues (API-Football / Football-Data.org)."""
    def sync_results(self, db: Session, tourney: Tournament) -> tuple[int, int]:
        comp = tourney.competition
        now_time = datetime.now(timezone.utc)
        fixtures_created = 0
        fixtures_updated_results = 0

        league_id = comp.api_league_id
        if not league_id:
            league_id = LEAGUE_MAPPING.get(comp.name, 39)

        try:
            api_season = int(tourney.season_name)
        except ValueError:
            api_season = 2026
            
        print(f"Fetching fixtures from API-Football for league={league_id}, season={api_season}...")
        try:
            res = updater_module.call_football_api("fixtures", {"league": league_id, "season": api_season})
        except Exception as e:
            print(f"Error calling football API for league fixtures: {e}")
            return 0, 0
            
        if not isinstance(res, dict) or "response" not in res:
            print(f"Invalid API response for league fixtures: {res}")
            return 0, 0
            
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
                
            if fixture.status != "Finished" and status == "Finished":
                settle_result(fixture, feed_home_score, feed_away_score)
                fixtures_updated_results += 1
            elif fixture.status != "Finished":
                fixture.status = status
                fixture.home_score = feed_home_score
                fixture.away_score = feed_away_score

        try:
            last_club_sync = db.query(EloHistory).join(Team).filter(Team.elo_source == "clubelo").order_by(EloHistory.recorded_at.desc()).first()
            if not last_club_sync or last_club_sync.recorded_at.date() < now_time.date():
                print("Syncing Elo ratings from ClubElo...")
                club_ratings = updater_module.fetch_clubelo_ratings()
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

        return fixtures_created, fixtures_updated_results

    def sync_live_scores(self, db: Session, tourney: Tournament) -> tuple[int, int]:
        normalizer = NameNormalizer()
        fixtures_updated = 0
        fixtures_finished = 0

        api_key = os.getenv("FOOTBALL_DATA_API_KEY")
        if not api_key:
            print("Warning: FOOTBALL_DATA_API_KEY is not configured in the environment. Skipping live scores.")
            return 0, 0
            
        print("Fetching live matches from Football-Data.org...")
        url = "https://api.football-data.org/v4/matches"
        headers = {"X-Auth-Token": api_key}
        try:
            res = updater_module.fetch_json_with_retry(url, headers=headers, use_cache=False)
        except Exception as e:
            print(f"Error fetching live scores from Football-Data.org: {e}")
            return 0, 0
            
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
                    if normalizer.match_names(f.home_team.name, api_home) and normalizer.match_names(f.away_team.name, api_away):
                        matching_fixture = f
                        break
                        
            if not matching_fixture:
                continue
                
            score_info = m.get("score", {}).get("fullTime", {})
            feed_home_score = score_info.get("home")
            feed_away_score = score_info.get("away")
            
            if api_status == "FINISHED":
                settle_result(matching_fixture, feed_home_score, feed_away_score)
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

        return fixtures_updated, fixtures_finished

def get_format_adapter(format_engine: str, competition_name: str = "") -> BaseFormatAdapter:
    """Factory method resolving the format engine or competition name to the appropriate adapter."""
    if format_engine == "league" or "Premier League" in competition_name:
        return LeagueFormatAdapter()
    return GroupKnockoutAdapter()
