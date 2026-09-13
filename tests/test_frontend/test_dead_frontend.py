from pathlib import Path

DEAD_FILES = [
    "frontend/js/prototype-ui.js",
    "frontend/css/styles-backup-pre-overhaul.css",
    "frontend/css/archived-styles.css",
    "frontend/css/styles.css",
]

DEAD_URLS = [
    "/js/prototype-ui.js",
    "/css/styles-backup-pre-overhaul.css",
    "/css/archived-styles.css",
    "/css/styles.css",
]


def test_issue_42_dead_frontend_files_are_gone():
    for path in DEAD_FILES:
        assert not Path(path).exists(), path


def test_issue_42_dead_frontend_assets_are_not_served(client):
    for url in DEAD_URLS:
        response = client.get(url)
        assert response.status_code == 404, url
