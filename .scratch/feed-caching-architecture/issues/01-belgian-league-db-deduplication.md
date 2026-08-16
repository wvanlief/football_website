# 01 — Belgian Pro League & Duplicate Tournament Database Cleanup

**What to build:** Test and execute database deduplication for Belgian Pro League tournaments (`"2026"` vs `"2026/27"`). Consolidate finished match scores into `"2026/27"`, remove duplicate fixture records, set legacy `"2026"` to `"Completed"`, and establish the pattern for deduplicating other European leagues.

**Blocked by:** None — can start immediately

**Status:** completed

- [x] Execute `python backend/scripts/cleanup_belgian_league.py` dry-run and verify duplicate count
- [x] Create global deduplication script `backend/scripts/cleanup_duplicate_tournaments.py`
- [x] Confirm script logic merges finished scores and sets legacy `"2026"` tournaments to `"Completed"`
- [x] Verify idempotent execution across local and remote database targets
