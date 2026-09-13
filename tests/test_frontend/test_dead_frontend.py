from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DEAD_FILES = [
    "frontend/js/prototype-ui.js",
    "frontend/css/styles-backup-pre-overhaul.css",
    "frontend/css/archived-styles.css",
    "frontend/css/styles.css",
]


def _url_for(rel_path: str) -> str:
    return "/" + rel_path.removeprefix("frontend/")


def test_issue_42_dead_frontend_files_are_gone():
    for path in DEAD_FILES:
        assert not (REPO_ROOT / path).exists(), path


def test_issue_42_dead_frontend_assets_are_not_served(client):
    for path in DEAD_FILES:
        response = client.get(_url_for(path))
        assert response.status_code == 404, path


def test_issue_42_html_does_not_reference_dead_frontend():
    names = [Path(path).name for path in DEAD_FILES]
    for html in (REPO_ROOT / "frontend").glob("*.html"):
        text = html.read_text(encoding="utf-8")
        for name in names:
            assert name not in text, f"{html.name} references {name}"
