from datetime import datetime, timezone
from backend.database import Competition, Tournament, Fixture, FixtureOdds, TournamentTeam, Team
from backend.services.ingestion.fixture_upserter import FixtureUpserter


def test_upsert_creates_new_fixture(db_session):
    """Upserting a brand-new fixture payload creates a Fixture and default FixtureOdds."""
    comp = Competition(name="Premier League Test", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.commit()

    upserter = FixtureUpserter()
    now_utc = datetime.now(timezone.utc)

    payload = {
        "api_id": "api_1001",
        "home_team_name": "Arsenal",
        "away_team_name": "Chelsea",
        "date_utc": now_utc,
        "stage": "Regular Season",
        "status": "Scheduled"
    }

    fixture, is_created = upserter.upsert_fixture(db_session, tourney, payload)
    db_session.commit()

    assert is_created is True
    assert fixture.api_id == "api_1001"
    assert fixture.home_team.name == "Arsenal"
    assert fixture.away_team.name == "Chelsea"

    # Verify initial odds created
    odds = db_session.query(FixtureOdds).filter_by(fixture_id=fixture.id).all()
    assert len(odds) == 1

    # Verify TournamentTeam registrations created
    tt_list = db_session.query(TournamentTeam).filter_by(tournament_id=tourney.id).all()
    assert len(tt_list) == 2


def test_upsert_updates_existing_fixture(db_session):
    """Upserting an existing fixture updates attributes without creating a duplicate Fixture."""
    comp = Competition(name="La Liga Test", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.commit()

    upserter = FixtureUpserter()
    now_utc = datetime.now(timezone.utc)

    payload = {
        "api_id": "api_2001",
        "home_team_name": "Real Madrid",
        "away_team_name": "Barcelona",
        "date_utc": now_utc,
        "stage": "Regular Season",
        "status": "Scheduled"
    }

    f1, is_created1 = upserter.upsert_fixture(db_session, tourney, payload)
    db_session.commit()
    assert is_created1 is True

    # Re-upsert with score update
    updated_payload = {
        "api_id": "api_2001",
        "home_team_name": "Real Madrid",
        "away_team_name": "Barcelona",
        "date_utc": now_utc,
        "stage": "Regular Season",
        "status": "Finished",
        "home_score": 3,
        "away_score": 1
    }

    f2, is_created2 = upserter.upsert_fixture(db_session, tourney, updated_payload)
    db_session.commit()

    assert is_created2 is False
    assert f1.id == f2.id
    assert f2.status == "Finished"
    assert f2.home_score == 3
    assert f2.away_score == 1
    assert f2.winner_id == f2.home_team_id


def test_odds_date_deduplication(db_session):
    """Re-running fixture upserts on the same day skips duplicate FixtureOdds creation."""
    comp = Competition(name="Serie A Test", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.commit()

    upserter = FixtureUpserter()
    now_utc = datetime.now(timezone.utc)

    payload = {
        "api_id": "api_3001",
        "home_team_name": "Juventus",
        "away_team_name": "Inter Milan",
        "date_utc": now_utc,
        "stage": "Regular Season",
        "status": "Scheduled"
    }

    fixture, _ = upserter.upsert_fixture(db_session, tourney, payload)
    db_session.commit()

    # Re-run upsert on same day
    upserter.upsert_fixture(db_session, tourney, payload)
    db_session.commit()

    # Verify only 1 FixtureOdds entry exists
    odds_entries = db_session.query(FixtureOdds).filter_by(fixture_id=fixture.id).all()
    assert len(odds_entries) == 1
