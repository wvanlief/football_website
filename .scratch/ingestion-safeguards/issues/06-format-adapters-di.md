# 06 — Format Adapter Refactoring & Dependency Injection

**What to build:** Inject `TeamResolver` and `FixtureUpserter` into format adapters in `backend/services/format_adapters.py`. Remove duplicate resolution and fixture upsert code, breaking circular imports.

**Blocked by:** 05 — Deep Ingestion Engine (`seed()` & `sync()` Orchestration)

**Status:** ready-for-agent

- [ ] Update `BaseFormatAdapter` to accept dependencies
- [ ] Refactor `GroupKnockoutAdapter` and `LeagueFormatAdapter` to use injected upserter/resolver
- [ ] Update `get_format_adapter()` factory and `updater.py` caller
- [ ] Verify circular imports are eliminated and updater tests pass
