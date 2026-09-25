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


def test_preflight_ignores_unstamped_draw_rows_in_existing_count(db_session):
    """Unstamped draw leftovers must not inflate the pre-flight denominator."""
    comp = Competition(name="UCL Preflight Draw", type="Cup", format_engine="league_phase_knockout")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    now_utc = datetime.now(timezone.utc)
    unstamped = [
        Fixture(
            tournament_id=tourney.id,
            api_id=None,
            date_utc=now_utc,
            stage="League Phase",
            status="Scheduled",
        )
        for _ in range(144)
    ]
    stamped = [
        Fixture(
            tournament_id=tourney.id,
            api_id=f"fd_{i}",
            date_utc=now_utc,
            stage="League Phase",
            status="Scheduled",
        )
        for i in range(10)
    ]
    db_session.add_all(unstamped + stamped)
    db_session.commit()

    guard = PreflightGuard()
    guard.check_fixture_count(db_session, tourney.id, fetched_count=10)

    with pytest.raises(IngestionAborted) as exc_info:
        guard.check_fixture_count(db_session, tourney.id, fetched_count=4)
    assert "existing count (10" in str(exc_info.value)


def test_preflight_aborts_thin_thesportsdb_dump_against_populated_uel(db_session):
    """A 15-event TheSportsDB page must not overlay a populated Europa League tournament."""
    comp = Competition(name="UEFA Europa League", type="Cup", format_engine="league_phase_knockout")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    now_utc = datetime.now(timezone.utc)
    db_session.add_all([
        Fixture(
            tournament_id=tourney.id,
            api_id=f"fd_{i}",
            date_utc=now_utc,
            stage="League Phase",
            status="Scheduled",
        )
        for i in range(44)
    ])
    db_session.commit()

    with pytest.raises(IngestionAborted) as exc_info:
        PreflightGuard().check_fixture_count(db_session, tourney.id, fetched_count=15)

    assert "existing count (44" in str(exc_info.value)

