import os
import json
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

def calculate_default_odds(home_elo, away_elo):
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

def update_odds_from_api(fixtures: list, db: Session):
    api_key = os.getenv("THE_ODDS_API_KEY")
    if not api_key:
        print("No THE_ODDS_API_KEY found in environment. Skipping Odds API update.")
        return
        
    print("Fetching odds from The Odds API...")
    url = f"https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/?apiKey={api_key}&regions=eu&markets=h2h"
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            odds_data = json.loads(response.read().decode())
            
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

def seed_database(db: Session):
    """
    Seeds database using actual World Cup 2026 schedules from GitHub, falling back to mock fixtures if offline.
    """
    # 1. Clear database in proper dependency order
    db.query(PlayerMatchStat).delete()
    db.query(FixtureOdds).delete()
    db.query(Fixture).delete()
    db.query(PlayerContract).delete()
    db.query(Player).delete()
    db.query(TournamentTeam).delete()
    db.query(Tournament).delete()
    db.query(Competition).delete()
    db.query(EloHistory).delete()
    db.query(Team).delete()
    db.commit()

    # 1.5 Create Competition and Tournament
    comp = Competition(name="FIFA World Cup", type="International")
    db.add(comp)
    db.flush()
    
    tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
    db.add(tourney)
    db.flush()

    # 2. Add Teams
    team_map = {}
    
    # Try fetching real teams list from GitHub
    fetched_teams = []
    try:
        print("Fetching team definitions from GitHub...")
        teams_url = "https://raw.githubusercontent.com/rezarahiminia/worldcup2026/main/football.teams.json"
        req = urllib.request.Request(teams_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            fetched_teams = json.loads(response.read().decode())
            print(f"Fetched {len(fetched_teams)} team definitions.")
    except Exception as e:
        print(f"Failed to fetch team definitions: {e}. Seeding using fallback groups.")

    if fetched_teams:
        for t in fetched_teams:
            name = normalize_team_name(t.get("name_en", ""))
            group = t.get("groups", "")
            
            elo = ELO_RATINGS.get(name, 1700)
            form_score = min(95.0, max(45.0, 50.0 + (elo - 1500) * 0.05))
            
            win_streak = 0
            if elo > 2000:
                win_streak = 4
            elif elo > 1850:
                win_streak = 2
                
            db_team = Team(
                name=name,
                country_code=None,
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
                elo = ELO_RATINGS.get(name, 1700)
                form_score = min(95.0, max(45.0, 50.0 + (elo - 1500) * 0.05))
                win_streak = 4 if elo > 2000 else (2 if elo > 1850 else 0)
                
                db_team = Team(
                    name=name,
                    country_code=None,
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
        print("Fetching official schedule from GitHub...")
        matches_url = "https://raw.githubusercontent.com/rezarahiminia/worldcup2026/main/football.matches.json"
        req = urllib.request.Request(matches_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            fetched_matches = json.loads(response.read().decode())
            print(f"Successfully fetched {len(fetched_matches)} matches.")
    except Exception as e:
        print(f"Failed to fetch matches: {e}. Seeding fallback schedule.")

    fixtures_to_save = []
    
    if fetched_matches:
        stage_mapping = {
            "group": "Group Stage",
            "round_of_32": "Round of 32",
            "round_of_16": "Round of 16",
            "quarter": "Quarter-final",
            "semi": "Semi-final",
            "third": "Third-place play-off",
            "final": "Final"
        }
        
        for m in fetched_matches:
            h_team = team_map.get(m["home_team_id"])
            a_team = team_map.get(m["away_team_id"])
            
            if not h_team or not a_team:
                continue
                
            # Parse Date: "06/11/2026 13:00"
            date_str = m["local_date"]
            try:
                stadium_timezones = {
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
            
            h_elo = ELO_RATINGS.get(h_team, 1700)
            a_elo = ELO_RATINGS.get(a_team, 1700)
            odds_h, odds_d, odds_a = calculate_default_odds(h_elo, a_elo)
            
            fixture = Fixture(
                tournament_id=tourney.id,
                home_team_id=db_teams_by_name[h_team],
                away_team_id=db_teams_by_name[a_team],
                date_utc=dt_utc,
                stage=stage,
                status=status,
                home_score=int(m["home_score"]) if status == "Finished" else None,
                away_score=int(m["away_score"]) if status == "Finished" else None,
                winner_id=db_teams_by_name[h_team] if status == "Finished" and int(m["home_score"]) > int(m["away_score"]) else (db_teams_by_name[a_team] if status == "Finished" and int(m["home_score"]) < int(m["away_score"]) else None)
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
            
            h_elo = ELO_RATINGS.get(h_team, 1700)
            a_elo = ELO_RATINGS.get(a_team, 1700)
            odds_h, odds_d, odds_a = calculate_default_odds(h_elo, a_elo)
            
            fixture = Fixture(
                tournament_id=tourney.id,
                home_team_id=db_teams_by_name[h_team],
                away_team_id=db_teams_by_name[a_team],
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
    print("Database seeding completed. Triggering tournament Monte Carlo simulation...")
    from backend.services.tournament import run_monte_carlo_simulation
    try:
        run_monte_carlo_simulation(db)
    except Exception as e:
        print(f"Error running pre-computed Monte Carlo simulation: {e}")
        
    print("Database seeding and simulation completed.")
