import os
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from backend.database import (
    Team, Player, Fixture, Competition, Tournament, 
    TournamentTeam, PlayerContract, FixtureOdds, PlayerMatchStat, EloHistory
)
from backend.scoring import update_fixture_score
from backend.utils import fetch_url_with_retry, fetch_json_with_retry
from backend.services.ingestion import CacheAdapter, NameNormalizer, COUNTRY_ISO_MAP

NATIONAL_TEAM_ISO_CODES = COUNTRY_ISO_MAP


# Load environment variables
load_dotenv()

ELO_RATINGS = {
    "Spain": 2165, "Argentina": 2113, "France": 2082, "England": 2020,
    "Brazil": 1984, "Portugal": 1984, "Colombia": 1975, "Netherlands": 1961,
    "Germany": 1923, "Norway": 1912, "Japan": 1904, "Turkey": 1902,
    "Uruguay": 1892, "Switzerland": 1889, "Senegal": 1878, "Mexico": 1858,
    "USA": 1721, "Canada": 1784, "Morocco": 1821, "Algeria": 1743,
    "Croatia": 1930, "Ecuador": 1933, "Austria": 1827, "Paraguay": 1833,
    "South Korea": 1752, "Australia": 1783, "Scotland": 1767,
    "Iran": 1760, "Uzbekistan": 1727, "Qatar": 1600,
    "South Africa": 1650, "Haiti": 1550, "Curaçao": 1500, "Cape Verde": 1580,
    "Panama": 1737, "Ghana": 1680, "New Zealand": 1550, "Jordan": 1690,
    "Czechia": 1830,
    "Bosnia and Herzegovina": 1720,
    "Côte d'Ivoire": 1800,
    "Tunisia": 1750,
    "Poland": 1820,
    "Belgium": 1960,
    "Egypt": 1780,
    "Saudi Arabia": 1710,
    "Iraq": 1700,
    "Jamaica": 1680,
}

GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czechia"],
    "B": ["Canada", "Switzerland", "Qatar", "Bosnia and Herzegovina"],
    "C": ["Brazil", "Morocco", "Scotland", "Haiti"],
    "D": ["USA", "Paraguay", "Australia", "Turkey"],
    "E": ["Germany", "Ecuador", "Curaçao", "Côte d'Ivoire"],
    "F": ["Netherlands", "Japan", "Tunisia", "Poland"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Uruguay", "Saudi Arabia", "Cape Verde"],
    "I": ["France", "Senegal", "Norway", "Iraq"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "Colombia", "Uzbekistan", "Jamaica"],
    "L": ["England", "Croatia", "Panama", "Ghana"],
}

SPOTLIGHT_PLAYERS = {
    "Germany": [("Florian Wirtz", "Midfielder", 93.5), ("Jamal Musiala", "Midfielder", 91.0)],
    "Ecuador": [("Moisés Caicedo", "Midfielder", 84.0), ("Piero Hincapié", "Defender", 81.5)],
    "France": [("Kylian Mbappé", "Forward", 95.0), ("Antoine Griezmann", "Forward", 82.0)],
    "Spain": [("Lamine Yamal", "Forward", 94.5), ("Rodri", "Midfielder", 92.0)],
    "Uruguay": [("Federico Valverde", "Midfielder", 88.0), ("Darwin Núñez", "Forward", 82.0)],
    "Brazil": [("Vinícius Júnior", "Forward", 94.0), ("Rodrygo", "Forward", 85.5)],
    "Morocco": [("Achraf Hakimi", "Defender", 86.5), ("Brahim Díaz", "Midfielder", 89.0)],
    "Portugal": [("Cristiano Ronaldo", "Forward", 81.0), ("Bruno Fernandes", "Midfielder", 89.5)],
    "Colombia": [("Luis Díaz", "Forward", 91.0), ("James Rodríguez", "Midfielder", 86.0)],
    "England": [("Jude Bellingham", "Midfielder", 94.0), ("Harry Kane", "Forward", 89.0)],
    "Croatia": [("Luka Modrić", "Midfielder", 81.0), ("Joško Gvardiol", "Defender", 87.5)],
    "Argentina": [("Lionel Messi", "Forward", 92.5), ("Alexis Mac Allister", "Midfielder", 87.0)],
    "Netherlands": [("Cody Gakpo", "Forward", 83.5), ("Virgil van Dijk", "Defender", 86.0)],
    "Japan": [("Kaoru Mitoma", "Forward", 88.0), ("Takefusa Kubo", "Midfielder", 87.0)],
    "USA": [("Christian Pulisic", "Forward", 85.0), ("Weston McKennie", "Midfielder", 79.5)],
    "Turkey": [("Arda Güler", "Midfielder", 89.0), ("Hakan Çalhanoğlu", "Midfielder", 85.0)],
    "Belgium": [("Kevin De Bruyne", "Midfielder", 91.5), ("Romelu Lukaku", "Forward", 83.0)],
    "Norway": [("Erling Haaland", "Forward", 94.0), ("Martin Ødegaard", "Midfielder", 92.5)],
}

