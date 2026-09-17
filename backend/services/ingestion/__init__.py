from backend.services.ingestion.normalizer import (
    COUNTRY_ISO_MAP,
    TEAM_NAME_ALIASES,
    NameNormalizer,
    default_normalizer,
)
from backend.services.ingestion.preflight import (
    IngestionAborted,
    PreflightGuard,
    has_provider_fixture_id,
)
from backend.services.ingestion.team_resolver import TeamResolver
from backend.services.ingestion.fixture_upserter import FixtureUpserter, UpsertResult

__all__ = [
    "COUNTRY_ISO_MAP",
    "TEAM_NAME_ALIASES",
    "NameNormalizer",
    "default_normalizer",
    "IngestionAborted",
    "PreflightGuard",
    "has_provider_fixture_id",
    "TeamResolver",
    "FixtureUpserter",
    "UpsertResult",
    "IngestionEngine",
    "seed_competition",
]


def __getattr__(name: str):
    if name in ("IngestionEngine", "seed_competition"):
        from backend.services.ingestion.engine import IngestionEngine, seed_competition

        globals()["IngestionEngine"] = IngestionEngine
        globals()["seed_competition"] = seed_competition
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

