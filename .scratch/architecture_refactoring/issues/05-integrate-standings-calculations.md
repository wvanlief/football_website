# 05 — Integrate Standings Calculations into Ingestor and Live Updater

**What to build:**
Integrate the consolidated `StandingsService` into both the seeding scripts (`ingestor.py`) and live scores updater (`updater.py`), replacing scattered custom math with calls to the unified service.

**Blocked by:** 02 — Consolidate Standings and Streaks Calculations

**Status:** ready-for-agent

- [ ] Update the live scorer in `updater.py` to trigger standings cache updates using `StandingsService.recalculate_standings`.
- [ ] Add calls to `recalculate_standings` at the end of the `seed_competition` function in `ingestor.py` before committing.
- [ ] Update CLI command handlers to use the consolidated service for standings updates.
- [ ] Verify that running a seed or live score update updates all cached standings fields in the database correctly.
