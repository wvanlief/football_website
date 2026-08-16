"""
Belgian Pro League Database Cleanup Test Script
Deduplicates Belgian Pro League tournaments (merging '2026' into '2026/27')
and removes duplicate fixture records.
"""
import sys
from pathlib import Path

# Ensure backend modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database import SessionLocal, Competition, Tournament, Fixture, TournamentTeam

def cleanup_belgian_league(db: Session, dry_run: bool = True):
    print(f"=== Belgian Pro League Cleanup Test (dry_run={dry_run}) ===")
    
    comp = db.query(Competition).filter(func.lower(Competition.name).contains("belgian")).first()
    if not comp:
        print("Competition containing 'belgian' not found in database.")
        return

    tournaments = db.query(Tournament).filter(Tournament.competition_id == comp.id).all()
    print(f"Found {len(tournaments)} tournaments for Belgian Pro League:")
    for t in tournaments:
        fix_count = db.query(Fixture).filter(Fixture.tournament_id == t.id).count()
        print(f"  - Tournament ID {t.id}: season_name='{t.season_name}', status='{t.status}', fixtures={fix_count}")

    t_target = next((t for t in tournaments if t.season_name == "2026/27"), None)
    t_legacy = next((t for t in tournaments if t.season_name == "2026"), None)

    if not t_target or not t_legacy:
        print("Did not find both '2026' and '2026/27' tournaments. Nothing to merge.")
        return

    target_fixtures = db.query(Fixture).filter(Fixture.tournament_id == t_target.id).all()
    legacy_fixtures = db.query(Fixture).filter(Fixture.tournament_id == t_legacy.id).all()

    print(f"\nTarget ('2026/27') fixtures: {len(target_fixtures)}")
    print(f"Legacy ('2026') fixtures: {len(legacy_fixtures)}")

    duplicates_to_delete = []
    
    # Map target fixtures by (home_team_id, away_team_id, date)
    target_map = {}
    for f in target_fixtures:
        key = (f.home_team_id, f.away_team_id, f.date_utc.strftime("%Y-%m-%d") if f.date_utc else "")
        target_map[key] = f

    for lf in legacy_fixtures:
        key = (lf.home_team_id, lf.away_team_id, lf.date_utc.strftime("%Y-%m-%d") if lf.date_utc else "")
        if key in target_map:
            tf = target_map[key]
            # Copy score or finished status if legacy had it and target didn't
            if lf.status == "Finished" and tf.status != "Finished":
                if not dry_run:
                    tf.status = "Finished"
                    tf.home_score = lf.home_score
                    tf.away_score = lf.away_score
                print(f"  [Merge] Copied finished status from legacy fixture ID {lf.id} to target fixture ID {tf.id}")
            duplicates_to_delete.append(lf)

    print(f"\nFound {len(duplicates_to_delete)} duplicate fixtures in legacy tournament.")

    if not dry_run:
        for df in duplicates_to_delete:
            db.delete(df)
        
        t_legacy.status = "Completed"
        db.commit()
        print("\nSuccessfully deleted duplicate fixtures and set legacy tournament to 'Completed'.")
    else:
        print("\nDRY RUN COMPLETE. Pass --execute to apply changes to the database.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Belgian Pro League Deduplication Cleanup Test")
    parser.add_argument("--execute", action="store_true", help="Apply changes to DB (default is dry run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        cleanup_belgian_league(db, dry_run=not args.execute)
    finally:
        db.close()
