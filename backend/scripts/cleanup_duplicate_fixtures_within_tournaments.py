"""
Comprehensive Fixture Deduplication Script
Identifies and removes duplicate fixture rows sharing the same (home_team_id, away_team_id, match_date).
Retains 1 authoritative fixture row per match, preserving finished scores, status, and odds links.
"""
import sys
from pathlib import Path

# Ensure backend modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from collections import defaultdict
from sqlalchemy.orm import Session
from backend.database import SessionLocal, Fixture, Tournament, Competition, FixtureOdds

def deduplicate_all_fixtures(db: Session, dry_run: bool = True):
    print(f"=== Starting Comprehensive Fixture Deduplication (dry_run={dry_run}) ===")
    
    # Query all fixtures in active tournaments
    active_fixtures = (
        db.query(Fixture)
        .join(Tournament, Fixture.tournament_id == Tournament.id)
        .filter(Tournament.status != "Completed")
        .all()
    )
    
    print(f"Total active fixtures in database: {len(active_fixtures)}")

    # Group fixtures by (home_team_id, away_team_id, date_str)
    grouped = defaultdict(list)
    for f in active_fixtures:
        date_str = f.date_utc.strftime("%Y-%m-%d") if f.date_utc else "unknown"
        key = (f.home_team_id, f.away_team_id, date_str)
        grouped[key].append(f)

    duplicate_groups = {k: v for k, v in grouped.items() if len(v) > 1}
    print(f"Found {len(duplicate_groups)} distinct match groups with duplicates.")

    total_deleted = 0

    for key, fixtures in duplicate_groups.items():
        home_id, away_id, match_date = key
        
        # Sort to pick the best authoritative fixture to KEEP:
        # 1. Finished status first
        # 2. Fixture with odds attached
        # 3. Lowest ID
        def sort_score(f):
            has_odds = db.query(FixtureOdds).filter(FixtureOdds.fixture_id == f.id).count() > 0
            is_finished = 1 if f.status == "Finished" else 0
            return (is_finished, 1 if has_odds else 0, -f.id)

        fixtures.sort(key=sort_score, reverse=True)
        keep = fixtures[0]
        delete_list = fixtures[1:]

        # Copy any score/status from duplicates to the kept fixture if needed
        for df in delete_list:
            if df.status == "Finished" and keep.status != "Finished":
                if not dry_run:
                    keep.status = "Finished"
                    keep.home_score = df.home_score
                    keep.away_score = df.away_score
            
            # Re-link odds from deleted fixture to kept fixture if keep has no odds
            odds_records = db.query(FixtureOdds).filter(FixtureOdds.fixture_id == df.id).all()
            for o in odds_records:
                if not dry_run:
                    o.fixture_id = keep.id

            if not dry_run:
                db.delete(df)

        total_deleted += len(delete_list)

    if not dry_run:
        db.commit()
        print(f"\nCleanup Successful: Removed {total_deleted} duplicate fixture rows across {len(duplicate_groups)} match groups.")
    else:
        print(f"\nDRY RUN COMPLETE: Would remove {total_deleted} duplicate fixture rows across {len(duplicate_groups)} match groups. Pass --execute to apply changes.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Comprehensive Fixture Deduplication")
    parser.add_argument("--execute", action="store_true", help="Apply changes to DB (default is dry run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        deduplicate_all_fixtures(db, dry_run=not args.execute)
    finally:
        db.close()
