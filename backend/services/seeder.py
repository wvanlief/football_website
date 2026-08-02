import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from backend.database import (
    Team, Player, Fixture, Competition, Tournament, 
    TournamentTeam, PlayerContract, FixtureOdds, EloHistory
)
from backend.scoring import update_fixture_score
from backend.utils import fetch_json_with_retry
from backend.services.ingestion import NameNormalizer, COUNTRY_ISO_MAP
from backend.services.odds import calculate_default_odds, update_odds_from_api
from backend.services.elo import fetch_current_elo_ratings
from backend.services.settling import settle_result

NATIONAL_TEAM_ISO_CODES = COUNTRY_ISO_MAP

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
    "Czechia": 1830, "Bosnia and Herzegovina": 1720, "Côte d'Ivoire": 1800,
    "Tunisia": 1750, "Poland": 1820, "Belgium": 1960, "Egypt": 1780,
    "Saudi Arabia": 1710, "Iraq": 1700, "Jamaica": 1680,
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

def get_fallback_matches():
    base_date = datetime(2026, 6, 11, 12, 0, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(ZoneInfo("UTC"))
    return [
        {"id": "1", "home": "Mexico", "away": "South Africa", "stage": "Group Stage", "date": base_date.isoformat(), "status": "Scheduled"},
        {"id": "2", "home": "South Korea", "away": "Czechia", "stage": "Group Stage", "date": (base_date + timedelta(hours=7)).isoformat(), "status": "Scheduled"},
        {"id": "3", "home": "Canada", "away": "Bosnia and Herzegovina", "stage": "Group Stage", "date": (base_date + timedelta(days=1, hours=3)).isoformat(), "status": "Scheduled"},
        {"id": "4", "home": "Qatar", "away": "Switzerland", "stage": "Group Stage", "date": (base_date + timedelta(days=2)).isoformat(), "status": "Scheduled"},
        {"id": "5", "home": "Germany", "away": "Ecuador", "stage": "Group Stage", "date": (base_date + timedelta(days=2, hours=6)).isoformat(), "status": "Scheduled"},
        {"id": "6", "home": "Brazil", "away": "Morocco", "stage": "Group Stage", "date": (base_date + timedelta(days=3)).isoformat(), "status": "Scheduled"},
        {"id": "7", "home": "Spain", "away": "Uruguay", "stage": "Group Stage", "date": (base_date + timedelta(days=4, hours=4)).isoformat(), "status": "Scheduled"},
        {"id": "8", "home": "Portugal", "away": "Colombia", "stage": "Group Stage", "date": (base_date + timedelta(days=5)).isoformat(), "status": "Scheduled"},
        {"id": "9", "home": "England", "away": "Croatia", "stage": "Group Stage", "date": (base_date + timedelta(days=6)).isoformat(), "status": "Scheduled"}
    ]

def seed_database(db: Session):
    """
    Seeds database using actual World Cup 2026 schedules from API-Football, falling back to mock fixtures if offline.
    Also seeds Phase 8 competitions (Copa del Rey, Nations League).
    """
    normalizer = NameNormalizer()
    comp = db.query(Competition).filter_by(name="FIFA World Cup").first()
    if not comp:
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
    
    tourney = db.query(Tournament).filter_by(competition_id=comp.id, season_name="2026").first()
    if not tourney:
        tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
        db.add(tourney)
        db.flush()

    team_map = {}

    
    try:
        print("Fetching live Elo ratings from eloratings.net...")
        live_elo = fetch_current_elo_ratings()
        print(f"Successfully fetched {len(live_elo)} Elo ratings from eloratings.net.")
    except Exception as e:
        print(f"Failed to fetch live Elo ratings: {e}. Falling back to hardcoded dictionary.")
        live_elo = ELO_RATINGS

    id_counter = 1
    for group, teams_list in GROUPS.items():
        for name in teams_list:
            elo = live_elo.get(name, 1700)
            form_score = min(95.0, max(45.0, 50.0 + (elo - 1500) * 0.05))
            win_streak = 4 if elo > 2000 else (2 if elo > 1850 else 0)
            
            country_code = NATIONAL_TEAM_ISO_CODES.get(name) or name[:3].upper()
            db_team = db.query(Team).filter(Team.name == name).first()
            if not db_team:
                db_team = Team(
                    name=name,
                    country_code=country_code,
                    team_type="National",
                    elo_source="eloratings",
                    elo=elo,
                    form_score=round(form_score, 1),
                    win_streak=win_streak,
                    draw_streak=0,
                    loss_streak=0
                )
                db.add(db_team)
                db.flush()
            else:
                db_team.elo = elo
                db_team.form_score = round(form_score, 1)
                db.flush()
            
            db_tourney_team = db.query(TournamentTeam).filter(
                TournamentTeam.tournament_id == tourney.id,
                TournamentTeam.team_id == db_team.id
            ).first()
            if not db_tourney_team:
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

    db_teams_by_name = {team.name: team.id for team in db.query(Team).all()}

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

    fetched_matches = []
    api_key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
    if api_key:
        try:
            print("Fetching official schedule from API-Football...")
            res = call_football_api("fixtures", {"league": 1, "season": 2026})
            if isinstance(res, dict) and "response" in res:
                raw_fixtures = res["response"]
                for f in raw_fixtures:
                    fixture_info = f.get("fixture", {})
                    teams_info = f.get("teams", {})
                    goals_info = f.get("goals", {})
                    league_info = f.get("league", {})
                    
                    status_short = fixture_info.get("status", {}).get("short", "")
                    finished = "TRUE" if status_short in ("FT", "AET", "PEN") else "FALSE"
                    
                    api_date = fixture_info.get("date")
                    dt_utc_val = None
                    if api_date:
                        try:
                            dt_utc_val = datetime.fromisoformat(api_date.replace('Z', '+00:00'))
                        except Exception as date_err:
                            print(f"Error parsing date {api_date}: {date_err}")
                    
                    round_str = league_info.get("round", "")
                    
                    m = {
                        "id": str(fixture_info.get("id")),
                        "home_team_name": normalizer.normalize(teams_info.get("home", {}).get("name", "")),
                        "away_team_name": normalizer.normalize(teams_info.get("away", {}).get("name", "")),
                        "home_team_id": None,
                        "away_team_id": None,
                        "type": round_str,
                        "finished": finished,
                        "home_score": str(goals_info.get("home")) if goals_info.get("home") is not None else None,
                        "away_score": str(goals_info.get("away")) if goals_info.get("away") is not None else None,
                        "dt_utc": dt_utc_val,
                    }
                    fetched_matches.append(m)
                print(f"Successfully fetched {len(fetched_matches)} matches from API-Football.")
        except Exception as e:
            print(f"Failed to fetch matches from API-Football: {e}. Seeding fallback schedule.")

    fixtures_to_save = []
    
    if fetched_matches:
        stage_mapping = {
            "group": "Group Stage", "r32": "Round of 32", "round_of_32": "Round of 32",
            "r16": "Round of 16", "round_of_16": "Round of 16", "qf": "Quarter-final",
            "quarter": "Quarter-final", "semi": "Semi-final", "sf": "Semi-final",
            "third": "Third-place play-off", "final": "Final"
        }
        
        for m in fetched_matches:
            h_team = m.get("home_team_name") or team_map.get(m.get("home_team_id"))
            a_team = m.get("away_team_name") or team_map.get(m.get("away_team_id"))
            
            home_id = db_teams_by_name.get(h_team) if h_team else None
            away_id = db_teams_by_name.get(a_team) if a_team else None
            
            home_placeholder = m.get("home_team_label") if not home_id else None
            away_placeholder = m.get("away_team_label") if not away_id else None
            
            dt_utc = m.get("dt_utc")
            if not dt_utc:
                date_str = m.get("local_date") or ""
                try:
                    dt_naive = datetime.strptime(date_str, "%m/%d/%Y %H:%M")
                    dt_utc = dt_naive.replace(tzinfo=timezone.utc)
                except Exception:
                    dt_utc = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)
                
            raw_stage = m.get("type", "Group Stage")
            stage = stage_mapping.get(raw_stage, raw_stage)
            if "Group" in str(stage):
                stage = "Group Stage"
            status = "Finished" if m.get("finished") == "TRUE" else "Scheduled"
            
            h_elo = live_elo.get(h_team, 1700) if h_team else 1700
            a_elo = live_elo.get(a_team, 1700) if a_team else 1700
            odds_h, odds_d, odds_a = calculate_default_odds(h_elo, a_elo)
            
            api_id_str = str(m.get("id"))
            fixture = db.query(Fixture).filter(
                Fixture.tournament_id == tourney.id,
                Fixture.api_id == api_id_str
            ).first()
            if not fixture:
                fixture = Fixture(
                    tournament_id=tourney.id,
                    home_team_id=home_id,
                    away_team_id=away_id,
                    home_team_placeholder=home_placeholder,
                    away_team_placeholder=away_placeholder,
                    api_id=api_id_str,
                    date_utc=dt_utc,
                    stage=stage,
                    status=status
                )
                db.add(fixture)
            else:
                fixture.home_team_id = home_id or fixture.home_team_id
                fixture.away_team_id = away_id or fixture.away_team_id
                fixture.date_utc = dt_utc
                fixture.stage = stage
                fixture.status = status

            if status == "Finished" and m.get("home_score") is not None and m.get("away_score") is not None:
                try:
                    settle_result(fixture, int(m["home_score"]), int(m["away_score"]))
                except Exception:
                    pass
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
    else:
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
    
    update_odds_from_api(fixtures_to_save, db)
    db.commit()
    
    for fixture in fixtures_to_save:
        update_fixture_score(fixture, db)
        
    db.commit()
    
    from backend.services.standings import recalculate_standings
    recalculate_standings(db, tourney.id)
    db.commit()

    try:
        from backend.seed_phase8 import seed_phase8_data
        seed_phase8_data()
    except Exception as e:
        print(f"Phase 8 seeding warning: {e}")

    print("Database seeding and simulation completed.")

