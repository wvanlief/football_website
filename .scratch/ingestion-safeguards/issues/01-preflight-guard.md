# 01 — Preflight Safety Guard & Non-Destructive Invariant

**What to build:** Add pre-flight safety validation and runtime invariants to prevent data loss. Aborts any seeding or sync operation if fetched fixtures drop below 50% of existing DB fixture count for a tournament. Enforces runtime assertions prohibiting `DELETE` queries across ingestion operations.

**Blocked by:** None — can start immediately.

**Status:** completed

- [x] Implement `IngestionAborted` exception in `backend/services/ingestion/preflight.py`
- [x] Implement `PreflightGuard` class with `check_fixture_count(db, tournament_id, fetched_count)`
- [x] Ensure `check_fixture_count` passes when existing fixture count is 0 (initial seed)
- [x] Raise `IngestionAborted` when `fetched_count < 0.5 * existing_count` on populated tournaments
- [x] Add unit tests verifying pre-flight aborts on low fixture counts and passes on healthy counts
