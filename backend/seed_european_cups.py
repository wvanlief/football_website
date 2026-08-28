"""
Standalone Seeder script for 2026/27 UEFA European Competitions Draw Data.
Seeds or refreshes Champions League, Europa League, and Conference League 36-team Swiss league phase.
"""
import sys
from pathlib import Path

# Add project root to sys.path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.database import SessionLocal
from backend.services.seeder import seed_european_cups

def main():
    print("--- Seeding 2026/27 European Competitions Draw Data ---")
    db = SessionLocal()
    try:
        results = seed_european_cups(db)
        print("\n--- Seeding Summary ---")
        for comp, res in results.items():
            print(f"  • {comp}: {res}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
