"""Regression coverage for date / status / competition filtering (issue #91).

Locks calendar-day upcoming gating in the viewer timezone (`match_date >= today`).
PR #153 (Paris clocks / Next 7 Days) is already on origin/main; this suite does
not encode kickoff `datetime >= now` (GPT Rule 7) and will need a follow-up if
that contract lands.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.database import Competition, Fixture, Team, Tournament, TournamentTeam
import backend.crud.fixture as crud_fixture
from backend.services.enrichment import group_enriched_fixtures
from backend.services.feed_builder import build_fixtures_feed_cache
from backend.services.tournament import get_grouped_fixtures


UPCOMING_KEYS = ("today", "tomorrow", "this_week")


def _naive(dt):
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _seed_league(db, name, status="Active"):
    comp = Competition(name=name, type="League")
    db.add(comp)
    db.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status=status)
    db.add(tourney)
    db.flush()
    home = Team(name=f"{name} Home", elo=1700)
    away = Team(name=f"{name} Away", elo=1680)
    db.add_all([home, away])
    db.flush()
    db.add_all(
        [
            TournamentTeam(tournament_id=tourney.id, team_id=home.id),
            TournamentTeam(tournament_id=tourney.id, team_id=away.id),
        ]
    )
    db.flush()
    return tourney, home, away


def _add_fixture(db, tourney, home, away, date_utc, status="Scheduled", score=None, watchability=70.0):
    kwargs = dict(
        tournament_id=tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        stage="Regular Season",
        status=status,
        date_utc=_naive(date_utc) if getattr(date_utc, "tzinfo", None) else date_utc,
        watchability_score=watchability,
    )
    if score is not None:
        kwargs["home_score"] = score[0]
        kwargs["away_score"] = score[1]
    fixture = Fixture(**kwargs)
    db.add(fixture)
    db.flush()
    return fixture


def _upcoming_ids(grouped):
    ids = []
    for key in UPCOMING_KEYS:
        ids.extend(m["id"] for m in grouped[key])
    return ids


def _assert_upcoming_dates_not_before_today(grouped, now_dt, tz_name="UTC"):
    tz = ZoneInfo(tz_name)
    today = now_dt.astimezone(tz).date()
    for key in UPCOMING_KEYS:
        for match in grouped[key]:
            dt = datetime.fromisoformat(match["date"].replace("Z", "+00:00"))
            assert dt.astimezone(tz).date() >= today, (
                f"{key} contained past-dated fixture {match['id']} on {dt.date()}"
            )
            assert match.get("status") != "Finished"


def test_upcoming_view_excludes_past_dated_scheduled_fixtures(db_session):
    """B12 / #91: a stale Scheduled row from yesterday must not appear as upcoming."""
    tourney, home, away = _seed_league(db_session, "Stale Scheduled League")
    now_utc = datetime.now(timezone.utc)

    stale = _add_fixture(db_session, tourney, home, away, now_utc - timedelta(days=1, hours=2))
    last_month = _add_fixture(
        db_session, tourney, home, away, now_utc - timedelta(days=28), status="Scheduled"
    )
    today_kickoff = now_utc.replace(hour=23, minute=30, second=0, microsecond=0)
    tomorrow_kickoff = (now_utc + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
    today_match = _add_fixture(
        db_session, tourney, home, away, today_kickoff, watchability=80.0
    )
    tomorrow_match = _add_fixture(
        db_session, tourney, home, away, tomorrow_kickoff, watchability=75.0
    )
    db_session.commit()

    eligible = crud_fixture.get_eligible_fixtures(
        db_session, tournament_id=tourney.id, now_utc=now_utc
    )
    eligible_ids = {f.id for f in eligible}
    assert stale.id in eligible_ids  # still inside the -14d rolling window
    assert last_month.id not in eligible_ids

    grouped = get_grouped_fixtures(db_session, "UTC", tournament_id=tourney.id)
    upcoming = _upcoming_ids(grouped)
    assert today_match.id in upcoming
    assert tomorrow_match.id in upcoming
    assert stale.id not in upcoming
    assert last_month.id not in upcoming
    _assert_upcoming_dates_not_before_today(grouped, now_utc)


def test_finished_in_rolling_window_goes_to_finished_not_upcoming(db_session):
    """Adjacent: recent Finished results stay on the results bar, not Today/Week."""
    tourney, home, away = _seed_league(db_session, "Finished Adjacent League")
    now_utc = datetime.now(timezone.utc)
    finished = _add_fixture(
        db_session,
        tourney,
        home,
        away,
        now_utc - timedelta(days=2),
        status="Finished",
        score=(2, 1),
        watchability=90.0,
    )
    live_today = _add_fixture(
        db_session,
        tourney,
        home,
        away,
        now_utc.replace(hour=20, minute=0, second=0, microsecond=0),
        status="Live",
        watchability=88.0,
    )
    future = _add_fixture(
        db_session, tourney, home, away, now_utc + timedelta(days=2), watchability=72.0
    )
    db_session.commit()

    grouped = get_grouped_fixtures(db_session, "UTC", tournament_id=tourney.id)
    upcoming = _upcoming_ids(grouped)
    finished_ids = [m["id"] for m in grouped["finished"]]

    assert finished.id in finished_ids
    assert finished.id not in upcoming
    assert live_today.id in grouped["today"] or live_today.id in upcoming
    assert live_today.id not in finished_ids
    assert future.id in upcoming
    _assert_upcoming_dates_not_before_today(grouped, now_utc)


def test_group_enriched_fixtures_drops_past_calendar_dates_from_upcoming():
    """Pure grouping seam: date < today never lands in upcoming buckets."""
    now_utc = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    fixtures = [
        {
            "id": 1,
            "date": (now_utc - timedelta(days=5)).isoformat(),
            "status": "Scheduled",
            "watchability": {"overall": 99.0},
        },
        {
            "id": 2,
            "date": (now_utc - timedelta(hours=3)).isoformat(),
            "status": "Finished",
            "watchability": {"overall": 40.0},
        },
        {
            "id": 3,
            "date": (now_utc + timedelta(hours=4)).isoformat(),
            "status": "Scheduled",
            "watchability": {"overall": 70.0},
        },
        {
            "id": 4,
            "date": (now_utc + timedelta(days=4)).isoformat(),
            "status": "Scheduled",
            "watchability": {"overall": 80.0},
        },
        {
            "id": 5,
            "date": (now_utc + timedelta(days=20)).isoformat(),
            "status": "Scheduled",
            "watchability": {"overall": 95.0},
        },
    ]
    grouped = group_enriched_fixtures(fixtures, ZoneInfo("UTC"), now_dt=now_utc)
    upcoming = _upcoming_ids(grouped)
    assert 1 not in upcoming
    assert 2 not in upcoming
    assert grouped["today"][0]["id"] == 3
    assert 4 in upcoming
    assert 5 not in upcoming  # beyond the 8-day this-week window
    assert 2 in [m["id"] for m in grouped["finished"]]
    _assert_upcoming_dates_not_before_today(grouped, now_utc)


def test_offseason_fallback_excludes_legacy_and_respects_now_gate(db_session):
    """Off-season fallback is date_utc >= now; past Scheduled leftovers stay out."""
    tourney, home, away = _seed_league(db_session, "Offseason Gate League")
    now_utc = datetime.now(timezone.utc)
    # Outside the -14/+30 rolling window so the future-only fallback is used.
    just_before_window = _add_fixture(
        db_session, tourney, home, away, now_utc - timedelta(days=40)
    )
    _add_fixture(db_session, tourney, home, away, now_utc - timedelta(days=90))
    future_a = _add_fixture(
        db_session, tourney, home, away, now_utc + timedelta(days=45), watchability=81.0
    )
    future_b = _add_fixture(
        db_session, tourney, home, away, now_utc + timedelta(days=46), watchability=60.0
    )
    db_session.commit()

    eligible = crud_fixture.get_eligible_fixtures(
        db_session, tournament_id=tourney.id, now_utc=now_utc
    )
    ids = {f.id for f in eligible}
    assert ids == {future_a.id, future_b.id}
    assert just_before_window.id not in ids
    for fixture in eligible:
        assert fixture.date_utc >= _naive(now_utc)

    grouped = get_grouped_fixtures(db_session, "UTC", tournament_id=tourney.id)
    assert grouped["is_offseason"] is True
    upcoming = _upcoming_ids(grouped)
    assert set(upcoming) == {future_a.id, future_b.id}
    _assert_upcoming_dates_not_before_today(grouped, now_utc)


def test_feed_cache_grouping_hides_in_window_stale_rows(db_session, monkeypatch, tmp_path):
    """Adjacent: rolling-window cache may keep leftovers; grouping still gates upcoming."""
    cache_path = tmp_path / "fixtures_feed_cache.json"
    monkeypatch.setattr(
        "backend.services.feed_builder.CACHE_FILE_PATH", str(cache_path)
    )

    tourney, home, away = _seed_league(db_session, "Feed Stale League")
    now_utc = datetime.now(timezone.utc)
    stale = _add_fixture(db_session, tourney, home, away, now_utc - timedelta(days=3))
    future = _add_fixture(
        db_session, tourney, home, away, now_utc + timedelta(days=2), watchability=77.0
    )
    db_session.commit()

    payload = build_fixtures_feed_cache(db_session)
    cached_ids = {m["id"] for m in payload["fixtures"]}
    assert stale.id in cached_ids
    assert future.id in cached_ids

    grouped = group_enriched_fixtures(
        payload["fixtures"], ZoneInfo("UTC"), now_dt=now_utc
    )
    upcoming = _upcoming_ids(grouped)
    assert stale.id not in upcoming
    assert future.id in upcoming
    _assert_upcoming_dates_not_before_today(grouped, now_utc)


def test_competition_filter_isolates_fixtures_on_api(client, db_session):
    """Selecting one competition/tournament must not leak the other league's matches."""
    premier, p_home, p_away = _seed_league(db_session, "Premier League Filter")
    laliga, l_home, l_away = _seed_league(db_session, "La Liga Filter")
    now_utc = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    today_kickoff = now_utc.replace(hour=23, minute=0, second=0, microsecond=0)
    pl_match = _add_fixture(
        db_session, premier, p_home, p_away, today_kickoff, watchability=85.0
    )
    ll_match = _add_fixture(
        db_session, laliga, l_home, l_away, today_kickoff.replace(minute=30), watchability=82.0
    )
    db_session.commit()

    all_today = client.get("/api/fixtures").json()["today"]
    all_ids = {m["id"] for m in all_today}
    assert pl_match.id in all_ids
    assert ll_match.id in all_ids

    premier_payload = client.get(f"/api/fixtures?tournament_id={premier.id}").json()
    laliga_payload = client.get(f"/api/fixtures?tournament_id={laliga.id}").json()
    premier_ids = set(_upcoming_ids(premier_payload))
    laliga_ids = set(_upcoming_ids(laliga_payload))
    assert premier_ids == {pl_match.id}
    assert laliga_ids == {ll_match.id}

    premier_grouped = get_grouped_fixtures(db_session, "UTC", tournament_id=premier.id)
    laliga_grouped = get_grouped_fixtures(db_session, "UTC", tournament_id=laliga.id)
    assert premier_grouped["today"][0]["competition_name"] == "Premier League Filter"
    assert laliga_grouped["today"][0]["competition_name"] == "La Liga Filter"


def test_viewer_timezone_excludes_previous_local_calendar_day():
    """#153 merge-order: a UTC 'today' kickoff that is yesterday in Paris is not upcoming."""
    now_utc = datetime(2026, 9, 13, 22, 0, tzinfo=timezone.utc)
    fixtures = [
        {
            "id": 1,
            "date": "2026-09-13T15:30:00+00:00",
            "status": "Scheduled",
            "watchability": {"overall": 91.0},
        },
        {
            "id": 2,
            "date": "2026-09-14T18:00:00+00:00",
            "status": "Scheduled",
            "watchability": {"overall": 80.0},
        },
    ]
    grouped = group_enriched_fixtures(fixtures, ZoneInfo("Europe/Paris"), now_dt=now_utc)
    upcoming = _upcoming_ids(grouped)
    assert 1 not in upcoming
    assert 2 in upcoming
    _assert_upcoming_dates_not_before_today(grouped, now_utc, tz_name="Europe/Paris")


def test_offseason_fallback_empty_when_only_legacy_past_exists(db_session):
    """Rule 8 adjacent: no future records means upcoming stays empty, not first Scheduled leftover."""
    tourney, home, away = _seed_league(db_session, "Legacy Only League")
    now_utc = datetime.now(timezone.utc)
    leftover = _add_fixture(
        db_session, tourney, home, away, now_utc - timedelta(days=40)
    )
    db_session.commit()

    eligible = crud_fixture.get_eligible_fixtures(
        db_session, tournament_id=tourney.id, now_utc=now_utc
    )
    assert eligible == []
    assert leftover.id not in {f.id for f in eligible}

    grouped = get_grouped_fixtures(db_session, "UTC", tournament_id=tourney.id)
    assert _upcoming_ids(grouped) == []
    _assert_upcoming_dates_not_before_today(grouped, now_utc)


def test_postponed_past_date_is_not_upcoming(db_session):
    """Adjacent status: Postponed leftover with a past kickoff stays out of upcoming."""
    tourney, home, away = _seed_league(db_session, "Postponed Adjacent League")
    now_utc = datetime.now(timezone.utc)
    postponed = _add_fixture(
        db_session,
        tourney,
        home,
        away,
        now_utc - timedelta(days=4),
        status="Postponed",
    )
    scheduled = _add_fixture(
        db_session, tourney, home, away, now_utc + timedelta(days=1)
    )
    db_session.commit()

    grouped = get_grouped_fixtures(db_session, "UTC", tournament_id=tourney.id)
    upcoming = _upcoming_ids(grouped)
    assert postponed.id not in upcoming
    assert scheduled.id in upcoming
    _assert_upcoming_dates_not_before_today(grouped, now_utc)
