# 03 — Multi-Source Fallback Chain & Ingestor Failover

**What to build:** Refactor `seed_competition` and `IngestorService` to execute an automated multi-provider fallback chain (`Football-Data.org` -> `API-Football` -> `TheSportsDB`). If a provider returns an error payload (e.g. account suspended, rate limit, timeout), automatically failover to the next provider while guaranteeing zero fixture duplication.

**Blocked by:** 02 — Football-Data.org Client & Provider Adapter

**Status:** completed

- [x] Implement provider failover loop inside `seed_competition` that checks `res.get("errors")` and HTTP errors before attempting secondary/tertiary providers.
- [x] Ensure fixture matching checks existing DB entries by `(tournament_id, home_team_id, away_team_id, date_utc)` to update existing rows rather than creating duplicate fixtures across failover.
- [x] Add explicit warning logs when a primary provider is skipped due to API errors.
- [x] Add integration test in `tests/test_services/test_multi_source_fallback.py` verifying seamless failover when the primary provider returns an error payload.
