from datetime import datetime, timezone, timedelta
import json
from unittest.mock import Mock

from backend.database import Competition, Team, EloHistory
from backend.services.elo import record_elo_history, sync_ratings_for_competition
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


def test_unchanged_clubelo_sync_records_daily_marker(db_session, monkeypatch):
    competition = Competition(name="Marker League", type="League")
    team = Team(name="Marker FC", elo=1500, elo_source="clubelo")
    db_session.add_all([competition, team])
    db_session.commit()
    fetch = Mock(return_value={"Marker FC": 1500})
    monkeypatch.setattr("backend.services.elo.fetch_clubelo_ratings", fetch)
    sync_time = datetime(2026, 9, 4, 10, tzinfo=timezone.utc)

    assert sync_ratings_for_competition(db_session, competition, sync_time) == 0
    assert db_session.query(EloHistory).filter_by(team_id=team.id).count() == 1
    assert sync_ratings_for_competition(
        db_session, competition, sync_time + timedelta(hours=2)
    ) == 0
    fetch.assert_called_once()


def test_clubelo_sync_uses_only_approved_name_mappings(db_session, monkeypatch, tmp_path):
    competition = Competition(name="Mapping League", type="League")
    approved = Team(name="Approved FC", elo=1500, elo_source="clubelo")
    unapproved = Team(name="Unapproved FC", elo=1500, elo_source="clubelo")
    db_session.add_all([competition, approved, unapproved])
    db_session.commit()

    review_path = tmp_path / "backend" / "data" / "elo_name_review.json"
    review_path.parent.mkdir(parents=True)
    review_path.write_text(json.dumps([
        {
            "api_football_name": "Approved FC",
            "clubelo_name": "Approved ClubElo",
            "status": "approved",
        },
        {
            "api_football_name": "Unapproved FC",
            "clubelo_name": "Wrong ClubElo",
            "status": "needs_review",
        },
    ]), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "backend.services.elo.fetch_clubelo_ratings",
        lambda: {
            "Approved ClubElo": 1600,
            "Wrong ClubElo": 1900,
            "Unapproved FC": 1550,
        },
    )

    assert sync_ratings_for_competition(
        db_session,
        competition,
        datetime(2026, 9, 4, tzinfo=timezone.utc),
    ) == 2
    assert approved.elo == 1600
    assert unapproved.elo == 1550

def test_seeder_rerun_deduplicates_elo_history(db_session):
    # Run seed_database twice
    seed_database(db_session)
    count_first = db_session.query(EloHistory).count()
    assert count_first > 0

    # Second run should not create duplicate EloHistory records
    seed_database(db_session)
    count_second = db_session.query(EloHistory).count()

    assert count_second == count_first
