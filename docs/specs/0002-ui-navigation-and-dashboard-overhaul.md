# Spec: UI Navigation & Dashboard Overhaul

**Triage Label**: `ready-for-agent`  
**Status**: Approved & Published  
**Author**: Antigravity AI Assistant  
**Wayfinder Map**: [docs/wayfinder-map-ui-overhaul.md](file:///c:/Users/user/PycharmProjects/football_website/docs/wayfinder-map-ui-overhaul.md)

---

## Problem Statement

Users of **findfootball.games** currently experience cognitive overload and visual clutter when browsing fixtures across dozens of active domestic leagues, European cups, and international tournaments:
1. Flat horizontal text scrolling pills and flag carousels become crowded, unorganized, and clunky on both desktop and mobile screens as fixture data expands.
2. Filtering down to a single league (like the Premier League) defeats the primary value proposition of the website, which is to serve as a curated **Watchability Index** highlighting top matches across all competitions.
3. Clicking a match card opens a full-screen modal popup that interrupts the user's browsing flow and hides the surrounding schedule.
4. Desktop displays fail to utilize horizontal screen space effectively, leaving empty margins or squishing multi-column layouts.

---

## Solution

A multi-competition UI navigation and dashboard redesign that eliminates all horizontal side-scrolling tech:
1. **Hamburger Competitions Off-Canvas Drawer**: A top-left `☰` button that opens a smooth sliding off-canvas drawer on the far left for precise competition filtering (*Premier League*, *La Liga*, *Serie A*, *Bundesliga*, *UEFA Champions League*, *UEFA Europa League*, *FIFA World Cup*).
2. **Top Inline Geographic Cascading Filter Bar**: A single-row horizontal waterfall chip system for continent ➔ country ➔ team drill-down (*Region: Europe ➔ Country: England ➔ Team: Man City*).
3. **3-Column Watchability Feed (`Today`, `Tomorrow`, `This Week`)**: Anchored to watchability ratings as the default cross-competition home view across all 3 columns.
4. **Docked Right Side Inspector Panel**: Docked panel on the right side of `index.html` that replaces modal popups by intercepting card clicks and displaying real-time matchup crests, xG attack drivers, ELO differentials, win probabilities (Home/Draw/Away), and live bookmaker odds.
5. **Stylesheet Safety Backup**: Created `frontend/css/styles-backup-pre-overhaul.css` to protect existing styling baseline.

---

## User Stories

1. As a football fan looking for the best games, I want the home page to default to a cross-competition Watchability Feed across 3 columns, so that I can immediately spot high-rating matches regardless of league.
2. As a user who wants to inspect a match, I want to click any fixture card in `Today`, `Tomorrow`, or `This Week` and see its deep watchability drivers, win probabilities, and odds appear in a docked side panel, so that I don't have to deal with disruptive modal popups.
3. As a user exploring specific leagues, I want to click a top-left hamburger menu (`☰`), so that an off-canvas drawer slides open for quick, precise competition filtering without cluttering the main page.
4. As a user searching for matches by country or team, I want an inline horizontal waterfall filter bar at the top (*Continent ➔ Country ➔ Team*), so that I can drill down geographically without taking up extra vertical space.
5. As a desktop user, I want the 3 match columns and side inspector panel to expand flush across the screen, so that screen real estate is maximized without left padding whitespace.
6. As a developer, I want a safety backup of the pre-overhaul CSS, so that styling regressions can be safely referenced or restored if needed.

---

## Implementation Decisions

- **Layout Grid Structure**: `index.html` main view utilizes a 2-column grid layout (`1fr 300px`) containing `#inspector-feed-area` (left) and `#proto-inspector` (right side panel). Inside `#inspector-feed-area`, `.triptych-container` renders 3 equal match columns (`repeat(3, minmax(0, 1fr))`).
- **Sleek Rectangular Compact Cards (~65px Height)**: Match cards use a 3-column internal grid (`1fr auto 1fr`) with single-line `ellipsis` overflow truncation on team names. Vertical padding is reduced to `0.45rem` and multi-line reason boxes are hidden inside cards (as drivers are fully detailed in the Side Inspector Panel), producing a sleek, non-squared horizontal rectangle card that never cuts off text on the right.
- **Off-Canvas Drawer Component**: Injected into `document.body` with class `.offcanvas-sidebar`. Toggled via `#hamburger-menu-btn` in header and `#trigger-drawer-chip` in top waterfall bar.
- **Card Click Event Delegation**: Event capture listener bound to `.match-card` clicks, extracting team names (`.team-box.home .team-name`, `.team-box.away .team-name`), team crests (`.team-flag`), stage tags, ELO ratings, and watchability scores to update `#proto-inspector` dynamically.
- **Geographic Waterfall Component**: Injected into `#inspector-feed-area` containing 3 cascading chip containers (`#inline-waterfall-group`, `#geo-sub-level`, `#geo-team-level`) that expand sideways on user selection.
- **Stylesheet Preservation**: Backup file created at `frontend/css/styles-backup-pre-overhaul.css`.

---

## Testing Decisions

- **Seam 1: Frontend User Interaction & DOM Seam (`frontend/index.html`, `frontend/js/navigation.js`, `frontend/js/app.js`, `frontend/css/styles.css`)**:
  - Verify that clicking `#hamburger-menu-btn` toggles `.offcanvas-sidebar.open`.
  - Verify that selecting a drawer competition or geographic waterfall chip filters visible `.match-card` elements correctly.
  - Verify that clicking any `.match-card` updates `#proto-inspector` with home/away team names, logos, probabilities, and odds without triggering `#match-modal`.
- **Seam 2: Responsive Viewport Seam**:
  - Verify layout integrity on desktop (> 1200px), tablet (768px - 1199px), and mobile (< 768px).

---

## Out of Scope

- Backend API schema changes (all required fixture & competition data already served by `/api/fixtures` and `/api/competitions`).
- Mobile bottom navigation tab bar adaptation (deferred to Ticket 5 in a dedicated session).

---

## Further Notes

- Prototype code in `frontend/js/prototype-ui.js` validated all interactive behaviors and will be refactored into production `navigation.js` and `app.js` during ticket execution.
