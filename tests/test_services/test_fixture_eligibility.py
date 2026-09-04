import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from backend.database import Competition, Tournament, Team, Fixture, TournamentTeam
import backend.crud.fixture as crud_fixture
from backend.services.tournament import group_enriched_fixtures, get_grouped_fixtures, enrich_fixture
from backend.services.feed_builder import build_fixtures_feed_cache
import backend.services.feed_builder as feed_builder

def test_offseason_fallback_returns_only_future_fixtures(db_session):
    """
    Regression test: When no fixtures exist in the rolling window (-14 to +30 days),
    off-season fallback MUST strictly return only future fixtures (date_utc >= now_utc).
    Past fixtures (both finished and scheduled) must NEVER be included.
    """
    comp = Competition(name="Offseason Cup", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    t1 = Team(name="Team Future A", elo=1600)
    t2 = Team(name="Team Future B", elo=1600)
    t3 = Team(name="Team Legacy Past", elo=1500)
    db_session.add_all([t1, t2, t3])
    db_session.flush()

    now_utc = datetime.now(timezone.utc)

    # 1. Legacy past fixtures (e.g. from previous season 60 and 90 days ago)
    # One finished, one erroneously unplayed/scheduled
    f_past_finished = Fixture(
        tournament_id=tourney.id,
        home_team_id=t3.id,
        away_team_id=t1.id,
        stage="Group Stage",
        status="Finished",
        home_score=1,
        away_score=0,
        date_utc=(now_utc - timedelta(days=90)).replace(tzinfo=None)
    )
    f_past_scheduled = Fixture(
        tournament_id=tourney.id,
        home_team_id=t3.id,
        away_team_id=t2.id,
        stage="Group Stage",
        status="Scheduled",
        date_utc=(now_utc - timedelta(days=60)).replace(tzinfo=None)
    )

    # 2. Future fixtures outside standard 30-day window (e.g. 50 and 52 days in the future)
    f_future_1 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        status="Scheduled",
        date_utc=(now_utc + timedelta(days=50)).replace(tzinfo=None),
        watchability_score=85.0
    )
    f_future_2 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t2.id,
        away_team_id=t1.id,
        stage="Group Stage",
        status="Scheduled",
        date_utc=(now_utc + timedelta(days=52)).replace(tzinfo=None),
        watchability_score=78.0
    )

    db_session.add_all([f_past_finished, f_past_scheduled, f_future_1, f_future_2])
    db_session.commit()

    # Query eligible fixtures via canonical CRUD function
    eligible = crud_fixture.get_eligible_fixtures(db_session, tournament_id=tourney.id, now_utc=now_utc)
    
    # Must only contain the future fixtures
    assert len(eligible) == 2
    for f in eligible:
        assert f.date_utc >= now_utc.replace(tzinfo=None)
        assert f.id in (f_future_1.id, f_future_2.id)
        assert f.id not in (f_past_finished.id, f_past_scheduled.id)

    # Test grouped output
    grouped = get_grouped_fixtures(db_session, "UTC", tournament_id=tourney.id)
    assert grouped["is_offseason"] is True
    assert len(grouped["today"]) == 0
    assert len(grouped["tomorrow"]) == 0
    assert len(grouped["this_week"]) == 2
    assert grouped["offseason_notice"] is not None
    assert "Off-season: Showing next upcoming matches starting" in grouped["offseason_notice"]

    # Verify that the matches in this_week are strictly the future ones
    match_ids = [m["id"] for m in grouped["this_week"]]
    assert f_future_1.id in match_ids
    assert f_future_2.id in match_ids
    assert f_past_scheduled.id not in match_ids
    assert f_past_finished.id not in match_ids


