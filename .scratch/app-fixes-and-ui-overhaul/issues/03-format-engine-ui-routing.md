# 03 — Format Engine UI Routing & Standings Adaptability

**What to build:** Dynamic navigation routing and standings layout adaptation based on `Competition.format_engine`. Domestic leagues render 20-team single tables (bracket tab disabled). European club cups render 36-team flat tables (filtered strictly to `League Phase` fixtures). Knockout cups (FA Cup, Copa del Rey) route to pure knockout bracket trees instead of empty group tables.

**Blocked by:** 02 — Active 2026 Season & Date Anchor Filtering

**Status:** closed

- [x] Navigation bar dynamically inspects `format_engine` and updates active links.
- [x] Domestic leagues (`league`) render single 20-team standings and disable the bracket tab.
- [x] European club cups (`league_phase_knockout`) render 36-team flat tables with qualification zone styling (Top 8, 9-24, 25-36) and filter out pre-season qualifying games.
- [x] Knockout cups (`cup`) route directly to bracket trees and hide group standings tabs.

