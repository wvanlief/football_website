"""Execute frontend getFlagUrl via Node so tests fail if it produces API-Sports URLs."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

SHARED_JS = Path("frontend/js/shared.js")
API_SPORTS_MEDIA = "media.api-sports.io"


def _extract_crest_helper_source() -> str:
    src = SHARED_JS.read_text(encoding="utf-8")
    flags_start = src.index("const COUNTRY_FLAGS")
    fn_start = src.index("function getFlagUrl")
    depth = 0
    end = None
    for i, ch in enumerate(src[fn_start:], fn_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise AssertionError("could not extract getFlagUrl from shared.js")
    return src[flags_start:end]


def _eval_get_flag_url(target, size="w40"):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required to execute getFlagUrl")
    helper = _extract_crest_helper_source()
    harness = (
        helper
        + "\nconst target = "
        + json.dumps(target)
        + ";\nconst size = "
        + json.dumps(size)
        + ";\nprocess.stdout.write(String(getFlagUrl(target, size)));\n"
    )
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
        raise AssertionError(result.stderr or "getFlagUrl harness failed")
    return result.stdout


@pytest.mark.parametrize(
    "target, expected",
    [
        ({"name": "Arsenal", "logo_url": "https://crests.football-data.org/57.png"}, "https://crests.football-data.org/57.png"),
        ({"name": "Club Brugge KV", "logo_url": "/static/badges/569.png", "api_id": 569}, "/static/badges/569.png"),
        ({"name": "Cached Club", "api_id": 99}, "/static/badges/99.png"),
        ("England", "https://flagcdn.com/w40/gb-eng.png"),
        ({"name": "Spain"}, "https://flagcdn.com/w40/es.png"),
        (
            {"name": "Legacy", "logo_url": "https://media.api-sports.io/football/teams/7.png", "api_id": 7},
            "/static/badges/7.png",
        ),
        (
            {"name": "Mixed Case Legacy", "logo_url": "https://MEDIA.Api-Sports.IO/football/teams/8.png", "api_id": 8},
            "/static/badges/8.png",
        ),
        (None, "/static/badges/default.png"),
    ],
)
def test_get_flag_url_does_not_rewrite_to_api_sports(target, expected):
    url = _eval_get_flag_url(target)
    assert url == expected
    assert API_SPORTS_MEDIA not in url.lower()
