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


def test_tab_relationships_and_keyboard_switching():
    import json
    import subprocess
    from html.parser import HTMLParser

    class ElementsById(HTMLParser):
        def __init__(self):
            super().__init__()
            self.elements = {}

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if 'id' in attributes:
                self.elements[attributes['id']] = attributes

    parser = ElementsById()
    parser.feed(INDEX)
    elements = parser.elements
    assert elements['mobile-tab-bar']['role'] == 'tablist'
    for pane in ('feed', 'competitions', 'inspector'):
        tab = elements[f'mobile-tab-{pane}']
        panel = elements[tab['aria-controls']]
        assert tab['role'] == 'tab'
        assert panel['role'] == 'tabpanel'
        assert panel['aria-labelledby'] == tab['id']
    mobile_css = CSS[CSS.index('MOBILE BOTTOM TABS'):]
    assert '@media (width < 768px)' in mobile_css
    controller = NAV[NAV.index('    // 6. Off-Canvas'):NAV.index('    // 7. Top Inline')]
    harness = r'''
const assert = require('node:assert/strict');
const attributes = ATTRIBUTES;
let focused;
function element(attrs = {}) {
    const classes = new Set((attrs.class || '').split(' '));
    return {
        attrs, listeners: {}, inert: false,
        getAttribute(name) { return this.attrs[name]; },
        setAttribute(name, value) { this.attrs[name] = value; },
        removeAttribute(name) { delete this.attrs[name]; },
        addEventListener(name, fn) { this.listeners[name] = fn; },
        focus() { focused = this; },
        contains(target) { return target === this || (this.attrs.id === 'offcanvas-sidebar' && target === elements['close-drawer-btn']); },
        classList: {
            contains(name) { return classes.has(name); },
            add(name) { classes.add(name); },
            remove(name) { classes.delete(name); },
            toggle(name, force = !classes.has(name)) {
                if (force) classes.add(name); else classes.delete(name);
            },
        },
    };
}
const elements = Object.fromEntries(Object.entries(attributes).map(([id, attrs]) => [id, element(attrs)]));
const tabs = ['feed', 'competitions', 'inspector'].map(p => elements['mobile-tab-' + p]);
elements['mobile-tab-bar'].querySelectorAll = () => tabs;
const document = {
    body: element(), listeners: {},
    get activeElement() { return focused; },
    getElementById: id => elements[id], querySelectorAll: () => [],
    addEventListener(name, fn) { this.listeners[name] = fn; },
};
const window = {innerWidth: 767, listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; }};
CONTROLLER
function selected(index) {
    tabs.forEach((tab, i) => {
        assert.equal(tab.attrs['aria-selected'], String(i === index));
        assert.equal(tab.tabIndex, i === index ? 0 : -1);
        const panel = elements[tab.attrs['aria-controls']];
        assert.equal(panel.inert, i !== index);
        assert.equal(panel.attrs['aria-hidden'], String(i !== index));
    });
}
function key(index, key) {
    let prevented = false;
    tabs[index].listeners.keydown({key, preventDefault() { prevented = true; }});
    assert.equal(prevented, true);
}
selected(0);
key(0, 'ArrowLeft'); selected(2); assert.equal(focused, tabs[2]);
assert(document.body.classList.contains('mobile-pane-inspector'));
key(2, 'ArrowRight'); selected(0); assert.equal(focused, tabs[0]);
key(0, 'End'); selected(2);
key(2, 'Home'); selected(0);
key(0, 'ArrowRight'); selected(1);
assert(elements['offcanvas-sidebar'].classList.contains('open'));
elements['close-drawer-btn'].focus();
elements['close-drawer-btn'].listeners.click(); selected(0);
assert.equal(focused, tabs[0]);
tabs[2].listeners.click(); selected(2);
window.innerWidth = 768; window.listeners.resize();
assert(!document.body.classList.contains('mobile-pane-inspector'));
for (const tab of tabs) {
    const panel = elements[tab.attrs['aria-controls']];
    assert.equal(panel.inert, false);
    assert.equal(panel.attrs['aria-hidden'], undefined);
}
window.innerWidth = 767; window.listeners.resize(); selected(0);
'''.replace('ATTRIBUTES', json.dumps(elements)).replace('CONTROLLER', controller)
    result = subprocess.run(['node', '-e', harness], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
