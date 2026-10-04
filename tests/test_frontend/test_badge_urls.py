from pathlib import Path

from backend.database import Team

from tests.conftest import replica_badge_key, replica_club

GROUP_JS = Path("frontend/js/group.js").read_text(encoding="utf-8")
REC_JS = Path("frontend/js/recommended.js").read_text(encoding="utf-8")
SHARED_JS = Path("frontend/js/shared.js").read_text(encoding="utf-8")
DATABASE_PY = Path("backend/database.py").read_text(encoding="utf-8")

API_SPORTS_CREST_CDN = "https://media.api-sports.io/football/teams/"


def test_group_and_hot_list_pass_team_objects_to_get_flag_url():
    assert "getFlagUrl(match.home_team.name" not in GROUP_JS
    assert "getFlagUrl(match.away_team.name" not in GROUP_JS
    assert "getFlagUrl(match.home_team)" in GROUP_JS
    assert "getFlagUrl(match.home_team.name" not in REC_JS
    assert "getFlagUrl(match.home_team)" in REC_JS
    assert "media.api-sports.io/football/teams/" in SHARED_JS


def test_crest_helpers_rewrite_local_badge_paths_to_api_sports_cdn():
    assert API_SPORTS_CREST_CDN in SHARED_JS
    assert API_SPORTS_CREST_CDN in DATABASE_PY


def test_served_shared_js_rewrites_local_badge_paths(client):
    js = client.get("/js/shared.js")
    assert js.status_code == 200
    assert API_SPORTS_CREST_CDN in js.text
    assert "function getFlagUrl" in js.text


def test_team_badge_url_prefers_http_crest_then_api_sports_cdn():
    arsenal = Team(name="Arsenal", logo_url="https://crests.football-data.org/57.png", api_id=42)
    assert arsenal.badge_url == "https://crests.football-data.org/57.png"

    brugge = Team(name="Club Brugge KV", api_id=569, team_type="Club", logo_url="/static/badges/569.png")
    assert brugge.badge_url == f"{API_SPORTS_CREST_CDN}569.png"

    cached = Team(name="Cached Club", api_id=99, team_type="Club")
    assert cached.badge_url == f"{API_SPORTS_CREST_CDN}99.png"

    england = Team(name="England", country_code="GB", team_type="National")
    assert england.badge_url == "https://flagcdn.com/w80/gb.png"

    unknown = Team(name="Unknown")
    assert unknown.badge_url == "/static/badges/default.png"

    legacy = Team(
        name="Legacy CDN Club",
        api_id=7,
        logo_url="https://media.api-sports.io/football/teams/7.png",
    )
    assert legacy.badge_url == f"{API_SPORTS_CREST_CDN}7.png"


def test_reported_clubs_keep_their_own_badge_ids(replica_db):
    """Issue 27: replica rows must not share another club's stored badge key."""
    sparta = replica_club(replica_db, "Sparta Praha")
    besiktas = replica_club(replica_db, "Besiktas")
    zagreb = replica_club(replica_db, "Dinamo Zagreb")
    gent = replica_club(replica_db, "Gent")
    qarabag = replica_club(replica_db, "Qarabag")

    sparta_key = replica_badge_key(sparta)
    besiktas_key = replica_badge_key(besiktas)
    zagreb_key = replica_badge_key(zagreb)
    gent_key = replica_badge_key(gent)
    qarabag_key = replica_badge_key(qarabag)

    assert sparta_key
    assert besiktas_key
    assert zagreb_key
    assert gent_key
    assert qarabag_key
    assert sparta_key != besiktas_key
    assert zagreb_key != gent_key
    assert sparta_key in sparta.badge_url
    assert besiktas_key not in sparta.badge_url
    assert zagreb_key in zagreb.badge_url
    assert gent_key not in zagreb.badge_url
    assert qarabag.badge_url != "/static/badges/default.png"
    assert qarabag_key in qarabag.badge_url


def test_logo_only_alias_does_not_borrow_another_clubs_crest(replica_db):
    """Adjacent case: a draw-name replica row keeps its own stored crest path."""
    orphan = replica_club(replica_db, "Sparta Prague")
    besiktas = replica_club(replica_db, "Besiktas")
    orphan_key = replica_badge_key(orphan)
    besiktas_key = replica_badge_key(besiktas)
    assert orphan.logo_url
    assert orphan.badge_url == orphan.logo_url or (orphan_key and orphan_key in orphan.badge_url)
    assert besiktas_key
    assert besiktas_key not in (orphan.logo_url or "")
    if orphan.api_id is None:
        assert orphan.badge_url == orphan.logo_url
