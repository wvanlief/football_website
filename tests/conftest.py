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


REPLICA_DB = Path(__file__).resolve().parent.parent / "football_games.db"


@pytest.fixture(scope="session")
def replica_db():
    """Read-only session against the local production SQLite replica."""
    if not REPLICA_DB.exists() or REPLICA_DB.stat().st_size == 0:
        pytest.skip("local production replica football_games.db is required")
    replica_engine = create_engine(
        "sqlite:///" + REPLICA_DB.resolve().as_posix(),
        connect_args={"check_same_thread": False},
    )
    ReplicaSession = sessionmaker(autocommit=False, autoflush=False, bind=replica_engine)
    db = ReplicaSession()
    try:
        yield db
    finally:
        db.close()
        replica_engine.dispose()


def replica_club(db, name: str):
    from backend.database import Team

    rows = db.query(Team).filter(Team.name == name).all()
    if not rows:
        pytest.fail(f"{name} is missing from the local production replica")
    clubs = [row for row in rows if (row.team_type or "") == "Club"] or rows
    with_key = [row for row in clubs if row.api_id is not None or row.logo_url]
    return with_key[0] if with_key else clubs[0]


def replica_badge_key(team) -> str | None:
    """Badge identity stored on the replica row, not a test-authored id."""
    if team.api_id is not None:
        return str(team.api_id)
    logo = team.logo_url or ""
    if "/static/badges/" in logo and not logo.endswith("default.png"):
        digits = "".join(ch for ch in logo.rsplit("/", 1)[-1] if ch.isdigit())
        return digits or None
    return None


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

