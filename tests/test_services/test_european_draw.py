import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, Competition, Tournament, Team, TournamentTeam, Fixture
from backend.services.seeder import seed_european_cups

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    """Pytest fixture providing a clean in-memory SQLite database session for each test."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

def test_seed_european_cups(db_session):
    """
    Tests that seed_european_cups correctly creates competitions, tournaments, teams, and fixtures
    for UEFA Champions League, Europa League, and Conference League with proper format and structure.
    """
    results = seed_european_cups(db_session)
    assert "UEFA Champions League" in results
    assert "UEFA Europa League" in results
    assert "UEFA Conference League" in results
    
    # 1. Verify UCL format engine and tournament setup
    ucl_comp = db_session.query(Competition).filter(Competition.name == "UEFA Champions League").first()
    assert ucl_comp is not None
    assert ucl_comp.format_engine == "league_phase_knockout"
    assert ucl_comp.type == "Cup"
    
    ucl_tourney = db_session.query(Tournament).filter(
        Tournament.competition_id == ucl_comp.id,
        Tournament.season_name == "2026/27"
    ).first()
    assert ucl_tourney is not None
    assert ucl_tourney.status == "Active"
    
    # 2. Verify all 36 teams are added to TournamentTeam
    ucl_teams_count = db_session.query(TournamentTeam).filter(
        TournamentTeam.tournament_id == ucl_tourney.id
    ).count()
    assert ucl_teams_count == 36
    
    # 3. Verify fixtures are created with stage League Phase and odds
    ucl_fixtures = db_session.query(Fixture).filter(
        Fixture.tournament_id == ucl_tourney.id
    ).all()
    assert len(ucl_fixtures) > 0
    for f in ucl_fixtures:
        assert f.stage == "League Phase"
        assert f.status == "Scheduled"
        assert f.home_team_id is not None
        assert f.away_team_id is not None
        assert len(f.odds_history) > 0
        
    # 4. Verify UEL and UECL setup
    uel_comp = db_session.query(Competition).filter(Competition.name == "UEFA Europa League").first()
    assert uel_comp.format_engine == "league_phase_knockout"
    
    uecl_comp = db_session.query(Competition).filter(Competition.name == "UEFA Conference League").first()
    assert uecl_comp.format_engine == "league_phase_knockout"

    # 5. Verify idempotency: second run creates no duplicate rows
    comp_count = db_session.query(Competition).count()
    team_count = db_session.query(Team).count()
    tt_count = db_session.query(TournamentTeam).count()
    fixture_count = db_session.query(Fixture).count()

    results2 = seed_european_cups(db_session)
    assert "UEFA Champions League" in results2
    assert db_session.query(Competition).count() == comp_count
    assert db_session.query(Team).count() == team_count
    assert db_session.query(TournamentTeam).count() == tt_count
    assert db_session.query(Fixture).count() == fixture_count

