"""
General Database Tournament & Fixture Deduplication Script
Scans all active competitions for duplicate tournaments ('2026' vs '2026/27'),
merges scores and finished statuses, removes duplicate fixtures, and sets legacy tournaments to 'Completed'.
"""
import sys
from pathlib import Path

# Ensure backend modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database import SessionLocal, Competition, Tournament, Fixture

def cleanup_all_duplicate_tournaments(db: Session, dry_run: bool = True):
    print(f"=== Starting Global Tournament & Fixture Deduplication (dry_run={dry_run}) ===")
    
    competitions = db.query(Competition).all()
    total_duplicates_found = 0
    tournaments_completed = 0

    for comp in competitions:
        tournaments = db.query(Tournament).filter(Tournament.competition_id == comp.id).all()
        if len(tournaments) < 2:
            continue

        t_target = next((t for t in tournaments if t.season_name == "2026/27"), None)
        t_legacy = next((t for t in tournaments if t.season_name == "2026" and t.status != "Completed"), None)

        if not t_target or not t_legacy:
            continue

        print(f"\nProcessing '{comp.name}':")
        print(f"  Target Tournament (ID {t_target.id}, '2026/27'), Legacy Tournament (ID {t_legacy.id}, '2026')")

        target_fixtures = db.query(Fixture).filter(Fixture.tournament_id == t_target.id).all()
        legacy_fixtures = db.query(Fixture).filter(Fixture.tournament_id == t_legacy.id).all()

        target_map = {}
        for f in target_fixtures:
            key = (f.home_team_id, f.away_team_id, f.date_utc.strftime("%Y-%m-%d") if f.date_utc else "")
            target_map[key] = f

        duplicates_to_delete = []
        for lf in legacy_fixtures:
            key = (lf.home_team_id, lf.away_team_id, lf.date_utc.strftime("%Y-%m-%d") if lf.date_utc else "")
            if key in target_map:
                tf = target_map[key]
                if lf.status == "Finished" and tf.status != "Finished":
                    if not dry_run:
                        tf.status = "Finished"
                        tf.home_score = lf.home_score
                        tf.away_score = lf.away_score
                    print(f"    [Merge] Copied finished score ({lf.home_score}-{lf.away_score}) from legacy ID {lf.id} to target ID {tf.id}")
                duplicates_to_delete.append(lf)

        print(f"  Found {len(duplicates_to_delete)} duplicate fixtures to remove.")
        total_duplicates_found += len(duplicates_to_delete)

        if not dry_run:
            for df in duplicates_to_delete:
                db.delete(df)
            t_legacy.status = "Completed"
            tournaments_completed += 1

    if not dry_run:
        db.commit()
        print(f"\nCleanup Complete: Removed {total_duplicates_found} duplicate fixtures and marked {tournaments_completed} legacy tournaments as 'Completed'.")
    else:
        print(f"\nDRY RUN COMPLETE: Would remove {total_duplicates_found} duplicate fixtures. Pass --execute to apply changes.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Global Tournament & Fixture Deduplication")
    parser.add_argument("--execute", action="store_true", help="Apply changes to DB (default is dry run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        cleanup_all_duplicate_tournaments(db, dry_run=not args.execute)
    finally:
        db.close()
