import os
import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Ensure root directory is always on sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Set env variables BEFORE importing backend modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DATABASE_PUBLIC_URL"] = "sqlite:///:memory:"
os.environ["TESTING"] = "True"
os.environ["ADMIN_TOKEN"] = "test-admin-token"

from backend.database import Base, get_db, SessionLocal
from backend.main import app

@pytest.fixture(scope="function")
def db_session():
    """
    Creates a fresh, clean in-memory database schema for each test.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()

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
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()

