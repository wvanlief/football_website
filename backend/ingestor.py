import sys
import os
from pathlib import Path

# Add project root to sys.path if missing
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
import urllib.request
from sqlalchemy.orm import Session
from backend.database import SessionLocal, Team
from backend.services.ingestion import NameNormalizer, COUNTRY_ISO_MAP


# Re-exports for backward compatibility
from backend.services.odds import (
    calculate_default_odds,
    update_odds_from_api
)
from backend.services.elo import (
    fetch_current_elo_ratings,
    fetch_clubelo_ratings,
    fuzzy_match_team,
    review_elo_matches,
    apply_elo_matches
)
from backend.services.seeder import (
    call_football_api,
    get_fallback_matches,
    seed_database,
    fetch_and_seed_teams,
    seed_competition,
    GROUPS,
    SPOTLIGHT_PLAYERS,
    ELO_RATINGS
)

NATIONAL_TEAM_ISO_CODES = COUNTRY_ISO_MAP

def normalize_team_name(name: str) -> str:
    """Standardizes team name by stripping whitespace and mapping known alias variants."""
    return NameNormalizer().normalize(name)

def download_and_cache_badges(db: Session):
    """
    Downloads and caches team badge PNGs locally in backend/static/badges/{api_id}.png
    and updates team.logo_url in the database.
    """
    os.makedirs(os.path.join("backend", "static", "badges"), exist_ok=True)
    teams = db.query(Team).all()
    print(f"Caching badges for {len(teams)} teams...")
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    updated_count = 0
    
    for team in teams:
        if team.api_id:
            local_path = os.path.join("backend", "static", "badges", f"{team.api_id}.png")
            url_path = f"/static/badges/{team.api_id}.png"
            
            if not os.path.exists(local_path):
                img_url = f"https://media.api-sports.io/football/teams/{team.api_id}.png"
                try:
                    import ssl
                    ssl_ctx = ssl._create_unverified_context()
                    req = urllib.request.Request(img_url, headers=headers)
                    with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
                        if resp.status == 200:
                            with open(local_path, "wb") as f:
                                f.write(resp.read())
                            print(f"Downloaded badge for {team.name} ({team.api_id})")
                except Exception as e:
                    print(f"Could not download badge for {team.name}: {e}")
            
            if os.path.exists(local_path):
                if team.logo_url != url_path:
                    team.logo_url = url_path
                    updated_count += 1
        elif team.team_type == "National" and team.country_code:
            code = team.country_code.lower()
            if code == "eng": code = "gb-eng"
            elif code == "sco": code = "gb-sct"
            elif code == "wal": code = "gb-wls"
            elif code == "nir": code = "gb-nir"
            team.logo_url = f"https://flagcdn.com/w80/{code}.png"
            updated_count += 1
        else:
            team.logo_url = "/static/badges/default.png"
            
    db.commit()
    print(f"Successfully updated logo_url for {updated_count} teams.")



if __name__ == "__main__":
    import argparse
    from backend.database import SessionLocal
    
    parser = argparse.ArgumentParser(description="findfootball.games Database Ingestion and Seeding CLI")

    parser.add_argument("command", nargs="?", default="seed-wc", 
                        choices=["seed-wc", "fetch-teams", "review-elo-matches", "apply-elo-matches", "seed-competition", "cache-badges"],
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
            print("Seeding World Cup 2026...")
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
        elif args.command == "cache-badges":
            download_and_cache_badges(db)
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

