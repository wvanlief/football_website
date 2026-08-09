# 03 — Shared Fixture Upserter & Time-Series Deduplication

**What to build:** Implement `FixtureUpserter` in `backend/services/ingestion/fixture_upserter.py` to match fixtures by `api_id` or home/away team ID + date window. Insert `FixtureOdds` and `EloHistory` records with date deduplication to prevent duplicate time-series snapshots.

**Blocked by:** 02 — Unified Team Resolver & Mapping Engine

**Status:** completed

- [x] Implement `FixtureUpserter` class
- [x] Match existing fixtures by `api_id` or `(home_team_id, away_team_id)` within ±12h date window
- [x] Add date deduplication check for initial odds seeding and ELO history creation
- [x] Trigger `settle_result()` for finished fixtures
- [x] Write unit tests for fixture upserting and odds deduplication
