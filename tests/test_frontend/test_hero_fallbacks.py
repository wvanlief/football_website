from pathlib import Path

APP_JS = Path("frontend/js/app.js").read_text(encoding="utf-8")
HERO_CSS = Path("frontend/css/hero.css").read_text(encoding="utf-8")


def test_fabricated_hero_fallback_arrays_are_gone():
    assert "HERO_FALLBACK_TODAY" not in APP_JS
    assert "HERO_FALLBACK_WEEK" not in APP_JS
    assert "Finalissima" not in APP_JS
    assert "Grand Final" not in APP_JS
    assert "Derby d\\'Italia" not in APP_JS
    assert "odds: { home: 2.35" not in APP_JS


def test_hero_spotlight_renders_offseason_and_next_match_notices():
    assert "data-hero-empty" in APP_JS
    assert "No Matches Today" in APP_JS
    assert "Off-Season" in APP_JS
    assert "Next match:" in APP_JS
    assert "renderHeroEmptyCard" in APP_JS
    assert ".hero-empty-card" in HERO_CSS


def test_hero_assets_are_served_without_fallbacks(client):
    js = client.get("/js/app.js")
    assert js.status_code == 200
    assert "HERO_FALLBACK_TODAY" not in js.text
    assert "data-hero-empty" in js.text

    css = client.get("/css/hero.css")
    assert css.status_code == 200
    assert ".hero-empty-card" in css.text

    home = client.get("/")
    assert home.status_code == 200
    assert "hero-match-spotlight" in home.text
    assert "app.js?v=1.0.9" in home.text
    assert "hero.css?v=1.1.0" in home.text
