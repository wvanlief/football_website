"""Only settlement assigns a Finished status literal.

Live score updates are the other score writer. They assign the provider status
variable inside ``_write_live_score`` and do not hard-code Finished.
"""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
ALLOWED_LITERAL = {
    Path("services/settling.py"),
}


def test_finished_status_literal_is_only_settlement():
    offenders = []
    for path in BACKEND.rglob("*.py"):
        relative = path.relative_to(BACKEND)
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if '.status = "Finished"' in line or ".status = 'Finished'" in line:
                if relative not in ALLOWED_LITERAL:
                    offenders.append(f"{relative}:{lineno}: {stripped}")
    assert offenders == []


def test_live_score_writer_is_the_other_score_writer():
    source = (BACKEND / "services" / "updater.py").read_text(encoding="utf-8")
    start = source.index("def _write_live_score")
    end = source.index("def _competitions_in_window")
    body = source[start:end]
    assert "finish_fixture(" not in body
    assert "fixture.home_score" in body
    assert "only score writer besides settlement" in body