def seed_all_default_competitions(db: Session) -> dict:
    """Seeds all default 15 competitions (World Cup, Big 5 Domestic Leagues, European Cups, Domestic Cups, Nations League)."""
    results = {}
    print("--- Starting Full Multi-Competition Database Seeding ---")
    
    # 1. FIFA World Cup 2026
    try:
        seed_database(db)
        results["FIFA World Cup"] = "Seeded successfully"
    except Exception as e:
        results["FIFA World Cup"] = f"Error: {e}"
        
    # 2. Copa del Rey & UEFA Nations League
    try:
        from backend.seed_phase8 import seed_phase8_data
        seed_phase8_data()
        results["Phase 8 (Copa del Rey & Nations League)"] = "Seeded successfully"
    except Exception as e:
        results["Phase 8"] = f"Error: {e}"
        
    # 3. API-Football Competitions (Big 5 Leagues, European Cups, Domestic Cups)
    api_key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
    if api_key:
        leagues_to_seed = [
            # Big 5 Domestic Leagues
            ("Premier League", "League", "league", 39, "2026/27", 2026, 3, 100),
            ("La Liga", "League", "league", 140, "2026/27", 2026, 3, 120),
            ("Serie A", "League", "league", 135, "2026/27", 2026, 3, 100),
            ("Bundesliga", "League", "league", 78, "2026/27", 2026, 2, 100),
            ("Ligue 1", "League", "league", 61, "2026/27", 2026, 2, 90),

            # European Cups
            ("UEFA Champions League", "Cup", "group_knockout", 2, "2026/27", 2026, 0, 80),
            ("UEFA Europa League", "Cup", "group_knockout", 3, "2026/27", 2026, 0, 60),
            ("UEFA Conference League", "Cup", "group_knockout", 848, "2026/27", 2026, 0, 50),

            # Domestic Cups
            ("FA Cup", "Cup", "cup", 45, "2026/27", 2026, 0, 30),
            ("Coppa Italia", "Cup", "cup", 137, "2026/27", 2026, 0, 30),
            ("DFB Pokal", "Cup", "cup", 81, "2026/27", 2026, 0, 30),
            ("Coupe de France", "Cup", "cup", 66, "2026/27", 2026, 0, 30),
        ]
        for name, comp_type, format_eng, league_id, season_str, api_season, releg_spots, home_adv in leagues_to_seed:
            try:
                print(f"Seeding competition: {name}...")
                fetch_and_seed_teams(db, api_league_id=league_id, api_season=api_season, fetch_squads=False)
                seed_competition(
                    db=db,
                    competition_name=name,
                    competition_type=comp_type,
                    format_engine=format_eng,
                    season=season_str,
                    api_league_id=league_id,
                    api_season=api_season,
                    relegation_spots=releg_spots,
                    home_advantage_elo=home_adv
                )
                results[name] = "Seeded successfully"
            except Exception as e:
                print(f"Error seeding {name}: {e}")
                results[name] = f"Error: {e}"
    else:
        print("FOOTBALL_API_KEY not found. Skipping API-Football league seeding.")
        results["Leagues"] = "Skipped (No FOOTBALL_API_KEY)"

    print("--- Full Database Seeding Completed ---")
    return results



