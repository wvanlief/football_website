"""Frozen-clock coverage for the shared eligibility module."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from backend.services.eligibility import eligible_fixtures, select_recommended
from backend.services.queries import get_grouped_fixtures
from tests.factories import FROZEN_NOW, fixture, kickoff, league, team, tournament


def test_select_recommended_threshold_and_fallback_once():
    items = [{"id": 1, "score": 40}, {"id": 2, "score": 80}, {"id": 3, "score": 70}]
    above = select_recommended(items, lambda row: row["score"], min_score=65, min_count=1)
    assert [row["id"] for row in above] == [2, 3]
    topped_up = select_recommended(items, lambda row: row["score"], min_score=65, min_count=3)
    assert [row["id"] for row in topped_up] == [2, 3, 1]


def test_offseason_eligible_fixtures_are_future_only(db_session):
    comp = league(db_session, name="Eligibility Offseason")
    tourney = tournament(db_session, comp)
    home = team(db_session, "Off Home")
    away = team(db_session, "Off Away")
    fixture(db_session, tourney, home, away, kickoff=kickoff(days=-40), stamp="fd_past")
    future = fixture(db_session, tourney, home, away, kickoff=kickoff(days=45), stamp="fd_future")
    db_session.commit()

    rows = eligible_fixtures(db_session, tournament_id=tourney.id, now_utc=FROZEN_NOW)
    assert [row.id for row in rows] == [future.id]


def test_today_and_tomorrow_edges_use_frozen_clock(db_session):
    comp = league(db_session, name="Eligibility Edges")
    tourney = tournament(db_session, comp)
    home = team(db_session, "Edge Home")
    away = team(db_session, "Edge Away")
    today = fixture(db_session, tourney, home, away, kickoff=kickoff(days=0, hour=18), stamp="fd_today")
    tomorrow = fixture(db_session, tourney, home, away, kickoff=kickoff(days=1, hour=18), stamp="fd_tomorrow")
    db_session.commit()

    grouped = get_grouped_fixtures(db_session, "UTC", tournament_id=tourney.id, now=FROZEN_NOW)
    assert [row["id"] for row in grouped["today"]] == [today.id]
    assert [row["id"] for row in grouped["tomorrow"]] == [tomorrow.id]


def test_paris_and_utc_split_a_late_kickoff(db_session):
    """23:30 UTC on the frozen day is still today in UTC and already tomorrow in Paris."""
    comp = league(db_session, name="Eligibility Paris")
    tourney = tournament(db_session, comp)
    home = team(db_session, "Paris Home")
    away = team(db_session, "Paris Away")
    late = fixture(
        db_session,
        tourney,
        home,
        away,
        kickoff=FROZEN_NOW.replace(hour=23, minute=30),
        stamp="fd_late",
    )
    db_session.commit()

    utc = get_grouped_fixtures(db_session, "UTC", tournament_id=tourney.id, now=FROZEN_NOW)
    paris = get_grouped_fixtures(db_session, "Europe/Paris", tournament_id=tourney.id, now=FROZEN_NOW)
    assert [row["id"] for row in utc["today"]] == [late.id]
    assert late.id not in [row["id"] for row in utc["tomorrow"]]
    assert [row["id"] for row in paris["tomorrow"]] == [late.id]
    assert late.id not in [row["id"] for row in paris["today"]]
    paris_today = FROZEN_NOW.astimezone(ZoneInfo("Europe/Paris")).date()
    assert paris_today == (FROZEN_NOW + timedelta(hours=2)).date()
