from pathlib import Path

import pytest

from backend.database import Team

GROUP_JS = Path("frontend/js/group.js").read_text(encoding="utf-8")
REC_JS = Path("frontend/js/recommended.js").read_text(encoding="utf-8")
SHARED_JS = Path("frontend/js/shared.js").read_text(encoding="utf-8")
DATABASE_PY = Path("backend/database.py").read_text(encoding="utf-8")
CLI_PY = Path("backend/cli.py").read_text(encoding="utf-8")

API_SPORTS_CREST_CDN = "https://media.api-sports.io/football/teams/"


def test_group_and_hot_list_pass_team_objects_to_get_flag_url():
    assert "getFlagUrl(match.home_team.name" not in GROUP_JS
    assert "getFlagUrl(match.away_team.name" not in GROUP_JS
    assert "getFlagUrl(match.home_team)" in GROUP_JS
    assert "getFlagUrl(match.home_team.name" not in REC_JS
    assert "getFlagUrl(match.home_team)" in REC_JS


def test_crest_helpers_do_not_construct_api_sports_media_urls():
    assert API_SPORTS_CREST_CDN not in SHARED_JS
    assert API_SPORTS_CREST_CDN not in DATABASE_PY
    assert API_SPORTS_CREST_CDN not in CLI_PY
    assert "/static/badges/${apiId}.png" in SHARED_JS


def test_served_shared_js_keeps_local_badge_paths(client):
    js = client.get("/js/shared.js")
    assert js.status_code == 200
    assert API_SPORTS_CREST_CDN not in js.text
    assert "function getFlagUrl" in js.text
    assert "/static/badges/${apiId}.png" in js.text

    default_badge = client.get("/static/badges/default.png")
    assert default_badge.status_code == 200
    assert default_badge.headers["content-type"].startswith("image/")

    cached = next(
        (path for path in Path("backend/static/badges").glob("*.png") if path.name != "default.png"),
        None,
    )
    if cached is None:
        pytest.skip("no cached club badge PNGs on disk")
    club_badge = client.get(f"/static/badges/{cached.name}")
    assert club_badge.status_code == 200
    assert club_badge.headers["content-type"].startswith("image/")


@pytest.mark.parametrize(
    "team, expected",
    [
        (
            Team(name="Arsenal", logo_url="https://crests.football-data.org/57.png", api_id=42),
            "https://crests.football-data.org/57.png",
        ),
        (
            Team(name="Club Brugge KV", api_id=569, team_type="Club", logo_url="/static/badges/569.png"),
            "/static/badges/569.png",
        ),
        (
            Team(name="Cached Club", api_id=99, team_type="Club"),
            "/static/badges/99.png",
        ),
        (
            Team(name="England", country_code="GB", team_type="National"),
            "https://flagcdn.com/w80/gb.png",
        ),
        (
            Team(name="Unknown"),
            "/static/badges/default.png",
        ),
        (
            Team(
                name="Legacy CDN Club",
                api_id=7,
                logo_url="https://media.api-sports.io/football/teams/7.png",
            ),
            "/static/badges/7.png",
        ),
    ],
)
def test_team_badge_url_never_uses_api_sports_cdn(team, expected):
    assert team.badge_url == expected
    assert API_SPORTS_CREST_CDN not in team.badge_url
    assert "media.api-sports.io" not in team.badge_url