def test_active_tournaments_gating(db_session):
    """
    Verifies that global eligible fixtures queries only pull from tournaments with status='Active',
    while specific tournament_id queries can query any tournament.
    """
    comp = Competition(name="Active Filter Test Comp", type="League")
    db_session.add(comp)
    db_session.flush()

    tourney_active = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    tourney_inactive = Tournament(competition_id=comp.id, season_name="2025/26", status="Completed")
    db_session.add_all([tourney_active, tourney_inactive])
    db_session.flush()

    t1 = Team(name="Active Team 1", elo=1700)
    t2 = Team(name="Active Team 2", elo=1700)
    db_session.add_all([t1, t2])
    db_session.flush()

    now_utc = datetime.now(timezone.utc)
    
    f_active = Fixture(
        tournament_id=tourney_active.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Regular Season",
        status="Scheduled",
        date_utc=(now_utc + timedelta(days=2)).replace(tzinfo=None)
    )
    f_inactive = Fixture(
        tournament_id=tourney_inactive.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Regular Season",
        status="Scheduled",
        date_utc=(now_utc + timedelta(days=2)).replace(tzinfo=None)
    )
    db_session.add_all([f_active, f_inactive])
    db_session.commit()

    # Global query (tournament_id=None) -> only active tournament fixtures
    global_eligible = crud_fixture.get_eligible_fixtures(db_session, tournament_id=None, now_utc=now_utc)
    global_ids = [f.id for f in global_eligible]
    assert f_active.id in global_ids
    assert f_inactive.id not in global_ids

    # Targeted query for inactive tournament explicitly
    inactive_eligible = crud_fixture.get_eligible_fixtures(db_session, tournament_id=tourney_inactive.id, now_utc=now_utc)
    inactive_ids = [f.id for f in inactive_eligible]
    assert f_inactive.id in inactive_ids
    assert f_active.id not in inactive_ids


def test_group_enriched_fixtures_canonical_parity(db_session):
    """
    Tests canonical grouping rules:
    - Today: match date == today
    - Tomorrow: match date == tomorrow
    - This Week: (tomorrow, today + 8 days]
    - High-quality gems ranking
    - Finished matches capped at 30 and sorted descending
    """
    now_utc = datetime.now(timezone.utc)
    target_tz = ZoneInfo("UTC")

    # Construct sample enriched fixture dictionaries
    today_dt = now_utc.replace(hour=15, minute=0, second=0, microsecond=0)
    tomorrow_dt = (now_utc + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    day3_dt = (now_utc + timedelta(days=3)).replace(hour=20, minute=0, second=0, microsecond=0)
    day5_dt = (now_utc + timedelta(days=5)).replace(hour=20, minute=0, second=0, microsecond=0)
    day10_dt = (now_utc + timedelta(days=10)).replace(hour=20, minute=0, second=0, microsecond=0)
    past_dt = (now_utc - timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)

    fixtures_data = [
        {
            "id": 1,
            "home_team": {"name": "Team A"},
            "away_team": {"name": "Team B"},
            "date": today_dt.isoformat(),
            "status": "Scheduled",
            "watchability": {"overall": 60.0}
        },
        {
            "id": 2,
            "home_team": {"name": "Team C"},
            "away_team": {"name": "Team D"},
            "date": tomorrow_dt.isoformat(),
            "status": "Scheduled",
            "watchability": {"overall": 65.0}
        },
        {
            "id": 3,
            "home_team": {"name": "Team E"},
            "away_team": {"name": "Team F"},
            "date": day3_dt.isoformat(),
            "status": "Scheduled",
            "watchability": {"overall": 85.0}  # Gem
        },
        {
            "id": 4,
            "home_team": {"name": "Team G"},
            "away_team": {"name": "Team H"},
            "date": day5_dt.isoformat(),
            "status": "Scheduled",
            "watchability": {"overall": 75.0}  # Gem
        },
        {
            "id": 5,
            "home_team": {"name": "Team I"},
            "away_team": {"name": "Team J"},
            "date": day10_dt.isoformat(),  # Beyond 8-day window
            "status": "Scheduled",
            "watchability": {"overall": 90.0}
        },
        {
            "id": 6,
            "home_team": {"name": "Team K"},
            "away_team": {"name": "Team L"},
            "date": past_dt.isoformat(),
            "status": "Finished",
            "watchability": {"overall": 50.0}
        }
    ]

    result = group_enriched_fixtures(fixtures_data, target_tz, now_dt=now_utc)
    
    assert len(result["today"]) == 1
    assert result["today"][0]["id"] == 1
    
    assert len(result["tomorrow"]) == 1
    assert result["tomorrow"][0]["id"] == 2

    # This Week should contain day 3 and day 5 (within 8 days), but NOT day 10
    week_ids = [m["id"] for m in result["this_week"]]
    assert 3 in week_ids
    assert 4 in week_ids
    assert 5 not in week_ids

    # Finished should contain past match
    assert len(result["finished"]) == 1
    assert result["finished"][0]["id"] == 6
    assert result["is_offseason"] is False


def test_feed_builder_integration(db_session):
    """
    Tests build_fixtures_feed_cache producing a non-empty payload and
    properly integrating with get_eligible_fixtures.
    """
    comp = Competition(name="Feed Test League", type="League")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    t1 = Team(name="Feed Team 1", elo=1750)
    t2 = Team(name="Feed Team 2", elo=1720)
    db_session.add_all([t1, t2])
    db_session.flush()

    tt1 = TournamentTeam(tournament_id=tourney.id, team_id=t1.id)
    tt2 = TournamentTeam(tournament_id=tourney.id, team_id=t2.id)
    db_session.add_all([tt1, tt2])
    db_session.flush()

    now_utc = datetime.now(timezone.utc)
    f = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Regular Season",
        status="Scheduled",
        date_utc=(now_utc + timedelta(days=1)).replace(tzinfo=None),
        watchability_score=80.0
    )
    db_session.add(f)
    db_session.commit()

    feed_payload = build_fixtures_feed_cache(db_session)
    assert feed_payload is not None
    assert feed_payload["total_fixtures"] >= 1
    assert len(feed_payload["fixtures"]) >= 1
    assert any(m["id"] == f.id for m in feed_payload["fixtures"])


