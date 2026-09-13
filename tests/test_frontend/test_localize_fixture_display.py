"""Execute frontend kickoff localization via Node."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

SHARED_JS = Path("frontend/js/shared.js")


def _extract_helpers() -> str:
    src = SHARED_JS.read_text(encoding="utf-8")
    start = src.index("function ymdInTimeZone")
    end = src.index("function getRatingClass")
    return src[start:end]


def _eval_js(expression: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required to execute timezone helpers")
    harness = _extract_helpers() + "\nprocess.stdout.write(JSON.stringify(" + expression + "));\n"
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
        raise AssertionError(result.stderr or "timezone helper harness failed")
    return json.loads(result.stdout)


def test_localize_fixture_display_paris_derby_clock():
    match = {
        "date": "2026-09-13T15:30:00+00:00",
        "formatted_time": "15:30",
        "formatted_date": "September 13, 2026",
        "formatted_date_short": "Sep 13",
    }
    localized = _eval_js(
        "localizeFixtureDisplay(" + json.dumps(match) + ", 'Europe/Paris')"
    )
    assert localized["formatted_time"] == "17:30"
    assert localized["formatted_date"] == "September 13, 2026"


def test_localize_fixture_display_midnight_crossing():
    match = {
        "date": "2026-09-13T22:00:00+00:00",
        "formatted_time": "22:00",
        "formatted_date": "September 13, 2026",
        "formatted_date_short": "Sep 13",
    }
    localized = _eval_js(
        "localizeFixtureDisplay(" + json.dumps(match) + ", 'Europe/Paris')"
    )
    assert localized["formatted_time"] == "00:00"
    assert localized["formatted_date"] == "September 14, 2026"
    assert localized["formatted_date_short"] == "Sep 14"


def test_add_calendar_days_is_timezone_safe():
    assert _eval_js("addCalendarDays('2026-09-12', 1)") == "2026-09-13"
    assert _eval_js("addCalendarDays('2026-09-12', 8)") == "2026-09-20"
