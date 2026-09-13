from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from backend.services.enrichment import (
    group_enriched_fixtures,
    localize_fixture_display,
    week_spotlight_matches,
)


def _watch(score, label=None):
    return {"overall": score, "percentile": score, "tier": "Must Watch", "context_label": label}


def test_localize_fixture_display_paris_derby_clock():
    utc_feed = {
        "id": 3916,
        "date": "2026-09-13T15:30:00+00:00",
        "formatted_time": "15:30",
        "formatted_date": "September 13, 2026",
        "formatted_date_short": "Sep 13",
        "watchability": {"overall": 91.3, "context_label": None},
    }

    paris = localize_fixture_display(utc_feed, ZoneInfo("Europe/Paris"))

    assert utc_feed["formatted_time"] == "15:30"
    assert paris["formatted_time"] == "17:30"
    assert paris["formatted_date"] == "September 13, 2026"
    assert paris["date"].startswith("2026-09-13T17:30:00")


def test_localize_fixture_display_fixes_midnight_crossing_hours():
    """#133: late UTC kickoff moves calendar day and the clock together."""
    utc_feed = {
        "id": 99,
        "date": "2026-09-13T22:00:00+00:00",
        "formatted_time": "22:00",
        "formatted_date": "September 13, 2026",
        "formatted_date_short": "Sep 13",
    }

    paris = localize_fixture_display(utc_feed, ZoneInfo("Europe/Paris"))

    assert paris["formatted_time"] == "00:00"
    assert paris["formatted_date"] == "September 14, 2026"
    assert paris["formatted_date_short"] == "Sep 14"
    assert paris["date"].startswith("2026-09-14T00:00:00")


def test_group_enriched_fixtures_recomputes_clock_without_mutating_cache():
    cached = {
        "id": 3916,
        "date": "2026-09-13T15:30:00+00:00",
        "formatted_time": "15:30",
        "status": "Scheduled",
        "watchability": {"overall": 91.3, "context_label": None},
    }
    now = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)

    grouped = group_enriched_fixtures([cached], ZoneInfo("Europe/Paris"), now_dt=now)

    assert cached["formatted_time"] == "15:30"
    assert grouped["today"][0]["formatted_time"] == "17:30"
    assert grouped["today"][0]["watchability"]["context_label"] == "🔥 #1 Match Today"


def test_week_spotlight_keeps_tomorrow_derby():
    tomorrow = {
        "id": 3916,
        "date": "2026-09-13T15:30:00+00:00",
        "status": "Scheduled",
        "watchability": _watch(91.3),
    }
    later = {
        "id": 3927,
        "date": "2026-09-20T15:30:00+00:00",
        "status": "Scheduled",
        "watchability": _watch(77.1),
    }
    now = datetime(2026, 9, 12, 16, 0, tzinfo=timezone.utc)
    grouped = group_enriched_fixtures(
        [tomorrow, later],
        ZoneInfo("Europe/Paris"),
        now_dt=now,
    )

    assert grouped["tomorrow"][0]["id"] == 3916
    assert [m["id"] for m in grouped["this_week"]] == [3927]

    spotlight = week_spotlight_matches(grouped["tomorrow"], grouped["this_week"])
    assert spotlight[0]["id"] == 3916
    assert spotlight[0]["formatted_time"] == "17:30"
