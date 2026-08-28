from datetime import datetime, timezone, timedelta
from backend.database import Team, EloHistory
from backend.services.elo import record_elo_history
from backend.services.seeder import seed_database

def test_record_elo_history_deduplication_same_day(db_session):
    team = Team(name="Test Team Dedup", elo=1500)
    db_session.add(team)
    db_session.flush()

    now = datetime.now(timezone.utc)
    
    # 1. First record
    entry1 = record_elo_history(db_session, team.id, 1550, recorded_at=now)
    db_session.commit()

    records = db_session.query(EloHistory).filter(EloHistory.team_id == team.id).all()
    assert len(records) == 1
    assert records[0].elo_rating == 1550

    # 2. Second record on the same date with updated ELO
    now_later = now + timedelta(hours=2)
    entry2 = record_elo_history(db_session, team.id, 1600, recorded_at=now_later)
    db_session.commit()

    records_after = db_session.query(EloHistory).filter(EloHistory.team_id == team.id).all()
    assert len(records_after) == 1
    assert records_after[0].id == records[0].id
    assert records_after[0].elo_rating == 1600

def test_record_elo_history_different_dates(db_session):
    team = Team(name="Test Team Dates", elo=1500)
    db_session.add(team)
    db_session.flush()

    day1 = datetime.now(timezone.utc) - timedelta(days=1)
    day2 = datetime.now(timezone.utc)

    record_elo_history(db_session, team.id, 1500, recorded_at=day1)
    record_elo_history(db_session, team.id, 1520, recorded_at=day2)
    db_session.commit()

    records = db_session.query(EloHistory).filter(EloHistory.team_id == team.id).order_by(EloHistory.recorded_at.asc()).all()
    assert len(records) == 2
    assert records[0].elo_rating == 1500
    assert records[1].elo_rating == 1520

def test_seeder_rerun_deduplicates_elo_history(db_session):
    # Run seed_database twice
    seed_database(db_session)
    count_first = db_session.query(EloHistory).count()
    assert count_first > 0

    # Second run should not create duplicate EloHistory records
    seed_database(db_session)
    count_second = db_session.query(EloHistory).count()

    assert count_second == count_first
