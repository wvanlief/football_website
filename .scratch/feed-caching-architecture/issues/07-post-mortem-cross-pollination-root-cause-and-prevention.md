# 07 — Post-Mortem & Ingestion Guardrails (World Cup Cross-Pollination Prevention)

**What to build:** Audit all historical seeder, ingestor, and updater scripts (`backend/services/seeder.py`, `backend/services/updater.py`, `backend/ingestor.py`) to identify the exact code path that inserted World Cup fixtures into non-World Cup tournaments. Implement strict validation guardrails and database constraints to guarantee third-party API fixtures can never be cross-pollinated into incorrect tournaments in the future.

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Audit `seeder.py`, `ingestor.py`, and `updater.py` for league ID mapping leaks
- [ ] Add strict league/competition ID validation safeguards to `backend/services/format_adapters.py` and `updater.py`
- [ ] Ensure `sync_fixtures()` verifies `league_id` matches competition `api_id` before inserting fixtures into a tournament
- [ ] Document post-mortem root cause analysis and prevention guardrails in `docs/adr/0004-ingestion-league-isolation-guardrails.md`
