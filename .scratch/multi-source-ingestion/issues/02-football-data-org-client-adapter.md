# 02 — Football-Data.org Client & Provider Adapter

**What to build:** Build an API client and provider adapter for `Football-Data.org` (v4 API) that fetches competition matches and team rosters, normalizes payloads into standard domain entities, and records external IDs into mapping tables.

**Blocked by:** 01 — External Mapping Database Models & Schema Migration

**Status:** completed

- [x] Implement `FootballDataClient` adapter using `X-Auth-Token` header authentication.
- [x] Map Football-Data.org competition codes (`PL`, `PD`, `SA`, `BL1`, `FL1`, `CL`, `WC`) to internal competition entities.
- [x] Map fixture stages, matchday numbers, and game statuses (`SCHEDULED`, `FINISHED`, `IN_PLAY`, `PAUSED`) to findingfootball.games domain formats.
- [x] Resolve teams using `external_team_mappings`, falling back to `NameNormalizer` and auto-registering new mappings on initial fetch.