def fetch_and_seed_teams(
    db: Session,
    api_league_id: int,
    api_season: int,
    team_type: str = "Club",
    elo_source: str = "clubelo",
    fetch_squads: bool = False
):
    """Fetches all teams for a league and optionally picks spotlight players for each team."""
    normalizer = NameNormalizer()
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
        name = normalizer.normalize(t_info.get("name", ""))
        country_name = t_info.get("country", "")
        country_code = t_info.get("code")
        if not country_code and country_name:
            country_code = country_name[:3].upper()
            
        db_team = None
        if api_team_id:
            db_team = db.query(Team).filter(Team.api_id == api_team_id).first()
        if not db_team:
            db_team = db.query(Team).filter(Team.name == name).first()
            
        if db_team:
            db_team.api_id = api_team_id
            if country_code:
                db_team.country_code = country_code

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
        
        if not fetch_squads:
            continue

        existing_contracts = db.query(PlayerContract).filter(PlayerContract.team_id == db_team.id).first()
        if existing_contracts:
            print(f"Squad already populated for {name}, skipping squad API call.")
        else:
            try:
                print(f"Fetching squad for {name}...")
                squad_res = call_football_api("players/squads", {"team": api_team_id})
                time.sleep(6.0)
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

    # Ensure only the new season edition remains Active for this competition
    old_tourneys = db.query(Tournament).filter(
        Tournament.competition_id == comp.id,
        Tournament.season_name != season,
        Tournament.status == "Active"
    ).all()
    for old_t in old_tourneys:
        old_t.status = "Completed"

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
    else:
        tourney.status = "Active"
        db.flush()
        
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
        
        home_team = db.query(Team).filter(Team.api_id == h_api_id).first() if h_api_id else None
        if not home_team and h_api_id:
            h_raw_name = t_info.get("home", {}).get("name", "")
            h_norm_name = normalizer.normalize(h_raw_name)
            home_team = db.query(Team).filter(Team.name == h_norm_name).first()
            if home_team:
                home_team.api_id = h_api_id
            else:
                home_team = Team(
                    name=h_norm_name,
                    team_type="Club" if competition_type != "International" else "National",
                    api_id=h_api_id,
                    elo=1500,
                    form_score=50.0
                )
                db.add(home_team)
            db.flush()

        away_team = db.query(Team).filter(Team.api_id == a_api_id).first() if a_api_id else None
        if not away_team and a_api_id:
            a_raw_name = t_info.get("away", {}).get("name", "")
            a_norm_name = normalizer.normalize(a_raw_name)
            away_team = db.query(Team).filter(Team.name == a_norm_name).first()
            if away_team:
                away_team.api_id = a_api_id
            else:
                away_team = Team(
                    name=a_norm_name,
                    team_type="Club" if competition_type != "International" else "National",
                    api_id=a_api_id,
                    elo=1500,
                    form_score=50.0
                )
                db.add(away_team)
            db.flush()
        
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
                status=status
            )
            if status == "Finished" and home_score is not None and away_score is not None:
                settle_result(fixture, home_score, away_score)
            db.add(fixture)
        else:
            fixture.home_team_id = home_team.id if home_team else fixture.home_team_id
            fixture.away_team_id = away_team.id if away_team else fixture.away_team_id
            fixture.date_utc = date_utc
            fixture.stage = stage
            fixture.matchday_number = matchday_number
            if status == "Finished" and home_score is not None and away_score is not None:
                settle_result(fixture, home_score, away_score)
            else:
                fixture.status = status
                fixture.home_score = home_score
                fixture.away_score = away_score
            
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
        
    from backend.services.standings import recalculate_standings
    recalculate_standings(db, tourney.id)
    db.commit()
    print(f"Successfully seeded competition {competition_name} for season {season}.")