def normalize_team_name(name: str) -> str:
    name = name.strip()
    mapping = {
        "Czech Republic": "Czechia",
        "United States": "USA",
        "Bosnia & Herzegovina": "Bosnia and Herzegovina",
        "Bosnia & Herzegov.": "Bosnia and Herzegovina",
        "Bosnia & Herz.": "Bosnia and Herzegovina",
        "Cote d'Ivoire": "Côte d'Ivoire",
        "Ivory Coast": "Côte d'Ivoire",
        "Curaçao": "Curaçao",
        "Curacao": "Curaçao"
    }
    return mapping.get(name, name)

def fetch_current_elo_ratings() -> dict[str, int]:
    """
    Fetches the current Elo ratings of international football teams from eloratings.net.
    Returns:
        dict: A dictionary mapping normalized team names to their current Elo ratings as integers.
    """
    teams_url = "https://www.eloratings.net/en.teams.tsv"
    world_url = "https://www.eloratings.net/World.tsv"
    
    # 1. Fetch team mapping
    teams_content = fetch_url_with_retry(teams_url).decode('utf-8')
        
    code_to_name = {}
    for line in teams_content.split('\n'):
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            code = parts[0].strip()
            name = parts[1].strip()
            code_to_name[code] = normalize_team_name(name)
            
    # 2. Fetch World Elo ratings
    world_content = fetch_url_with_retry(world_url).decode('utf-8')
        
    parsed_ratings = {}
    for line in world_content.split('\n'):
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) >= 4:
            code = parts[2].strip()
            elo_str = parts[3].strip().replace('\u2212', '-')
            try:
                elo = int(elo_str)
                name = code_to_name.get(code)
                if name:
                    parsed_ratings[name] = elo
            except ValueError:
                pass
                
    return parsed_ratings

