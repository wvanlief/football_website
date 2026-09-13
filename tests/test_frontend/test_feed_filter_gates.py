"""Execute homepage date/status/competition gates against processHydratedFixtures."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

APP_JS = Path("frontend/js/app.js").read_text(encoding="utf-8")
SHARED_JS = Path("frontend/js/shared.js")


def _extract_process_hydrated() -> str:
    start = APP_JS.index("function processHydratedFixtures")
    end = APP_JS.index("async function fetchFixtures")
    return APP_JS[start:end]


def _extract_chip_filter() -> str:
    start = APP_JS.index("const filterFn = (match) => {")
    end = APP_JS.index("const filteredToday")
    return APP_JS[start:end]


def _shared_helpers() -> str:
    if not SHARED_JS.exists():
        return ""
    src = SHARED_JS.read_text(encoding="utf-8")
    if "function ymdInTimeZone" not in src:
        return ""
    start = src.index("function ymdInTimeZone")
    end = src.index("function getRatingClass") if "function getRatingClass" in src else len(src)
    return src[start:end]


def _eval_js(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required to execute homepage filter gates")
    harness = _shared_helpers() + "\n" + _extract_process_hydrated() + "\n" + body
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
        handle.write(harness)
        harness_path = handle.name
    try:
        result = subprocess.run(
            [node, harness_path],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        Path(harness_path).unlink(missing_ok=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr or "homepage filter harness failed")
    return json.loads(result.stdout)


def _upcoming_ids(grouped: dict) -> set:
    ids = []
    for key in ("today", "tomorrow", "this_week"):
        ids.extend(m["id"] for m in grouped.get(key) or [])
    return set(ids)


def test_process_hydrated_fixtures_drops_stale_scheduled_and_finished():
    """Reproduce the original leak: past Scheduled / Finished must not land in upcoming."""
    now = datetime.now(timezone.utc)
    fixtures = [
        {
            "id": 1,
            "date": (now - timedelta(days=1, hours=2)).isoformat(),
            "status": "Scheduled",
            "watchability": {"overall": 99.0},
        },
        {
            "id": 2,
            "date": (now - timedelta(days=2)).isoformat(),
            "status": "Finished",
            "watchability": {"overall": 40.0},
        },
        {
            "id": 3,
            "date": (now + timedelta(hours=4)).isoformat(),
            "status": "Scheduled",
            "watchability": {"overall": 70.0},
        },
    ]
    grouped = _eval_js(
        "process.stdout.write(JSON.stringify(processHydratedFixtures("
        + json.dumps(fixtures)
        + ", 'UTC')));\n"
    )
    upcoming = _upcoming_ids(grouped)
    assert 1 not in upcoming
    assert 2 not in upcoming
    assert 3 in upcoming
    assert 2 in {m["id"] for m in grouped["finished"]}


def test_homepage_competition_chip_isolates_rows():
    """Adjacent: chip filter keeps only matching competition_name across buckets."""
    now = datetime.now(timezone.utc)
    fixtures = [
        {
            "id": 10,
            "date": now.isoformat(),
            "status": "Scheduled",
            "competition_name": "Premier League",
            "watchability": {"overall": 80.0},
        },
        {
            "id": 11,
            "date": now.isoformat(),
            "status": "Scheduled",
            "competition_name": "La Liga",
            "watchability": {"overall": 79.0},
        },
    ]
    body = (
        "const activeCompFilter = 'Premier League';\n"
        "const activeFixtures = processHydratedFixtures("
        + json.dumps(fixtures)
        + ", 'UTC');\n"
        + _extract_chip_filter()
        + "const filtered = [].concat(\n"
        "  activeFixtures.today.filter(filterFn),\n"
        "  activeFixtures.tomorrow.filter(filterFn),\n"
        "  activeFixtures.this_week.filter(filterFn)\n"
        ");\n"
        "process.stdout.write(JSON.stringify(filtered.map(m => m.id)));\n"
    )
    assert _eval_js(body) == [10]
