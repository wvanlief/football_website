import json
import os
from datetime import datetime, timedelta, timezone

import pytest
from zoneinfo import ZoneInfo
import backend.crud.fixture as crud_fixture
from backend.services.enrichment import group_enriched_fixtures
from backend.services.queries import get_grouped_fixtures
from backend.services.feed_builder import build_fixtures_feed_cache
import backend.services.feed_builder as feed_builder
from tests.factories import FROZEN_NOW, cup, fixture, kickoff, league, membership, team, tournament

def test_offseason_fallback_returns_only_future_fixtures(db_session):
    """
    Regression test: When no fixtures exist in the rolling window (-14 to +30 days),
    off-season fallback MUST strictly return only future fixtures (date_utc >= now_utc).
    Past fixtures (both finished and scheduled) must NEVER be included.
    """
    comp = cup(db_session, "Offseason Cup", type="International", format_engine="group_knockout")
    tourney = tournament(db_session, comp)
    t1 = team(db_session, "Team Future A", elo=1600)
    t2 = team(db_session, "Team Future B", elo=1600)
    t3 = team(db_session, "Team Legacy Past", elo=1500)
    now_utc = FROZEN_NOW

    f_past_finished = fixture(
        db_session, tourney, t3, t1,
        status="Finished", kickoff=kickoff(-90), stage="Group Stage",
        home_score=1, away_score=0,
    )
    f_past_scheduled = fixture(
        db_session, tourney, t3, t2,
        status="Scheduled", kickoff=kickoff(-60), stage="Group Stage",
    )
    f_future_1 = fixture(
        db_session, tourney, t1, t2,
        status="Scheduled", kickoff=kickoff(50), stage="Group Stage",
        watchability_score=85.0,
    )
    f_future_2 = fixture(
        db_session, tourney, t2, t1,
        status="Scheduled", kickoff=kickoff(52), stage="Group Stage",
        watchability_score=78.0,
    )
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
    grouped = get_grouped_fixtures(db_session, "UTC", tournament_id=tourney.id, now=now_utc)
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
    comp = league(db_session, "Active Filter Test Comp")
    tourney_active = tournament(db_session, comp, status="Active")
    tourney_inactive = tournament(db_session, comp, season="2025/26", status="Completed")
    t1 = team(db_session, "Active Team 1", elo=1700)
    t2 = team(db_session, "Active Team 2", elo=1700)
    now_utc = FROZEN_NOW
    f_active = fixture(db_session, tourney_active, t1, t2, kickoff=kickoff(2), stage="Regular Season")
    f_inactive = fixture(db_session, tourney_inactive, t1, t2, kickoff=kickoff(2), stage="Regular Season")
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
    now_utc = FROZEN_NOW
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


def test_feed_builder_imports_without_odds_cycle():
    """odds.NameNormalizer must not pull FixtureUpserter back through the package init."""
    import backend.services.feed_builder as feed_builder
    from backend.services.odds import NameNormalizer, calculate_default_odds

    assert feed_builder.build_fixtures_feed_cache
    assert NameNormalizer.__module__ == "backend.services.ingestion.normalizer"
    assert calculate_default_odds(1800, 1500)[0] > 1


def test_feed_builder_integration(db_session, monkeypatch, tmp_path):
    """
    Tests build_fixtures_feed_cache producing a non-empty payload and
    properly integrating with get_eligible_fixtures.
    """
    comp = league(db_session, "Feed Test League")
    tourney = tournament(db_session, comp)
    t1 = team(db_session, "Feed Team 1", elo=1750)
    t2 = team(db_session, "Feed Team 2", elo=1720)
    membership(db_session, tourney, t1)
    membership(db_session, tourney, t2)
    now_utc = FROZEN_NOW
    f = fixture(
        db_session, tourney, t1, t2,
        kickoff=kickoff(1), stage="Regular Season", watchability_score=80.0,
    )
    db_session.commit()

    monkeypatch.setattr(feed_builder, "CACHE_FILE_PATH", str(tmp_path / "fixtures_feed_cache.json"))
    feed_payload = build_fixtures_feed_cache(db_session, now=now_utc)
    assert feed_payload is not None
    assert feed_payload["total_fixtures"] >= 1
    assert len(feed_payload["fixtures"]) >= 1
    assert any(m["id"] == f.id for m in feed_payload["fixtures"])


def test_feed_builder_preserves_cache_when_all_enrichment_fails(db_session, monkeypatch, tmp_path):
    comp = league(db_session, "Failed Enrichment League")
    tourney = tournament(db_session, comp)
    home = team(db_session, "Failed Enrichment Home", elo=1700)
    away = team(db_session, "Failed Enrichment Away", elo=1650)
    fixture(db_session, tourney, home, away, kickoff=kickoff(1), stage="Regular Season")
    db_session.commit()

    cache_path = tmp_path / "fixtures_feed_cache.json"
    existing_payload = {"updated_at": "existing", "total_fixtures": 1, "fixtures": [{"id": 999}]}
    cache_path.write_text(json.dumps(existing_payload), encoding="utf-8")
    monkeypatch.setattr(feed_builder, "CACHE_FILE_PATH", str(cache_path))

    def fail_enrichment(*args, **kwargs):
        raise RuntimeError("test enrichment failure")

    monkeypatch.setattr(feed_builder, "enrich_fixture", fail_enrichment)

    result = feed_builder.build_fixtures_feed_cache(db_session, now=FROZEN_NOW)

    assert result == existing_payload
    assert json.loads(cache_path.read_text(encoding="utf-8")) == existing_payload


