# Spec: Comprehensive Application Fixes, Badge Architecture & UI Overhaul

**Triage Label**: `ready-for-agent`  
**Status**: Approved & Published  
**Author**: Antigravity AI Assistant  

---

## Problem Statement

Users of **findfootball.games** currently experience several functional and visual defects:
1. Team badges are missing or display wrong logos (e.g. Sparta Praha shows Besiktas, Dinamo Zagreb shows Gent, Qarabag has no logo).
2. Team profile pages lack badges for teams that have logos elsewhere.
3. The "Hot List" recommendations display past August 2025 matches during the July 2026 off-season instead of upcoming 2026/27 season matchdays.
4. Standings and Bracket pages show resolved/completed 2025 seasons when 2026 season data is available.
5. Non-group competitions (e.g. FA Cup, Copa del Rey) incorrectly render Group Stage tables, and the Bracket page defaults to the World Cup tree for all selected competition filters.
6. European club cup standings (Champions League, Europa League, Conference League) include pre-season qualifying matches in point totals instead of displaying the 36-team flat League Phase table.
7. Home page response times suffer 1.5–2s latency due to un-cached DB enrichment queries per request.
8. The horizontal competition selector pill box is overflowing and unorganized.
9. The Calendar view lacks team logos and lacks Gameweek segmentation, reducing visual clarity.
10. Visual CSS artifacts (red dots) appear on the top-right of the search bar container.

---

## Solution

A unified backend and frontend overhaul:
1. **Local Static Badge Caching**: Store team badges locally under `backend/static/badges/{api_id}.png` during ingestion. Serve `logo_url` dynamically from API payloads to eliminate hardcoded JS dictionaries.
2. **Season & Date Anchoring**: Filter all active queries strictly for `season_name == "2026"`. Anchor dates to `today` (`datetime.now()`) with an off-season upcoming matchday notice banner.
3. **Format Engine UI Routing**: Route UI components based on `format_engine`:
   - `league`: 20-team domestic table, bracket tab disabled.
   - `league_phase_knockout`: 36-team flat table (Top 8 auto-R16, 9-24 playoff, 25-36 eliminated), filtered strictly to `League Phase` fixtures.
   - `cup`: Pure knockout bracket tree (R1 to Final), group standings tab disabled.
   - `group_knockout` / `nations_league`: Group tables + Knockout Bracket.
4. **In-Memory Payload Caching**: 60-second TTL response cache for `/api/fixtures` with immediate live score invalidation for sub-10ms page loads.
5. **UI & Calendar Redesign**: Categorized competition dropdown/pill bar, Gameweek/Weekly calendar split with team crests and a High-Watchability ($\ge 75\%$) toggle, and red dot CSS artifact removal.

---

## User Stories

1. As a football fan, I want to see correct team badges next to all clubs, so that I can instantly identify teams across the application.
2. As a user visiting a team profile page, I want to see the team's official badge, so that the team detail view looks complete and polished.
3. As a user browsing recommended hot matches in July, I want to see upcoming August 2026 kickoff matches with an off-season banner, so that I am not shown outdated 2025 fixtures.
4. As a fan checking league standings, I want to see current active 2026 season tables, so that I get up-to-date points and rankings.
5. As a user viewing domestic cups like the FA Cup, I want to see a knockout bracket tree instead of empty group tables, so that the UI matches the actual competition format.
6. As a European football follower, I want Champions League standings to display the 36-team flat League Phase table without pre-season qualifying noise, so that I can track the true tournament table.
7. As a site visitor, I want the home page to load instantly under 10ms, so that navigating between tabs feels fast and smooth.
8. As a user on mobile or desktop, I want competitions categorized into Top Leagues, European Cups, and Domestic Cups, so that I can easily switch between tournaments.
9. As a user checking the calendar, I want matches organized by Gameweek with team badges, so that I can scan upcoming schedules without visual clutter.
10. As a user looking at the search bar, I want a clean interface without stray red dot CSS artifacts, so that the search control looks visually polished.

---

## Implementation Decisions

- **Local Badge Ingestion**: During `fetch-teams`, download badge PNGs to `backend/static/badges/{api_id}.png`. Include `logo_url` in `TeamOut` and `FixtureOut` schemas.
- **Backend Response Caching**: In-memory dict cache with 60s TTL for `/api/fixtures` and `/api/fixtures/recommended` in `backend/services/tournament.py`.
- **Standings Stage Filtering**: Filter `Fixture.stage == "League Phase"` for European club cups in `backend/services/standings.py`.
- **Dynamic Navigation Router**: Update `frontend/js/navigation.js` to inspect `format_engine` and toggle nav links / page layouts dynamically.
- **Calendar Segmentation**: Update `frontend/js/calendar.js` to group fixtures by Gameweek/Week and render `home_team.logo_url` and `away_team.logo_url`.

---

## Testing Decisions

- **Behavioral Testing**: Test external API responses and DOM state without relying on internal helper implementation details.
- **Modules Tested**: `backend/routers/api_fixtures.py`, `backend/services/tournament.py`, `backend/services/standings.py`, `backend/main.py` static file server, and frontend JS scripts (`navigation.js`, `app.js`, `group.js`, `bracket.js`, `calendar.js`).
- **Prior Art**: Existing pytest backend suite under `tests/` and fixture/standings unit assertions.

---

## Out of Scope

- Modifying API-Football or ClubElo external API request quotas.
- Adding user authentication or personal user bookmark databases in this release.

---

## Further Notes

- Triage label: `ready-for-agent`
- All architectural decisions aligned with `CONTEXT.md`.
