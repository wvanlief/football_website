from pathlib import Path

CSS_DIR = Path("frontend/css")
PAGES = {
    "frontend/index.html": ["base.css", "cards.css", "hero.css"],
    "frontend/recommended.html": ["base.css", "cards.css"],
    "frontend/calendar.html": ["base.css", "cards.css"],
    "frontend/team.html": ["base.css", "cards.css"],
    "frontend/group.html": ["base.css", "cards.css", "standings.css"],
    "frontend/bracket.html": ["base.css", "bracket.css"],
}
MODULE_FILES = ["base.css", "cards.css", "hero.css", "standings.css", "bracket.css"]


def _css_text() -> str:
    return "\n".join((CSS_DIR / name).read_text(encoding="utf-8") for name in MODULE_FILES)


def test_css_modules_exist_and_pages_load_view_sheets():
    for name in MODULE_FILES:
        assert (CSS_DIR / name).is_file(), name
    for page, sheets in PAGES.items():
        html = Path(page).read_text(encoding="utf-8")
        assert "styles.css" not in html
        for sheet in sheets:
            assert sheet in html, f"{page} missing {sheet}"
        for name in MODULE_FILES:
            if name not in sheets:
                assert name not in html, f"{page} should not load {name}"


def test_important_count_is_limited_to_matrix_overrides():
    combined = _css_text()
    count = combined.count("!important")
    assert count <= 4, count
    assert "proto-variant-c" not in combined
    assert "proto-switcher" not in combined
    assert "cmd-palette-modal" not in combined
    standings = (CSS_DIR / "standings.css").read_text(encoding="utf-8")
    assert "border-collapse: separate !important" in standings
    assert ".clickable-matrix-cell:hover" in standings
    assert standings.count("!important") == 4


def test_css_modules_are_served(client):
    for name in MODULE_FILES:
        response = client.get(f"/css/{name}")
        assert response.status_code == 200, name
        assert len(response.text) > 100

    home = client.get("/")
    assert home.status_code == 200
    assert "base.css?v=1.1.0" in home.text
    assert "hero.css?v=1.1.0" in home.text
    assert "standings.css" not in home.text
    assert "bracket.css" not in home.text

    group = client.get("/group/A")
    assert group.status_code == 200
    assert "standings.css?v=1.1.0" in group.text
    assert "hero.css" not in group.text

    bracket = client.get("/bracket")
    assert bracket.status_code == 200
    assert "bracket.css?v=1.1.0" in bracket.text
    assert "hero.css" not in bracket.text
