"""Exercise score polling with deferred responses and a minimal card DOM in Node."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("scenario", ["missing_score", "out_of_order", "failed_newer_poll"])
def test_score_polling(scenario):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for score polling tests")
    source = Path("frontend/js/app.js").read_text()
    state = source[source.index("    // Local state"):source.index("    function formatRelativeTime")]
    helpers = source[source.index("    function rememberLiveScore"):source.index("    function renderResultsBar")]
    harness = r"""
const assert = require('node:assert/strict');
class Element {
    constructor(className = '', text = '') {
        this.className = className;
        this.textContent = text;
        this.children = [];
    }
    append(...nodes) { nodes.forEach(node => this.appendChild(node)); }
    appendChild(node) { node.parent = this; this.children.push(node); }
    insertBefore(node, next) {
        node.parent = this;
        this.children.splice(this.children.indexOf(next), 0, node);
    }
    remove() { this.parent.children = this.parent.children.filter(node => node !== this); }
    querySelectorAll(selector) {
        const classes = selector.split(',').map(s => s.trim().slice(1));
        return this.children.flatMap(node => [
            ...(classes.some(c => node.className.split(' ').includes(c)) ? [node] : []),
            ...node.querySelectorAll(selector),
        ]);
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    getAttribute(name) { return name === 'data-fixture-id' ? '1' : null; }
}
const card = new Element('match-card');
const center = new Element('match-info-center');
card.append(center);
center.append(new Element('match-time', '23:30'), new Element('match-vs', 'VS'));
const document = {
    querySelectorAll: () => [card],
    createElement: () => new Element(),
    createTextNode: text => new Element('', text),
};
const window = {};
const pending = [];
const fetch = () => new Promise(resolve => pending.push(resolve));
const response = (status, score) => ({ok: true, json: async () => [{id: 1, status, score}]});
"""
    scenarios = r"""
activeFixtures = {today: [{id: 1, status: 'Scheduled', score: null}]};
const match = activeFixtures.today[0];
if (scenario === 'missing_score') {
    applyLiveScoreToCard(card, {status: 'Live', score: null});
    assert.equal(center.querySelector('.match-time').textContent, '23:30');
    assert.equal(center.querySelectorAll('.live-indicator').length, 1);
    applyLiveScoreToCard(card, {status: 'Live', score: '0 - 0'});
    assert.equal(center.querySelector('.match-score').textContent, '0 - 0');
    assert.equal(center.querySelector('.match-time'), null);
    applyLiveScoreToCard(card, {status: 'Live', score: null});
    assert.equal(center.querySelector('.match-score').textContent, 'Score unavailable');
    assert.equal(center.querySelectorAll('.live-indicator').length, 1);
    applyLiveScoreToCard(card, {status: 'Finished', score: '2 - 1'});
    assert.equal(center.querySelector('.match-score').textContent, '2 - 1');
    assert.equal(center.querySelector('.live-indicator'), null);
} else {
    const older = pollLiveScores();
    const newer = pollLiveScores();
    if (scenario === 'out_of_order') {
        pending[1](response('Finished', '2 - 1'));
        await newer;
        pending[0](response('Live', '1 - 0'));
        await older;
        assert.equal(match.status, 'Finished');
        assert.equal(match.score, '2 - 1');
        assert.equal(center.querySelector('.match-score').textContent, '2 - 1');
        assert.equal(center.querySelector('.live-indicator'), null);
    } else {
        pending[1]({ok: false});
        await newer;
        pending[0](response('Live', '1 - 0'));
        await older;
        assert.equal(match.status, 'Live');
        assert.equal(match.score, '1 - 0');
        assert.equal(center.querySelector('.match-score').textContent, '1 - 0');
    }
}
"""
    result = subprocess.run(
        [node, "-e", harness + state + helpers +
         f"\nconst scenario = '{scenario}';\n(async () => {{\n" + scenarios +
         "\n})().catch(error => { console.error(error); process.exitCode = 1; });"],
        text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
