# 02 — Active 2026 Season & Date Anchor Filtering

**What to build:** End-to-end season and date filtering anchor. Filter all active competition queries strictly for `season_name == "2026"`. Evaluate match recommendations relative to `today` (`datetime.now()`). When browsing during off-season dates (e.g. July 2026), select the upcoming matchday window (e.g. Gameweek 1 starting Aug 15, 2026) and render an off-season matchday notice banner instead of falling back to 2025 dates.

**Blocked by:** 01 — Local Badge Asset Caching & Dynamic Logo Delivery

**Status:** ready-for-agent

- [ ] All database queries for active tournaments filter strictly for `season_name == "2026"`.
- [ ] Hot list and recommended match endpoints anchor dynamically to current `today` dates.
- [ ] Off-season banner renders cleanly when no matches occur in the current calendar week.
- [ ] No past 2025 resolved fixtures pollute current 2026 recommendation queues.
