# 02 — Consolidate Standings and Streaks Calculations

**What to build:**
A unified `StandingsService` (in `backend/services/standings.py`) that centralizes standings updates, streak computations, and guarantee math (currently scattered across `updater.py` and `tournament.py`).

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Move `recalculate_tournament_team_standings`, `recalculate_team_streaks`, `calculate_standings`, and `calculate_points_needed_to_guarantee_top_2` into the new `StandingsService`.
- [ ] Expose a single clean interface method `recalculate_standings(db, tournament_id)` to update and flush cached standings.
- [ ] Refactor and consolidate standings unit tests to run against the new service interface.
