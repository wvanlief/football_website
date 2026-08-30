import pytest
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from backend.database import Fixture, Tournament, Competition, Team, FixtureOdds
from backend.scoring import calculate_global_percentile, get_score_tier
import backend.crud.fixture as crud_fixture
from backend.services.tournament import group_enriched_fixtures, enrich_fixture, get_recommended_fixtures

def test_global_percentile_and_tier_calculation():
    # Boundary checks
    assert calculate_global_percentile(0.0) == 0.0
    assert calculate_global_percentile(100.0) == 100.0
    assert calculate_global_percentile(None) == 0.0
    
    # Calibration checks (based on empirical distribution)
    # p50 (median) ~ 59.4
    p50 = calculate_global_percentile(59.4)
    assert 49.0 <= p50 <= 51.0
    
    # p80 ~ 65.4
    p80 = calculate_global_percentile(65.4)
    assert 79.0 <= p80 <= 81.0
    
    # p95 ~ 71.7
    p95 = calculate_global_percentile(71.7)
    assert 94.0 <= p95 <= 96.0
    
    # Monotonicity
    scores = [30.0, 45.0, 55.0, 60.0, 65.0, 70.0, 75.0, 85.0, 95.0]
    percentiles = [calculate_global_percentile(s) for s in scores]
    for i in range(len(percentiles) - 1):
        assert percentiles[i] <= percentiles[i + 1]

    # Tier mapping checks
    assert get_score_tier(90.0) == "Must Watch"
    assert get_score_tier(72.0) == "Must Watch"
    assert get_score_tier(71.7) == "Must Watch"
    assert get_score_tier(68.0) == "Recommended"
    assert get_score_tier(65.0) == "Recommended"
    assert get_score_tier(55.0) == "Average"
    assert get_score_tier(45.0) == "Average"
    assert get_score_tier(30.0) == "Skip"

def test_recommended_fixtures_top_7_fallback(db_session):
    # Create competition & tournament
    comp = Competition(name="Test League", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
    db_session.add(tourney)
    db_session.flush()

    # Create 10 low-scoring matches (all below 65.0 threshold)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    for i in range(10):
        t1 = Team(name=f"Team A{i}", elo=1500)
        t2 = Team(name=f"Team B{i}", elo=1500)
        db_session.add_all([t1, t2])
        db_session.flush()

        score = 50.0 + i  # scores from 50.0 to 59.0 (all < 65.0)
        fix = Fixture(
            tournament_id=tourney.id,
            home_team_id=t1.id,
            away_team_id=t2.id,
            date_utc=now_utc + timedelta(days=i + 1),
            stage="Regular Season",
            status="Scheduled",
            watchability_score=score
        )
        db_session.add(fix)
    db_session.commit()

    # Query recommended fixtures: even though 0 meet >= 65.0, Top 7 fallback should return exactly 7
    recs = crud_fixture.get_recommended_fixtures(db_session, tournament_id=tourney.id, min_score=65.0, min_count=7, include_past=True)
    assert len(recs) == 7
    # Should be sorted descending by watchability_score
    scores = [f.watchability_score for f in recs]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 59.0
    assert scores[-1] == 53.0

def test_recommended_fixtures_high_quality_passthrough(db_session):
    comp = Competition(name="Elite Cup", type="Cup", format_engine="cup")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
    db_session.add(tourney)
    db_session.flush()

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    # Create 9 matches with high scores (>= 65.0)
    for i in range(9):
        t1 = Team(name=f"Elite A{i}", elo=1800)
        t2 = Team(name=f"Elite B{i}", elo=1800)
        db_session.add_all([t1, t2])
        db_session.flush()

        fix = Fixture(
            tournament_id=tourney.id,
            home_team_id=t1.id,
            away_team_id=t2.id,
            date_utc=now_utc + timedelta(days=i + 1),
            stage="Regular Season",
            status="Scheduled",
            watchability_score=68.0 + i  # 68.0 to 76.0 (all >= 65.0)
        )
        db_session.add(fix)
    db_session.commit()

    recs = crud_fixture.get_recommended_fixtures(db_session, tournament_id=tourney.id, min_score=65.0, min_count=7, include_past=True)
    assert len(recs) == 9

def test_group_enriched_fixtures_contextual_labels():
    target_tz = ZoneInfo("UTC")
    now_dt = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)

    # 1 today fixture
    f_today1 = {
        "id": 1,
        "date": "2026-08-30T15:00:00+00:00",
        "status": "Scheduled",
        "watchability": {"overall": 62.0, "percentile": 60.0, "tier": "Average", "context_label": None}
    }
    f_today2 = {
        "id": 2,
        "date": "2026-08-30T19:00:00+00:00",
        "status": "Scheduled",
        "watchability": {"overall": 75.0, "percentile": 96.0, "tier": "Must Watch", "context_label": None}
    }

    # 4 week fixtures
    week_fixtures_raw = [
        {"id": 10 + i, "date": f"2026-09-0{i+2}T18:00:00+00:00", "status": "Scheduled", "watchability": {"overall": 70.0 + i, "percentile": 85.0, "tier": "Recommended", "context_label": None}}
        for i in range(4)
    ]

    all_fixtures = [f_today1, f_today2] + week_fixtures_raw
    grouped = group_enriched_fixtures(all_fixtures, target_tz, now_dt=now_dt)

    # Check today top match has "#1 Match Today"
    today_list = grouped["today"]
    assert len(today_list) == 2
    match_75 = next(m for m in today_list if m["id"] == 2)
    assert match_75["watchability"]["context_label"] == "🔥 #1 Match Today"

    # Check this_week rankings
    this_week = grouped["this_week"]
    assert len(this_week) == 4
    # Top match in week should have #1 This Week
    assert this_week[0]["watchability"]["context_label"] == "🏆 #1 This Week"
    assert this_week[1]["watchability"]["context_label"] == "Top 3 This Week"
    assert this_week[2]["watchability"]["context_label"] == "Top 3 This Week"

def test_api_fixtures_recommended_response(client, db_session):
    comp = Competition(name="API Test League", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
    db_session.add(tourney)
    db_session.flush()

    t1 = Team(name="API Team 1", elo=1700)
    t2 = Team(name="API Team 2", elo=1700)
    db_session.add_all([t1, t2])
    db_session.flush()

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    fix = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        date_utc=now_utc + timedelta(days=2),
        stage="Regular Season",
        status="Scheduled",
        watchability_score=78.5,
        competitiveness_score=80.0,
        odds_score=75.0,
        form_score=70.0,
        narrative_score=85.0
    )
    db_session.add(fix)
    db_session.flush()
    odds = FixtureOdds(fixture_id=fix.id, recorded_at=now_utc, odds_home=2.1, odds_draw=3.2, odds_away=3.4)
    db_session.add(odds)
    db_session.commit()

    res = client.get("/api/fixtures/recommended")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    item = data[0]
    assert "watchability" in item
    assert "percentile" in item["watchability"]
    assert "tier" in item["watchability"]
    assert item["watchability"]["tier"] == "Must Watch"
    assert item["watchability"]["percentile"] >= 95.0
