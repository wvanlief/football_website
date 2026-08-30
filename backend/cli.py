"""
findfootball.games CLI Administration Entry Point.
Command-line tools for database seeding, ELO review/matching, badge caching, and competition seeding.
"""
import sys
import os
import argparse
import urllib.request
from pathlib import Path

# Add project root to sys.path if missing
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy.orm import Session
from backend.database import SessionLocal, Team
from backend.services.elo import review_elo_matches, apply_elo_matches
from backend.services.seeder import seed_database, fetch_and_seed_teams, seed_single_competition
from backend.services.ingestion import seed_competition


def download_and_cache_badges(db: Session):
    """
    Downloads and caches team badge PNGs locally in backend/static/badges/{api_id}.png
    and updates team.logo_url in the database.
    """
    teams = db.query(Team).filter(Team.api_id.isnot(None)).all()
    static_badges_dir = Path("backend/static/badges")
    static_badges_dir.mkdir(parents=True, exist_ok=True)
    
    updated_count = 0
    for team in teams:
        if not team.api_id:
            continue
            
        badge_path = static_badges_dir / f"{team.api_id}.png"
        local_url = f"/static/badges/{team.api_id}.png"
        
        if not badge_path.exists():
            remote_url = f"https://media.api-sports.io/football/teams/{team.api_id}.png"
            try:
                print(f"Downloading badge for {team.name} ({team.api_id})...")
                req = urllib.request.Request(remote_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req) as resp, open(badge_path, "wb") as f:
                    f.write(resp.read())
            except Exception as e:
                print(f"Failed to download badge for {team.name}: {e}")
                continue
                
        if team.logo_url != local_url:
            team.logo_url = local_url
            updated_count += 1
            
    db.commit()
    print(f"Badge caching complete. Updated logo_url for {updated_count} teams.")


def main():
    parser = argparse.ArgumentParser(description="findfootball.games Database Ingestion and Seeding CLI")

    parser.add_argument("command", nargs="?", default="seed-wc", 
                        choices=["seed-wc", "fetch-teams", "review-elo-matches", "apply-elo-matches", "seed-competition", "seed-one", "cache-badges"],
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
    parser.add_argument("--fetch-squads", action="store_true", help="Fetch full squad rosters for teams")
    
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
        elif args.command == "seed-one":
            if not args.league:
                print("Error: --league is required for seed-one.")
            else:
                res = seed_single_competition(db, league_id=args.league, fetch_squads=args.fetch_squads)
                print(f"Seed-one result: {res}")
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


if __name__ == "__main__":
    main()