def get_fallback_matches():
    base_date = datetime(2026, 6, 11, 12, 0, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(ZoneInfo("UTC"))
    return [
        {
            "id": "1", "home": "Mexico", "away": "South Africa", "stage": "Group Stage",
            "date": base_date.isoformat(), "status": "Scheduled"
        },
        {
            "id": "2", "home": "South Korea", "away": "Czechia", "stage": "Group Stage",
            "date": (base_date + timedelta(hours=7)).isoformat(), "status": "Scheduled"
        },
        {
            "id": "3", "home": "Canada", "away": "Bosnia and Herzegovina", "stage": "Group Stage",
            "date": (base_date + timedelta(days=1, hours=3)).isoformat(), "status": "Scheduled"
        },
        {
            "id": "4", "home": "Qatar", "away": "Switzerland", "stage": "Group Stage",
            "date": (base_date + timedelta(days=2)).isoformat(), "status": "Scheduled"
        },
        {
            "id": "5", "home": "Germany", "away": "Ecuador", "stage": "Group Stage",
            "date": (base_date + timedelta(days=2, hours=6)).isoformat(), "status": "Scheduled"
        },
        {
            "id": "6", "home": "Brazil", "away": "Morocco", "stage": "Group Stage",
            "date": (base_date + timedelta(days=3)).isoformat(), "status": "Scheduled"
        },
        {
            "id": "7", "home": "Spain", "away": "Uruguay", "stage": "Group Stage",
            "date": (base_date + timedelta(days=4, hours=4)).isoformat(), "status": "Scheduled"
        },
        {
            "id": "8", "home": "Portugal", "away": "Colombia", "stage": "Group Stage",
            "date": (base_date + timedelta(days=5)).isoformat(), "status": "Scheduled"
        },
        {
            "id": "9", "home": "England", "away": "Croatia", "stage": "Group Stage",
            "date": (base_date + timedelta(days=6)).isoformat(), "status": "Scheduled"
        }
    ]

def calculate_default_odds(home_elo, away_elo, neutral_venue: bool = True, home_advantage: int = 100):
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
    if not sport_key:
        print("Odds API sport key is None. Skipping Odds API update.")
        return
    api_key = os.getenv("THE_ODDS_API_KEY")
    if not api_key:
        print("No THE_ODDS_API_KEY found in environment. Skipping Odds API update.")
        return
        
    print(f"Fetching odds from The Odds API for {sport_key}...")
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={api_key}&regions=eu&markets=h2h"
    try:
        odds_data = fetch_json_with_retry(url)
            
        odds_lookup = {}
        for match in odds_data:
            home = normalize_team_name(match.get("home_team", ""))
            away = normalize_team_name(match.get("away_team", ""))
            
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
                h_odds = next(o["price"] for o in outcomes if normalize_team_name(o["name"]) == home)
                a_odds = next(o["price"] for o in outcomes if normalize_team_name(o["name"]) == away)
                d_odds = next(o["price"] for o in outcomes if o["name"].lower() == "draw")
                
                odds_lookup[(home, away)] = (h_odds, d_odds, a_odds)
            except Exception as ex:
                pass
                
        # Update matching fixtures (appending to odds history)
        count = 0
        now_time = datetime.now(timezone.utc)
        for f in fixtures:
            # Skip placeholders
            if not f.home_team or not f.away_team:
                continue
            # Load relationships eagerly in case they are not loaded
            home_name = f.home_team.name
            away_name = f.away_team.name
            key = (home_name, away_name)
            rev_key = (away_name, home_name)
            
            odds_found = None
            if key in odds_lookup:
                odds_found = odds_lookup[key]
            elif rev_key in odds_lookup:
                # swap home and away odds
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

NATIONAL_TEAM_ISO_CODES = {
    "Spain": "ESP",
    "Argentina": "ARG",
    "France": "FRA",
    "England": "ENG",
    "Brazil": "BRA",
    "Portugal": "PRT",
    "Colombia": "COL",
    "Netherlands": "NLD",
    "Germany": "DEU",
    "Norway": "NOR",
    "Japan": "JPN",
    "Turkey": "TUR",
    "Uruguay": "URY",
    "Switzerland": "CHE",
    "Senegal": "SEN",
    "Mexico": "MEX",
    "USA": "USA",
    "Canada": "CAN",
    "Morocco": "MAR",
    "Algeria": "DZA",
    "Croatia": "HRV",
    "Ecuador": "ECU",
    "Austria": "AUT",
    "Paraguay": "PRY",
    "South Korea": "KOR",
    "Australia": "AUS",
    "Scotland": "SCO",
    "Iran": "IRN",
    "Uzbekistan": "UZB",
    "Qatar": "QAT",
    "South Africa": "ZAF",
    "Haiti": "HTI",
    "Curaçao": "CUW",
    "Cape Verde": "CPV",
    "Panama": "PAN",
    "Ghana": "GHA",
    "New Zealand": "NZL",
    "Jordan": "JOR",
    "Czechia": "CZE",
    "Bosnia and Herzegovina": "BIH",
    "Côte d'Ivoire": "CIV",
    "Tunisia": "TUN",
    "Poland": "POL",
    "Belgium": "BEL",
    "Egypt": "EGY",
    "Saudi Arabia": "SAU",
    "Iraq": "IRQ",
    "Jamaica": "JAM",
}

def seed_database(db: Session):
    """
    Seeds database using actual World Cup 2026 schedules from GitHub, falling back to mock fixtures if offline.
    """
    # 1. Clear World Cup competition and associated data in proper dependency order
    comp = db.query(Competition).filter_by(name="FIFA World Cup").first()
    if comp:
        db.delete(comp)
        db.commit()
        
    # Clear national teams and their associated history/contracts/tournament associations
    db.query(Team).filter(Team.team_type == "National").delete()
    db.commit()
    
    # Clean up orphaned players (who have no contracts left)
    active_player_ids = db.query(PlayerContract.player_id).subquery()
    db.query(Player).filter(~Player.id.in_(active_player_ids)).delete(synchronize_session=False)
    db.commit()

    # 1.5 Create Competition and Tournament
    comp = Competition(
        name="FIFA World Cup",
        type="International",
        format_engine="group_knockout",
        odds_api_sport_key="soccer_fifa_world_cup",
        home_advantage_elo=0,
        neutral_venue=True
    )
    db.add(comp)
    db.flush()
    
    tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
    db.add(tourney)
    db.flush()

    # 2. Add Teams
    team_map = {}
    
    # Fetch live Elo ratings from eloratings.net, fallback to hardcoded ELO_RATINGS
    try:
        print("Fetching live Elo ratings from eloratings.net...")
        live_elo = fetch_current_elo_ratings()
        print(f"Successfully fetched {len(live_elo)} Elo ratings from eloratings.net.")
    except Exception as e:
        print(f"Failed to fetch live Elo ratings: {e}. Falling back to hardcoded dictionary.")
        live_elo = ELO_RATINGS

    # Try fetching real teams list from GitHub
    fetched_teams = []
    try:
        print("Fetching team definitions from API...")
        teams_url = "https://worldcup26.ir/get/teams"
        res_teams = fetch_json_with_retry(teams_url)
        fetched_teams = res_teams.get("teams") if isinstance(res_teams, dict) else res_teams
        print(f"Fetched {len(fetched_teams)} team definitions.")
    except Exception as e:
        print(f"Failed to fetch team definitions: {e}. Seeding using fallback groups.")

    if fetched_teams:
        for t in fetched_teams:
            name = normalize_team_name(t.get("name_en", ""))
            group = t.get("groups", "")
            
            elo = live_elo.get(name, 1700)
            form_score = min(95.0, max(45.0, 50.0 + (elo - 1500) * 0.05))
            
            win_streak = 0
            if elo > 2000:
                win_streak = 4
            elif elo > 1850:
                win_streak = 2
                
            country_code = NATIONAL_TEAM_ISO_CODES.get(name) or name[:3].upper()
            db_team = Team(
                name=name,
                country_code=country_code,
                elo=elo,
                form_score=round(form_score, 1),
                win_streak=win_streak,
                draw_streak=0,
                loss_streak=0
            )
            db.add(db_team)
            db.flush()
            
            # Tournament association
            db_tourney_team = TournamentTeam(
                tournament_id=tourney.id,
                team_id=db_team.id,
                group_name=group,
                tournament_status="Active"
            )
            db.add(db_tourney_team)
            
            # ELO History record
            db_elo_hist = EloHistory(
                team_id=db_team.id,
                recorded_at=datetime.now(timezone.utc),
                elo_rating=elo
            )
            db.add(db_elo_hist)
            
            team_map[t["id"]] = name
    else:
        # Fallback to local ELO ratings & Groups
        id_counter = 1
        for group, teams_list in GROUPS.items():
            for name in teams_list:
                elo = live_elo.get(name, 1700)
                form_score = min(95.0, max(45.0, 50.0 + (elo - 1500) * 0.05))
                win_streak = 4 if elo > 2000 else (2 if elo > 1850 else 0)
                
                country_code = NATIONAL_TEAM_ISO_CODES.get(name) or name[:3].upper()
                db_team = Team(
                    name=name,
                    country_code=country_code,
                    elo=elo,
                    form_score=round(form_score, 1),
                    win_streak=win_streak,
                    draw_streak=0,
                    loss_streak=0
                )
                db.add(db_team)
                db.flush()
                
                db_tourney_team = TournamentTeam(
                    tournament_id=tourney.id,
                    team_id=db_team.id,
                    group_name=group,
                    tournament_status="Active"
                )
                db.add(db_tourney_team)
                
                db_elo_hist = EloHistory(
                    team_id=db_team.id,
                    recorded_at=datetime.now(timezone.utc),
                    elo_rating=elo
                )
                db.add(db_elo_hist)
                
                team_map[str(id_counter)] = name
                id_counter += 1
                
    db.commit()

    # Re-query all teams to get the team name to id mapping
    db_teams_by_name = {team.name: team.id for team in db.query(Team).all()}

    # 3. Add Players & Contracts
    for team_name, players in SPOTLIGHT_PLAYERS.items():
        team_id = db_teams_by_name.get(team_name)
        if not team_id:
            continue
        for name, pos, form in players:
            db_player = Player(
                name=name,
                position=pos,
                form_score=form
            )
            db.add(db_player)
            db.flush()
            
            contract = PlayerContract(
                player_id=db_player.id,
                team_id=team_id,
                type="Country",
                is_active=True
            )
            db.add(contract)
            
    db.commit()

    # 4. Add Fixtures & Initial Odds
    fetched_matches = []
    try:
        print("Fetching official schedule from API...")
        matches_url = "https://worldcup26.ir/get/games"
        res_matches = fetch_json_with_retry(matches_url)
        fetched_matches = res_matches.get("games") if isinstance(res_matches, dict) else res_matches
        print(f"Successfully fetched {len(fetched_matches)} matches.")
    except Exception as e:
        print(f"Failed to fetch matches: {e}. Seeding fallback schedule.")

    fixtures_to_save = []
    
    if fetched_matches:
        stage_mapping = {
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
        
        for m in fetched_matches:
            h_team = team_map.get(m["home_team_id"])
            a_team = team_map.get(m["away_team_id"])
            
            home_id = db_teams_by_name.get(h_team) if h_team else None
            away_id = db_teams_by_name.get(a_team) if a_team else None
            
            home_placeholder = m.get("home_team_label") if not home_id else None
            away_placeholder = m.get("away_team_label") if not away_id else None
            
            # Parse Date: "06/11/2026 13:00"
            date_str = m["local_date"]
            try:
                stadium_timezones = {
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
                dt_naive = datetime.strptime(date_str, "%m/%d/%Y %H:%M")
                tz_name = stadium_timezones.get(str(m.get("stadium_id")), "America/New_York")
                dt_localized = dt_naive.replace(tzinfo=ZoneInfo(tz_name))
                dt_utc = dt_localized.astimezone(timezone.utc)
            except Exception as ex:
                print(f"Error localizing match date: {ex}")
                try:
                    dt = datetime.strptime(date_str, "%m/%d/%Y %H:%M")
                    dt_utc = dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    dt_utc = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
                
            stage = stage_mapping.get(m["type"], "Group Stage")
            status = "Finished" if m["finished"] == "TRUE" else "Scheduled"
            
            h_elo = live_elo.get(h_team, 1700) if h_team else 1700
            a_elo = live_elo.get(a_team, 1700) if a_team else 1700
            odds_h, odds_d, odds_a = calculate_default_odds(h_elo, a_elo)
            
            fixture = Fixture(
                tournament_id=tourney.id,
                home_team_id=home_id,
                away_team_id=away_id,
                home_team_placeholder=home_placeholder,
                away_team_placeholder=away_placeholder,
                api_id=str(m["id"]),
                date_utc=dt_utc,
                stage=stage,
                status=status,
                home_score=int(m["home_score"]) if status == "Finished" else None,
                away_score=int(m["away_score"]) if status == "Finished" else None,
                winner_id=home_id if status == "Finished" and home_id and away_id and int(m["home_score"]) > int(m["away_score"]) else (away_id if status == "Finished" and home_id and away_id and int(m["home_score"]) < int(m["away_score"]) else None)
            )
            db.add(fixture)
            db.flush()
            
            # Initial odds history record (recorded 2 days before)
            init_odds = FixtureOdds(
                fixture_id=fixture.id,
                recorded_at=dt_utc - timedelta(days=2),
                odds_home=odds_h,
                odds_draw=odds_d,
                odds_away=odds_a
            )
            db.add(init_odds)
            fixtures_to_save.append(fixture)
    else:
        # Fallback Seeding
        fallback_matches = get_fallback_matches()
        for f in fallback_matches:
            h_team = f["home"]
            a_team = f["away"]
            dt_utc = datetime.fromisoformat(f["date"])
            
            h_elo = live_elo.get(h_team, 1700)
            a_elo = live_elo.get(a_team, 1700)
            odds_h, odds_d, odds_a = calculate_default_odds(h_elo, a_elo)
            
            fixture = Fixture(
                tournament_id=tourney.id,
                home_team_id=db_teams_by_name[h_team],
                away_team_id=db_teams_by_name[a_team],
                api_id=str(f["id"]),
                date_utc=dt_utc,
                stage=f["stage"],
                status=f["status"],
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
            fixtures_to_save.append(fixture)
            
    db.commit()
    
    # Try updating odds from API if key is present
    update_odds_from_api(fixtures_to_save, db)
    db.commit()
    
    # Calculate watchability index using default weights
    for fixture in fixtures_to_save:
        update_fixture_score(fixture, db)
        
    db.commit()
    
    # Recalculate team streaks and standings cache based on seeded finished fixtures
    from backend.services.standings import recalculate_standings
    recalculate_standings(db, tourney.id)
    db.commit()

    print("Database seeding completed. Triggering tournament Monte Carlo simulation...")
    from backend.services.tournament import run_monte_carlo_simulation
    try:
        run_monte_carlo_simulation(db)
    except Exception as e:
        print(f"Error running pre-computed Monte Carlo simulation: {e}")
        
    print("Database seeding and simulation completed.")

def call_football_api(endpoint: str, params: dict = None) -> dict:
    """Helper to query the API-Football API."""
    api_key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
    if not api_key:
        raise ValueError("FOOTBALL_API_KEY/API_FOOTBALL_KEY is not configured in the environment.")
    
    query = ""
    if params:
        query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
        
    url = f"https://v3.football.api-sports.io/{endpoint}{query}"
    headers = {
        "x-apisports-key": api_key,
        "User-Agent": "Mozilla/5.0"
    }
    return fetch_json_with_retry(url, headers=headers)


def fetch_clubelo_ratings(date_str: str = None) -> dict[str, int]:
    """Fetches the current Elo ratings of club teams from clubelo.com."""
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = f"http://api.clubelo.com/{date_str}"
    print(f"Fetching ClubElo CSV from: {url}")
    try:
        content = fetch_url_with_retry(url).decode('utf-8')
    except Exception as e:
        print(f"Error fetching ClubElo ratings: {e}")
        return {}
        
    ratings = {}
    lines = content.split('\n')
    if len(lines) < 2:
        print("Warning: ClubElo response is empty or invalid.")
        return ratings
        
    for line in lines[1:]: # skip header
        if not line.strip():
            continue
        parts = line.split(',')
        if len(parts) >= 5:
            club_name = parts[1].strip()
            elo_str = parts[4].strip()
            try:
                elo = int(float(elo_str))
                ratings[club_name] = elo
            except ValueError:
                pass
    return ratings


def fuzzy_match_team(team_name: str, clubelo_names: list[str]) -> tuple[str, float]:
    """Fuzzy match team name against ClubElo name registry with fallback SequenceMatcher."""
    import difflib
    best_name = None
    best_score = 0.0
    
    try:
        from rapidfuzz import process, fuzz
        match = process.extractOne(team_name, clubelo_names, scorer=fuzz.token_sort_ratio)
        if match:
            return match[0], match[1] / 100.0
    except ImportError:
        pass
        
    for name in clubelo_names:
        score = difflib.SequenceMatcher(None, team_name.lower(), name.lower()).ratio()
        if score > best_score:
            best_score = score
            best_name = name
            
    return best_name, best_score


def review_elo_matches(db: Session, output_path: str = "backend/data/elo_name_review.json"):
    """Generates an ELO match review file comparing DB club teams with ClubElo database."""
    # Find all clubs in DB that use clubelo ELO source
    teams = db.query(Team).filter(Team.team_type == "Club", Team.elo_source == "clubelo").all()
    if not teams:
        print("No club teams found in DB. Did you fetch teams first?")
        return
        
    clubelo_ratings = fetch_clubelo_ratings()
    if not clubelo_ratings:
        print("Failed to fetch ClubElo ratings.")
        return
        
    clubelo_names = list(clubelo_ratings.keys())
    review_list = []
    
    for team in teams:
        best_name, confidence = fuzzy_match_team(team.name, clubelo_names)
        elo_val = clubelo_ratings.get(best_name, 1500)
        status = "approved" if confidence >= 0.85 else "needs_review"
        
        review_list.append({
            "api_football_name": team.name,
            "clubelo_name": best_name,
            "confidence": round(confidence, 2),
            "elo": elo_val,
            "status": status
        })
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(review_list, f, indent=2)
        
    print(f"Generated ELO review file: {output_path}")
    print("Please review the mapping in this file, fix any wrong mappings, and run apply-elo-matches.")


def apply_elo_matches(db: Session, file_path: str):
    """Applies verified ELO mappings from elo_name_review.json to DB."""
    if not os.path.exists(file_path):
        print(f"ELO review file {file_path} not found.")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        review_list = json.load(f)
        
    now_time = datetime.now(timezone.utc)
    count = 0
    for item in review_list:
        if item.get("status") == "approved":
            api_name = item.get("api_football_name")
            clubelo_name = item.get("clubelo_name")
            elo = item.get("elo")
            
            team = db.query(Team).filter(Team.name == api_name, Team.team_type == "Club").first()
            if team:
                team.elo = elo
                team.form_score = round(min(95.0, max(45.0, 50.0 + (elo - 1500) * 0.05)), 1)
                
                # Add to EloHistory
                history = EloHistory(
                    team_id=team.id,
                    recorded_at=now_time,
                    elo_rating=elo
                )
                db.add(history)
                count += 1
                print(f"Applied ELO {elo} to {api_name} (mapped from {clubelo_name})")
                
    db.commit()
    print(f"Successfully applied ELO ratings to {count} teams.")


def fetch_and_seed_teams(
    db: Session,
    api_league_id: int,
    api_season: int,
    team_type: str = "Club",
    elo_source: str = "clubelo"
):
    """Fetches all teams for a league and picks spotlight players for each team."""
    print(f"Fetching teams for league {api_league_id}, season {api_season}...")
    try:
        res = call_football_api("teams", {"league": api_league_id, "season": api_season})
    except Exception as e:
        print(f"Error calling football API for teams: {e}")
        return
        
    if not isinstance(res, dict) or "response" not in res:
        print(f"Invalid API response: {res}")
        return
        
    teams_data = res["response"]
    print(f"Seeding {len(teams_data)} teams...")
    
    for t_wrapper in teams_data:
        t_info = t_wrapper.get("team", {})
        api_team_id = t_info.get("id")
        name = normalize_team_name(t_info.get("name", ""))
        country_name = t_info.get("country", "")
        country_code = t_info.get("code")
        if not country_code and country_name:
            country_code = country_name[:3].upper()
            
        db_team = None
        if api_team_id:
            db_team = db.query(Team).filter(Team.api_id == api_team_id).first()
        if not db_team:
            db_team = db.query(Team).filter(Team.name == name, Team.country_code == country_code).first()
            
        if db_team:
            db_team.api_id = api_team_id
            db_team.team_type = team_type
            db_team.elo_source = elo_source
            print(f"Updated existing team: {name} (api_id={api_team_id})")
        else:
            db_team = Team(
                name=name,
                country_code=country_code,
                team_type=team_type,
                elo_source=elo_source,
                api_id=api_team_id,
                elo=1500,
                form_score=50.0,
                win_streak=0,
                draw_streak=0,
                loss_streak=0
            )
            db.add(db_team)
            print(f"Created new team: {name} (api_id={api_team_id})")
        db.flush()
        
        # Fetch squad players to select 3 spotlight players (1 GK, 1 MID, 1 FWD)
        existing_contracts = db.query(PlayerContract).filter(PlayerContract.team_id == db_team.id).first()
        if existing_contracts:
            print(f"Squad already populated for {name}, skipping squad API call.")
        else:
            try:
                print(f"Fetching squad for {name}...")
                squad_res = call_football_api("players/squads", {"team": api_team_id})
                time.sleep(6.0)  # Throttling to respect API-Football 10 req/min free tier rate limit
                squad_data = squad_res.get("response", [])
                if squad_data and isinstance(squad_data, list):
                    players_list = squad_data[0].get("players", [])
                    gks = [p for p in players_list if p.get("position") == "Goalkeeper"]
                    mids = [p for p in players_list if p.get("position") == "Midfielder"]
                    fwds = [p for p in players_list if p.get("position") == "Attacker" or p.get("position") == "Forward"]
                    
                    spotlights = []
                    for p_group in (gks, mids, fwds):
                        if p_group:
                            p_group_sorted = sorted(p_group, key=lambda x: x.get("age") or 0, reverse=True)
                            spotlights.append(p_group_sorted[0])
                            
                    for p in spotlights:
                        p_name = p.get("name")
                        p_pos = p.get("position")
                        if p_pos == "Attacker":
                            p_pos = "Forward"
                            
                        db_player = db.query(Player).filter(Player.name == p_name, Player.position == p_pos).first()
                        if not db_player:
                            db_player = Player(
                                name=p_name,
                                position=p_pos,
                                form_score=75.0
                            )
                            db.add(db_player)
                            db.flush()
                            
                        contract = db.query(PlayerContract).filter(
                            PlayerContract.player_id == db_player.id,
                            PlayerContract.team_id == db_team.id,
                            PlayerContract.type == team_type
                        ).first()
                        if not contract:
                            contract = PlayerContract(
                                player_id=db_player.id,
                                team_id=db_team.id,
                                type=team_type,
                                is_active=True
                            )
                            db.add(contract)
            except Exception as squad_err:
                print(f"Warning: Failed to fetch squad for {name}: {squad_err}")
            
    db.commit()
    print(f"Successfully seeded teams and spotlights for league={api_league_id}.")


def seed_competition(
    db: Session,
    competition_name: str,
    competition_type: str,
    format_engine: str,
    season: str,
    api_league_id: int,
    api_season: int,
    neutral_venue: bool = False,
    relegation_spots: int = 0,
    promotion_spots: int = 0,
    relegation_playoff_spots: int = 0,
    odds_api_sport_key: str = None,
    home_advantage_elo: int = 100
):
    """Seed / Upsert competition fixture data idempotently from API-Football."""
    comp = db.query(Competition).filter(Competition.name == competition_name).first()
    if not comp:
        comp = Competition(
            name=competition_name,
            type=competition_type,
            format_engine=format_engine,
            odds_api_sport_key=odds_api_sport_key,
            home_advantage_elo=0 if neutral_venue else home_advantage_elo,
            neutral_venue=neutral_venue,
            relegation_spots=relegation_spots,
            promotion_spots=promotion_spots,
            relegation_playoff_spots=relegation_playoff_spots,
            api_league_id=api_league_id
        )
        db.add(comp)
        db.flush()
        print(f"Created Competition: {competition_name}")
    else:
        comp.type = competition_type
        comp.format_engine = format_engine
        comp.odds_api_sport_key = odds_api_sport_key
        comp.neutral_venue = neutral_venue
        comp.relegation_spots = relegation_spots
        comp.promotion_spots = promotion_spots
        comp.relegation_playoff_spots = relegation_playoff_spots
        comp.home_advantage_elo = 0 if neutral_venue else home_advantage_elo
        comp.api_league_id = api_league_id
        db.flush()
        print(f"Updated Competition metadata: {competition_name}")

        
    tourney = db.query(Tournament).filter(
        Tournament.competition_id == comp.id,
        Tournament.season_name == season
    ).first()
    if not tourney:
        tourney = Tournament(
            competition_id=comp.id,
            season_name=season,
            status="Active"
        )
        db.add(tourney)
        db.flush()
        print(f"Created Tournament season: {season}")
        
    print(f"Fetching fixtures from API-Football for league={api_league_id}, season={api_season}...")
    try:
        res = call_football_api("fixtures", {"league": api_league_id, "season": api_season})
    except Exception as e:
        print(f"Error fetching fixtures from API-Football: {e}")
        return
        
    if not isinstance(res, dict) or "response" not in res:
        print(f"Invalid API response for fixtures: {res}")
        return
        
    fixtures_data = res["response"]
    print(f"Found {len(fixtures_data)} fixtures in response. Seeding/Upserting...")
    
    fixtures_saved = []
    team_ids_in_fixtures = set()
    
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
        
        if home_team:
            team_ids_in_fixtures.add(home_team.id)
        if away_team:
            team_ids_in_fixtures.add(away_team.id)
            
        stage = "Regular Season" if format_engine in ("league", "league_playoffs") else round_str
        status_short = f_info.get("status", {}).get("short", "")
        status = "Scheduled"
        if status_short in ("FT", "AET", "PEN"):
            status = "Finished"
        elif status_short in ("1H", "2H", "HT", "ET", "P", "LIVE"):
            status = "Live"
            
        home_score = goals.get("home")
        away_score = goals.get("away")
        
        fixture = db.query(Fixture).filter(
            Fixture.tournament_id == tourney.id,
            Fixture.api_id == api_id
        ).first()
        
        if not fixture:
            fixture = Fixture(
                tournament_id=tourney.id,
                api_id=api_id,
                home_team_id=home_team.id if home_team else None,
                away_team_id=away_team.id if away_team else None,
                home_team_placeholder=None if home_team else t_info.get("home", {}).get("name"),
                away_team_placeholder=None if away_team else t_info.get("away", {}).get("name"),
                date_utc=date_utc,
                stage=stage,
                matchday_number=matchday_number,
                status=status,
                home_score=home_score,
                away_score=away_score,
                winner_id=home_team.id if status == "Finished" and home_team and away_team and home_score > away_score else (away_team.id if status == "Finished" and home_team and away_team and home_score < away_score else None)
            )
            db.add(fixture)
        else:
            fixture.home_team_id = home_team.id if home_team else fixture.home_team_id
            fixture.away_team_id = away_team.id if away_team else fixture.away_team_id
            fixture.date_utc = date_utc
            fixture.stage = stage
            fixture.matchday_number = matchday_number
            fixture.status = status
            fixture.home_score = home_score
            fixture.away_score = away_score
            fixture.winner_id = home_team.id if status == "Finished" and home_team and away_team and home_score > away_score else (away_team.id if status == "Finished" and home_team and away_team and home_score < away_score else None)
            
        db.flush()
        fixtures_saved.append(fixture)
        
    for tid in team_ids_in_fixtures:
        tt = db.query(TournamentTeam).filter(
            TournamentTeam.tournament_id == tourney.id,
            TournamentTeam.team_id == tid
        ).first()
        if not tt:
            tt = TournamentTeam(
                tournament_id=tourney.id,
                team_id=tid,
                group_name=None,
                tournament_status="Active"
            )
            db.add(tt)
            
    db.flush()
    
    for fixture in fixtures_saved:
        if not fixture.odds_history:
            h_elo = fixture.home_team.elo if fixture.home_team else 1500
            a_elo = fixture.away_team.elo if fixture.away_team else 1500
            
            h_odds, d_odds, a_odds = calculate_default_odds(h_elo, a_elo, neutral_venue=neutral_venue, home_advantage=comp.home_advantage_elo or 100)

            
            init_odds = FixtureOdds(
                fixture_id=fixture.id,
                recorded_at=fixture.date_utc - timedelta(days=2),
                odds_home=h_odds,
                odds_draw=d_odds,
                odds_away=a_odds
            )
            db.add(init_odds)
            
        db.flush()
        update_fixture_score(fixture, db)
        
    # Recalculate standings cache and team streaks
    from backend.services.standings import recalculate_standings
    recalculate_standings(db, tourney.id)
    db.commit()
    print(f"Successfully seeded competition {competition_name} for season {season}.")


if __name__ == "__main__":
    import argparse
    from backend.database import SessionLocal
    
    parser = argparse.ArgumentParser(description="findfootball.games Database Ingestion and Seeding CLI")
    parser.add_argument("command", nargs="?", default="seed-wc", 
                        choices=["seed-wc", "fetch-teams", "review-elo-matches", "apply-elo-matches", "seed-competition"],
                        help="Seeding command to run")
    parser.add_argument("--league", type=int, help="API-Football league ID")
    parser.add_argument("--season", type=int, help="API-Football season year")
    parser.add_argument("--comp-name", type=str, help="Competition name (for seed-competition)")
    parser.add_argument("--comp-type", type=str, default="League", help="Competition type (League/Cup/International)")
    parser.add_argument("--format-engine", type=str, default="league", help="Competition format engine")
    parser.add_argument("--neutral", action="store_true", help="Matches played on neutral venues")
    parser.add_argument("--file", type=str, default="backend/data/elo_name_review.json", help="Path to ELO review file")
    parser.add_argument("--odds-key", type=str, help="Odds API sport key (e.g. soccer_epl)")
    parser.add_argument("--home-advantage", type=int, default=100, help="ELO boost for home teams (if non-neutral)")
    
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        if args.command == "seed-wc":
            print("Seeding legacy World Cup 2026...")
            seed_database(db)
        elif args.command == "fetch-teams":
            if not args.league or not args.season:
                print("Error: --league and --season are required for fetch-teams.")
            else:
                fetch_and_seed_teams(db, args.league, args.season)
        elif args.command == "review-elo-matches":
            review_elo_matches(db, output_path=args.file)
        elif args.command == "apply-elo-matches":
            apply_elo_matches(db, file_path=args.file)
        elif args.command == "seed-competition":
            if not args.league or not args.season or not args.comp_name:
                print("Error: --league, --season, and --comp-name are required for seed-competition.")
            else:
                seed_competition(
                    db=db,
                    competition_name=args.comp_name,
                    competition_type=args.comp_type,
                    format_engine=args.format_engine,
                    season=str(args.season),
                    api_league_id=args.league,
                    api_season=args.season,
                    neutral_venue=args.neutral,
                    odds_api_sport_key=args.odds_key,
                    home_advantage_elo=args.home_advantage
                )

    finally:
        db.close()
