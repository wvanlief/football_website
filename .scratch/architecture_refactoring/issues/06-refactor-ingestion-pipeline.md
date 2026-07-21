# 06 — Refactor Ingestion Pipeline to Ingestor Service

**What to build:**
A deep `IngestorService` (in `backend/services/ingestion.py`) that implements fetching and caching logic. The CLI script `ingestor.py` is refactored to call this service, and national team creation is updated to apply 3-letter ISO country codes.

**Blocked by:** 03 — Implement Ingestion Cache and Normalization Module

**Status:** ready-for-agent

- [ ] Wrap fetching, mapping, ELO-review generation, and seeding inside the new `IngestorService`.
- [ ] Incorporate `CacheAdapter` to cache external HTTP calls inside the service automatically.
- [ ] Use `NameNormalizer` to normalize team names and assign 3-letter ISO codes to all national teams.
- [ ] Update `ingestor.py` CLI script entry points to invoke `IngestorService` methods.
- [ ] Verify that running `fetch-teams` caches the API calls, and seeding national teams writes correct ISO codes (e.g. `MEX`, `USA`) into the `Team` table.
