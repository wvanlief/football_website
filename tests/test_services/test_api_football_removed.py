"""Regression: production ingestion must not import the removed API-Football client."""
import ast
from pathlib import Path

import pytest

from backend.database import Competition, Team
from backend.services.rate_limiter import APIRateLimiter

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

PRODUCTION_MODULES = (
    BACKEND_ROOT / "services" / "updater.py",
    BACKEND_ROOT / "services" / "seeder.py",
    BACKEND_ROOT / "services" / "ingestion" / "engine.py",
)

FORBIDDEN_IMPORT_ROOTS = {
    "backend.services.providers.api_football",
    "api_football",
}


def _imported_names(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                names.add(module)
            for alias in node.names:
                names.add(alias.name)
                if module:
                    names.add(f"{module}.{alias.name}")
    return names


def test_api_football_http_client_module_is_removed():
    assert not (BACKEND_ROOT / "services" / "providers" / "api_football.py").exists()
    with pytest.raises(ModuleNotFoundError):
        __import__("backend.services.providers.api_football")


def test_updater_seeder_engine_do_not_import_api_football_client():
    """Fails if updater, seeder, or the ingestion engine import the removed client."""
    for path in PRODUCTION_MODULES:
        source = path.read_text(encoding="utf-8")
        imported = _imported_names(source)
        collision = imported & FORBIDDEN_IMPORT_ROOTS
        assert not collision, f"{path.relative_to(REPO_ROOT)} imports {sorted(collision)}"
        assert "call_football_api" not in imported
        assert "ApiFootballProvider" not in imported


def test_rate_limiter_has_no_api_football_quota():
    assert "api_football" not in APIRateLimiter.LIMITS


def test_runtime_python_has_no_api_sports_v3_host():
    hits = []
    for path in BACKEND_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "v3.football.api-sports.io" in text:
            hits.append(str(path.relative_to(REPO_ROOT)))
    assert hits == []


def test_team_and_competition_opaque_ids_remain():
    assert Team.api_id is not None
    assert Competition.api_league_id is not None
