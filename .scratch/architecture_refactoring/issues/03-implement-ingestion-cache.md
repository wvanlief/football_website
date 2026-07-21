# 03 — Implement Ingestion Cache and Normalization Module

**What to build:**
A local file-based `CacheAdapter` caching external API responses to `backend/data/cache/` (keyed by URL hash, parameters, and current date), plus a unified `NameNormalizer` supporting 3-letter ISO code mappings for national teams.

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Create `CacheAdapter` implementing file reading and writing of JSON results under `backend/data/cache/`.
- [ ] Centralize team name normalizations (mapping ClubElo and API-Football names) into a unified `NameNormalizer` module.
- [ ] Add static lookup mappings for World Cup national team names to their 3-letter ISO codes.
- [ ] Write unit tests verifying that cache hits load files offline and cache misses execute normal HTTP requests.
