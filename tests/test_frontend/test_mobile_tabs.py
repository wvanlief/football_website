"""Homepage mobile panes: Feed, Competitions drawer, Inspector."""
from pathlib import Path

INDEX = Path("frontend/index.html").read_text(encoding="utf-8")
NAV = Path("frontend/js/navigation.js").read_text(encoding="utf-8")
APP = Path("frontend/js/app.js").read_text(encoding="utf-8")
CSS = Path("frontend/css/base.css").read_text(encoding="utf-8")
AGENTS = Path("AGENTS.md").read_text(encoding="utf-8")


def test_homepage_exposes_three_mobile_tabs():
    assert 'id="mobile-tab-bar"' in INDEX
    assert 'data-mobile-pane="feed"' in INDEX
    assert 'data-mobile-pane="competitions"' in INDEX
    assert 'data-mobile-pane="inspector"' in INDEX
    assert ">Feed<" in INDEX
    assert ">Competitions<" in INDEX
    assert ">Inspector<" in INDEX


def test_mobile_tabs_switch_panes_and_accept_horizontal_swipes():
    assert "function showMobilePane" in NAV
    assert "window.showMobilePane = showMobilePane" in APP or "window.showMobilePane = showMobilePane" in NAV
    assert "touchend" in NAV
    assert "mobile-pane-inspector" in NAV
    assert "max-width: 768px" in CSS
    assert ".mobile-tab-bar" in CSS
    assert "body.mobile-pane-inspector" in CSS


def test_narrow_hero_opens_side_inspector():
    assert "width < 768" in APP
    assert "showMobilePane('inspector')" in APP


def test_agents_md_names_all_ten_engineering_rules():
    for title in (
        "Smallest-layer-first",
        "Prove the root cause",
        "No unverified claims",
        "No production-first testing",
        "Preserve scope",
        "One source of truth",
        "Upcoming means future",
        "No stale fallback",
        "Regression test user-reported bugs",
        "Honest empty states",
    ):
        assert title in AGENTS