def test_feed_builder_writes_empty_cache_without_active_tournaments(db_session, monkeypatch, tmp_path):
    cache_path = tmp_path / "fixtures_feed_cache.json"
    monkeypatch.setattr(feed_builder, "CACHE_FILE_PATH", str(cache_path))

    result = feed_builder.build_fixtures_feed_cache(db_session, now=FROZEN_NOW)

    assert result["total_fixtures"] == 0
    assert json.loads(cache_path.read_text(encoding="utf-8")) == result
    assert list(tmp_path.glob("*.tmp")) == []


def test_feed_cache_replace_failure_keeps_the_previous_file(db_session, monkeypatch, tmp_path):
    """A failed publish leaves the previous cache intact and removes the temp file."""
    cache_path = tmp_path / "fixtures_feed_cache.json"
    original = {"updated_at": "old", "total_fixtures": 1, "fixtures": [{"id": 7}]}
    cache_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(feed_builder, "CACHE_FILE_PATH", str(cache_path))

    def fail_replace(src, dst):
        assert os.path.exists(src)
        assert json.loads(cache_path.read_text(encoding="utf-8")) == original
        raise OSError("disk full")

    monkeypatch.setattr(feed_builder.os, "replace", fail_replace)

    with pytest.raises(OSError, match="disk full"):
        feed_builder.build_fixtures_feed_cache(db_session, now=FROZEN_NOW)

    assert json.loads(cache_path.read_text(encoding="utf-8")) == original
    assert list(tmp_path.glob("*.tmp")) == []


def test_score_patch_replace_failure_keeps_the_previous_file(monkeypatch, tmp_path):
    cache_path = tmp_path / "fixtures_feed_cache.json"
    original = {
        "updated_at": "old",
        "total_fixtures": 1,
        "fixtures": [{"id": 7, "status": "Scheduled", "score": "-"}],
    }
    cache_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(feed_builder, "CACHE_FILE_PATH", str(cache_path))

    def fail_replace(src, dst):
        assert json.loads(cache_path.read_text(encoding="utf-8")) == original
        raise OSError("disk full")

    monkeypatch.setattr(feed_builder.os, "replace", fail_replace)

    with pytest.raises(OSError, match="disk full"):
        feed_builder.patch_feed_cache_scores([{"id": 7, "status": "Live", "score": "1-0"}])

    assert json.loads(cache_path.read_text(encoding="utf-8")) == original
    assert list(tmp_path.glob("*.tmp")) == []


def test_eligible_hides_scheduled_unstamped_once_tournament_is_stamped(db_session):
    """Homepage eligibility omits scheduled draw leftovers after a stamped UCL row exists."""
    comp = cup(db_session, "UCL Hide Unstamped", format_engine="league_phase_knockout")
    tourney = tournament(db_session, comp)
    villa = team(db_session, "BSC Young Boys")
    yb_opp = team(db_session, "Aston Villa")
    liv = team(db_session, "Liverpool")
    atl = team(db_session, "Atlético Madrid")

    now_utc = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    draw_row = fixture(
        db_session, tourney, villa, yb_opp,
        status="Scheduled", stamp=None,
        kickoff=datetime(2026, 9, 17, 18, 45, tzinfo=timezone.utc),
    )
    finished_unstamped = fixture(
        db_session, tourney, liv, yb_opp,
        status="Finished", stamp=None,
        kickoff=datetime(2026, 9, 10, 19, 0, tzinfo=timezone.utc),
        home_score=1, away_score=0,
    )
    stamped = fixture(
        db_session, tourney, liv, atl,
        status="Scheduled", stamp="fd_9002",
        kickoff=datetime(2026, 9, 16, 19, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    eligible = crud_fixture.get_eligible_fixtures(
        db_session, tournament_id=tourney.id, now_utc=now_utc
    )
    ids = {f.id for f in eligible}
    assert stamped.id in ids
    assert finished_unstamped.id in ids
    assert draw_row.id not in ids

    recommended = crud_fixture.get_recommended_fixtures(
        db_session, tournament_id=tourney.id, min_score=0.0, include_past=True
    )
    rec_ids = {f.id for f in recommended}
    assert stamped.id in rec_ids
    assert finished_unstamped.id in rec_ids
    assert draw_row.id not in rec_ids
    assert not any(
        f.home_team and f.away_team
        and f.home_team.name == "BSC Young Boys"
        and f.away_team.name == "Aston Villa"
        for f in recommended
    )
