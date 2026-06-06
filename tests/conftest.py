import os
import pytest

# Set env variables BEFORE importing backend modules
os.environ["DATABASE_URL"] = "sqlite:///./test_football_games.db"
os.environ["TESTING"] = "True"
os.environ["ADMIN_TOKEN"] = "test-admin-token"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base, get_db, engine, SessionLocal
from backend.main import app

@pytest.fixture(scope="function")
def db_session():
    """
    Creates a fresh, clean database schema for each test using the test database file.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        # Safely remove the test DB file if it exists to keep workspace clean
        try:
            if os.path.exists("./test_football_games.db"):
                os.remove("./test_football_games.db")
        except Exception:
            pass

@pytest.fixture(scope="function")
def client(db_session):
    """
    Yields a FastAPI TestClient that overrides get_db dependency.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