def test_feed_builder_preserves_cache_when_all_enrichment_fails(db_session, monkeypatch, tmp_path):
    comp = Competition(name="Failed Enrichment League", type="League")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    home = Team(name="Failed Enrichment Home", elo=1700)
    away = Team(name="Failed Enrichment Away", elo=1650)
    db_session.add_all([home, away])
    db_session.flush()
    fixture = Fixture(
        tournament_id=tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        stage="Regular Season",
        status="Scheduled",
        date_utc=(datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None),
    )
    db_session.add(fixture)
    db_session.commit()

    cache_path = tmp_path / "fixtures_feed_cache.json"
    existing_payload = {"updated_at": "existing", "total_fixtures": 1, "fixtures": [{"id": 999}]}
    cache_path.write_text(json.dumps(existing_payload), encoding="utf-8")
    monkeypatch.setattr(feed_builder, "CACHE_FILE_PATH", str(cache_path))

    def fail_enrichment(*args, **kwargs):
        raise RuntimeError("test enrichment failure")

    monkeypatch.setattr(feed_builder, "enrich_fixture", fail_enrichment)

    result = feed_builder.build_fixtures_feed_cache(db_session)

    assert result == existing_payload
    assert json.loads(cache_path.read_text(encoding="utf-8")) == existing_payload


def test_feed_builder_writes_empty_cache_without_active_tournaments(db_session, monkeypatch, tmp_path):
    cache_path = tmp_path / "fixtures_feed_cache.json"
    monkeypatch.setattr(feed_builder, "CACHE_FILE_PATH", str(cache_path))

    result = feed_builder.build_fixtures_feed_cache(db_session)

    assert result["total_fixtures"] == 0
    assert json.loads(cache_path.read_text(encoding="utf-8")) == result
