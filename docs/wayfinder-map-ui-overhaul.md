# Wayfinder Map: UI Navigation & Dashboard Overhaul

**GitHub Map Issue**: [#19](https://github.com/wvanlief/football_website/issues/19)

## Destination

Overhaul the findfootball.games multi-competition navigation and match dashboard to eliminate all horizontal side-scrolling pills and flag carousels, replacing them with a clean, responsive layout:
1. **Hamburger Competitions Drawer**: Top-left `☰` button opening an off-canvas drawer for precise competition filtering (*Premier League*, *La Liga*, *Serie A*, *Bundesliga*, *Champions League*, *Europa League*, *World Cup*).
2. **Top Inline Geographic Cascading Bar**: Single-row horizontal waterfall chips for continent ➔ country ➔ team drill-down (*Region: Europe ➔ Country: England ➔ Team: Man City*).
3. **3-Column Match Feed (`Today`, `Tomorrow`, `This Week`)**: Anchored to watchability ratings as the default cross-competition home feed.
4. **Docked Right Side Inspector Panel**: Replacing modal popups by displaying live watchability drivers, attack rating xG, ELO differential, win probabilities, and live odds movement when any match card is clicked.

## Notes

- **Domain**: Frontend Architecture & UI Components (`frontend/index.html`, `frontend/js/navigation.js`, `frontend/js/app.js`, `frontend/css/styles.css`).
- **Relevant Skills**: `/prototype`, `/codebase-design`.
- **Standing Preferences**: Zero horizontal side-scrolling tech, preserve Watchability Index as core home feed default, clean responsive dark aesthetics.

## Decisions so far

- [Validated Layout Prototype](file:///c:/Users/user/PycharmProjects/football_website/frontend/js/prototype-ui.js) — Settled and validated interactive prototype for Hamburger Drawer + Inline Geographic Waterfall + 3 Match Columns + Docked Right Side Inspector Panel.
- [Stylesheet Backup](file:///c:/Users/user/PycharmProjects/football_website/frontend/css/styles-backup-pre-overhaul.css) — Created safety backup of pre-overhaul styles (`frontend/css/styles-backup-pre-overhaul.css`).
- **Sleek Rectangular Cards (~65px Height)** — 3-column internal grid with single-line `ellipsis` overflow truncation, 22px crests, 0.15/0.25 watermark opacity, and hidden card footers.

## Open Frontier Tickets

- [x] **[Ticket 0: Stylesheet & Layout Safety Backup](https://github.com/wvanlief/football_website/issues/20)** (`#20`)
- [x] **[Ticket 1: Off-Canvas Hamburger Competitions Drawer Component](https://github.com/wvanlief/football_website/issues/21)** (`#21`)
- [x] **[Ticket 2: Top Inline Geographic Waterfall Filter Bar](https://github.com/wvanlief/football_website/issues/22)** (`#22`)
- [x] **[Ticket 3: Docked Right Side Inspector Panel & Event Delegation](https://github.com/wvanlief/football_website/issues/23)** (`#23`)
- [ ] **[Ticket 4: Main Layout Integration & Desktop Clean-up](https://github.com/wvanlief/football_website/issues/24)** (`#24`)
- [ ] **[Ticket 5: Mobile View Adaptation & Bottom Tab Bar](https://github.com/wvanlief/football_website/issues/25)** (`#25`)

## Not yet specified

- Gameweek / Matchday pagination integration within the top waterfall bar.

## Out of scope

- Backend API schema changes (all required fixture & competition data already served by `/api/fixtures` and `/api/competitions`).
