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
FORBIDDEN_CLIENT_SUBSTRING = "backend.services.providers.api_football"


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


def _production_python_files() -> list[Path]:
    return [
        path
        for path in BACKEND_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def _assert_module_has_no_api_football_client(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    imported = _imported_names(source)
    collision = imported & FORBIDDEN_IMPORT_ROOTS
    rel = path.relative_to(REPO_ROOT)
    assert not collision, f"{rel} imports {sorted(collision)}"
    assert "call_football_api" not in imported
    assert "ApiFootballProvider" not in imported
    assert FORBIDDEN_CLIENT_SUBSTRING not in source, (
        f"{rel} still references {FORBIDDEN_CLIENT_SUBSTRING}"
    )


def test_api_football_http_client_module_is_removed():
    assert not (BACKEND_ROOT / "services" / "providers" / "api_football.py").exists()
    with pytest.raises(ModuleNotFoundError):
        __import__("backend.services.providers.api_football")


def test_updater_seeder_engine_do_not_import_api_football_client():
    """Fails if updater, seeder, or the ingestion engine import the removed client."""
    for path in PRODUCTION_MODULES:
        assert path.is_file(), f"missing production module {path.relative_to(REPO_ROOT)}"
        _assert_module_has_no_api_football_client(path)
    for path in _production_python_files():
        _assert_module_has_no_api_football_client(path)


def test_rate_limiter_has_no_api_football_quota():
    assert "api_football" not in APIRateLimiter.LIMITS


def test_runtime_python_has_no_api_sports_v3_host():
    hits = []
    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        if "v3.football.api-sports.io" in text:
            hits.append(str(path.relative_to(REPO_ROOT)))
    assert hits == []


def test_team_and_competition_opaque_ids_remain():
    assert "api_id" in Team.__table__.columns
    assert "api_league_id" in Competition.__table__.columns
    assert Team.__table__.columns["api_id"].name == "api_id"
    assert Competition.__table__.columns["api_league_id"].name == "api_league_id"
