# 01 — Belgian Pro League & Duplicate Tournament Database Cleanup

**What to build:** Test and execute database deduplication for Belgian Pro League tournaments (`"2026"` vs `"2026/27"`). Consolidate finished match scores into `"2026/27"`, remove duplicate fixture records, set legacy `"2026"` to `"Completed"`, and establish the pattern for deduplicating other European leagues.

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Execute `python backend/scripts/cleanup_belgian_league.py` dry-run and verify duplicate count
- [ ] Execute `python backend/scripts/cleanup_belgian_league.py --execute` to apply cleanup to DB
- [ ] Confirm `fixtures` table contains single non-duplicate rows for Belgian Pro League matches
- [ ] Verify legacy `"2026"` Belgian Pro League tournament status is set to `"Completed"`
