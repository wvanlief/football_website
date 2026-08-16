"""
Ultra-Safe World Cup Cross-Pollination Cleanup Script
Removes ONLY World Cup fixtures (June-July 2026 dates) that were erroneously inserted
into non-World Cup domestic/cup tournaments (FA Cup, Coppa Italia, DFB Pokal, etc.).
"""
import sys
from pathlib import Path

# Ensure backend modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database import SessionLocal, Fixture, Tournament, Competition, Team

def cleanup_world_cup_cross_pollination(db: Session, dry_run: bool = True):
    print(f"=== Ultra-Safe World Cup Cross-Pollination Cleanup (dry_run={dry_run}) ===")
    
    # World Cup 2026 date boundaries: June 1, 2026 to July 20, 2026
    start_date = datetime(2026, 6, 1)
    end_date = datetime(2026, 7, 20)

    # Query all fixtures during World Cup dates that are NOT assigned to FIFA World Cup
    bogus_fixtures = (
        db.query(Fixture)
        .join(Tournament, Fixture.tournament_id == Tournament.id)
        .join(Competition, Tournament.competition_id == Competition.id)
        .filter(
            Competition.name != "FIFA World Cup",
            Fixture.date_utc >= start_date,
            Fixture.date_utc <= end_date
        )
        .all()
    )

    print(f"Found {len(bogus_fixtures)} World Cup date fixtures mistakenly attached to non-World Cup tournaments.")

    # Group by competition name for reporting
    comp_counts = {}
    for f in bogus_fixtures:
        comp_name = f.tournament.competition.name
        comp_counts[comp_name] = comp_counts.get(comp_name, 0) + 1

    print("\nBreakdown of bogus fixtures per competition:")
    for comp_name, count in sorted(comp_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {comp_name}: {count} bogus World Cup fixtures")

    if not dry_run:
        for f in bogus_fixtures:
            db.delete(f)
        db.commit()
        print(f"\nCleanup Complete: Safely deleted {len(bogus_fixtures)} bogus World Cup fixtures across {len(comp_counts)} non-World Cup competitions.")
    else:
        print(f"\nDRY RUN COMPLETE: Would delete {len(bogus_fixtures)} bogus World Cup fixtures. Pass --execute to apply changes.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ultra-Safe World Cup Cross-Pollination Cleanup")
    parser.add_argument("--execute", action="store_true", help="Apply changes to DB (default is dry run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        cleanup_world_cup_cross_pollination(db, dry_run=not args.execute)
    finally:
        db.close()
