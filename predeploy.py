import os
import subprocess
import sqlalchemy
from sqlalchemy import inspect

def main():
    print("--- Starting Pre-Deployment Tasks ---")
    
    # Get database URL from environment
    db_url = os.getenv("DATABASE_URL", "sqlite:///./football_games.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    print("Checking database schema at connection...")
    
    try:
        engine = sqlalchemy.create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # If the database is populated (competitions table exists) but Alembic is not tracked yet
        import sys
        if "competitions" in tables and "alembic_version" not in tables:
            print("Detected populated database without Alembic version tracking. Stamping database with initial version 766d253ea2b0...")
            subprocess.run([sys.executable, "-m", "alembic", "stamp", "766d253ea2b0"], check=True)
        else:
            print("Alembic version tracking check passed.")
    except Exception as e:
        print(f"Error during database check: {e}")
        
    # Apply any pending migrations
    print("Running database migrations (alembic upgrade head)...")
    try:
        import sys
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
        print("Database migrations applied successfully.")
    except Exception as e:
        import sys
        print(f"Error running database migrations: {e}")
        sys.exit(1)
        
    # Seed database if it is empty or has incomplete data
    print("Checking if database seeding is required...")
    try:
        from backend.database import get_db, Fixture
        from backend.ingestor import seed_database
        
        db = next(get_db())
        try:
            fixture_count = db.query(Fixture).count()
            if fixture_count < 104:
                print(f"Database has {fixture_count} fixtures (expected 104). Cleaning up database and re-seeding...")
                from sqlalchemy import text
                
                # Delete existing data in dependency order
                try:
                    db.execute(text("TRUNCATE TABLE player_match_stats, fixture_odds, fixtures, tournament_teams, elo_history, teams CASCADE"))
                except Exception:
                    db.execute(text("DELETE FROM player_match_stats"))
                    db.execute(text("DELETE FROM fixture_odds"))
                    db.execute(text("DELETE FROM fixtures"))
                    db.execute(text("DELETE FROM tournament_teams"))
                    db.execute(text("DELETE FROM elo_history"))
                    db.execute(text("DELETE FROM teams"))
                db.commit()
                
                print("Database cleared. Seeding initial fixtures and data...")
                seed_database(db)
                print("Seeding completed successfully.")
            else:
                print(f"Database is already seeded with {fixture_count} fixtures.")
        finally:
            db.close()
    except Exception as e:
        print(f"Error during database seeding: {e}")
        
    print("--- Pre-Deployment Tasks Completed Successfully ---")

if __name__ == "__main__":
    main()
