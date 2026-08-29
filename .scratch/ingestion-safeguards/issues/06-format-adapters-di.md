# 06 — Format Adapter Refactoring & Dependency Injection

**What to build:** Inject `TeamResolver` and `FixtureUpserter` into format adapters in `backend/services/format_adapters.py`. Remove duplicate resolution and fixture upsert code, breaking circular imports.

**Blocked by:** 05 — Deep Ingestion Engine (`seed()` & `sync()` Orchestration)

**Status:** completed

- [x] Refactor `BaseFormatAdapter` to accept optional `team_resolver` and `fixture_upserter`
- [x] Refactor `GroupKnockoutAdapter` and `LeagueFormatAdapter` to use injected upserter and resolver
- [x] Update `get_format_adapter()` factory and callers in `updater.py` to pass dependencies
- [x] Eliminate circular `import backend.services.updater as updater_module` imports
- [x] Verify existing updater tests pass against the refactored adapters
