# 05 — Deep Ingestion Engine (`seed()` & `sync()` Orchestration)

**What to build:** Create `backend/services/ingestion/` package exposing public `seed(db, config)` and `sync(db, tournament)` interfaces. Refactor `seeder.py` to delegate to the new ingestion package.

**Blocked by:** 01 — Preflight Safety Guard, 03 — Shared Fixture Upserter, 04 — Provider Adapter Extraction

**Status:** ready-for-agent

- [ ] Assemble `backend/services/ingestion/__init__.py`
- [ ] Implement `seed(db, config)` with pre-flight check, provider fallback chain, and fixture upserter
- [ ] Implement `sync(db, tournament)` for ongoing updates
- [ ] Refactor `seeder.py` to delegate to `ingestion.seed()`
- [ ] Verify existing seeder tests pass against the new deep engine
