"""
One-off admin script to manually fix the Final and 3rd-place fixtures.

The external API source (worldcup26.ir) has not yet updated with the
correct team assignments for these two fixtures, so this script applies
the known outcome directly to the database:

    Final:       Spain vs Argentina
    3rd-place:   France vs England

Usage:
    python fix_knockout_fixtures.py
"""

import os
import sys

from dotenv import load_dotenv

# Load environment variables (DATABASE_URL, etc.)
load_dotenv()

from backend.database import SessionLocal, Fixture, Team  # noqa: E402


def main():
    db = SessionLocal()
    try:
        print("Looking up team IDs...")

        spain = db.query(Team).filter(Team.name == "Spain").first()
        argentina = db.query(Team).filter(Team.name == "Argentina").first()
        france = db.query(Team).filter(Team.name == "France").first()
        england = db.query(Team).filter(Team.name == "England").first()

        missing = [
            name
            for name, team in (
                ("Spain", spain),
                ("Argentina", argentina),
                ("France", france),
                ("England", england),
            )
            if team is None
        ]
        if missing:
            print(f"Error: Could not find team(s) in database: {', '.join(missing)}")
            sys.exit(1)

        print(f"Spain id={spain.id}, Argentina id={argentina.id}, "
              f"France id={france.id}, England id={england.id}")

        final_fixture = db.query(Fixture).filter(Fixture.stage == "Final").first()
        third_place_fixture = (
            db.query(Fixture).filter(Fixture.stage == "Third-place play-off").first()
        )

        if final_fixture is None:
            print("Error: Could not find the Final fixture.")
            sys.exit(1)

        if third_place_fixture is None:
            print("Error: Could not find the Third-place play-off fixture.")
            sys.exit(1)

        print("Updating Final fixture: Spain vs Argentina...")
        final_fixture.home_team_id = spain.id
        final_fixture.away_team_id = argentina.id
        final_fixture.home_team_placeholder = None
        final_fixture.away_team_placeholder = None

        print("Updating Third-place play-off fixture: France vs England...")
        third_place_fixture.home_team_id = france.id
        third_place_fixture.away_team_id = england.id
        third_place_fixture.home_team_placeholder = None
        third_place_fixture.away_team_placeholder = None

        db.commit()
        print("Success: Final and Third-place fixtures updated.")

    except Exception as e:
        db.rollback()
        print(f"Error: Failed to update fixtures: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
