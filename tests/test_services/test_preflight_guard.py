from datetime import datetime, timezone
import pytest
from backend.database import Tournament, Fixture, Competition
from backend.services.ingestion.preflight import PreflightGuard, IngestionAborted


def test_preflight_passes_on_first_seed(db_session):
    """Initial seed into an empty tournament (0 existing fixtures) must pass for any fetched count."""
    comp = Competition(name="Test League First Seed", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.commit()

    guard = PreflightGuard()
    # 0 existing fixtures, 10 fetched -> Should pass without raising
    guard.check_fixture_count(db_session, tourney.id, fetched_count=10)


def test_preflight_passes_on_healthy_reseed(db_session):
    """Re-seeding with minor fixture count differences (e.g. 378 vs 380) must pass."""
    comp = Competition(name="Test League Healthy Reseed", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    now_utc = datetime.now(timezone.utc)
    # Create 380 dummy fixtures
    fixtures = [
        Fixture(tournament_id=tourney.id, api_id=f"test_{i}", date_utc=now_utc, stage="Regular Season", status="Scheduled")
        for i in range(380)
    ]
    db_session.add_all(fixtures)
    db_session.commit()

    guard = PreflightGuard()
    # 380 existing fixtures, 378 fetched (99.4%) -> Should pass
    guard.check_fixture_count(db_session, tourney.id, fetched_count=378)


def test_preflight_aborts_on_low_fixture_count(db_session):
    """Re-seeding with <50% of existing fixture count (e.g. 50 vs 380) must raise IngestionAborted."""
    comp = Competition(name="Test League Low Count", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    now_utc = datetime.now(timezone.utc)
    fixtures = [
        Fixture(tournament_id=tourney.id, api_id=f"test_{i}", date_utc=now_utc, stage="Regular Season", status="Scheduled")
        for i in range(380)
    ]
    db_session.add_all(fixtures)
    db_session.commit()

    guard = PreflightGuard()
    # 380 existing fixtures, 50 fetched (13.1%) -> Should raise IngestionAborted
    with pytest.raises(IngestionAborted) as exc_info:
        guard.check_fixture_count(db_session, tourney.id, fetched_count=50)

    assert "below 50% threshold" in str(exc_info.value)
    assert "existing count (380" in str(exc_info.value)


def test_preflight_aborts_on_zero_fetched(db_session):
    """Re-seeding a populated tournament with 0 fetched fixtures must raise IngestionAborted."""
    comp = Competition(name="Test League Zero Fetched", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    now_utc = datetime.now(timezone.utc)
    fixtures = [
        Fixture(tournament_id=tourney.id, api_id=f"test_{i}", date_utc=now_utc, stage="Regular Season", status="Scheduled")
        for i in range(10)
    ]
    db_session.add_all(fixtures)
    db_session.commit()

    guard = PreflightGuard()
    with pytest.raises(IngestionAborted):
        guard.check_fixture_count(db_session, tourney.id, fetched_count=0)


def test_preflight_handles_none_tournament_id(db_session):
    """check_fixture_count with tournament_id=None must safely pass."""
    guard = PreflightGuard()
    guard.check_fixture_count(db_session, tournament_id=None, fetched_count=0)

