# 02 — Global Single-Call API Sync Engine & Rate Limit Upgrade

**What to build:** Refactor `backend/services/updater.py` to replace the 33-league sequential loop with single global date queries (`GET /fixtures?date=TODAY`), update `backend/services/rate_limiter.py` quotas (10 calls/min, 100/day for `api_football`), and gate 15-minute live score polling by active match windows in PostgreSQL.

**Blocked by:** None — can start immediately

**Status:** completed

- [x] Update `rate_limiter.py` to support `10 calls/min` and `100 calls/day` for `api_football`
- [x] Refactor `update_results_and_odds()` to query global `GET /fixtures?date=TODAY` in 1 API call
- [x] Ensure live score updater (`update_live_scores()`) queries `GET /fixtures?live=all` only during active match windows
- [x] Verify daily API consumption drops from 33+ calls down to 2–5 calls per day
