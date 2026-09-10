# Site map (findfootball.games)

What a visitor can open, what each surface is called, and which file serves it.

The header label for the table view is **not** always "Groups". It follows the selected competition's `format_engine` (stored as `findfootball-tournament-id` in `localStorage`). For domestic leagues — the usual case — the header says **Standings**.

## Header chrome (every HTML page)

Always visible:

| Nav label | URL | HTML |
| --------- | --- | ---- |
| Home | `/` | `frontend/index.html` |
| Hot List | `/recommended` | `frontend/recommended.html` |
| Calendar | `/calendar` | `frontend/calendar.html` |

Conditional (rewritten by `frontend/js/navigation.js`):

| What you see | When | URL | Same file |
| ------------ | ---- | --- | --------- |
| **Standings** | `league` or `league_phase_knockout` (Premier League, La Liga, UCL league phase, …) | `/group/standings` | `frontend/group.html` |
| **Groups** | `group_knockout` or `nations_league` (World Cup, Nations League) | `/group/A` | `frontend/group.html` |
| *(hidden)* | `cup` (FA Cup, Copa del Rey, …) | — | — |
| **Bracket** | shown except when `format_engine` is `league` | `/bracket` | `frontend/bracket.html` |

There is no second table page. Standings and Groups are one page (`group.html` + `group.js`) with two skins.

## Surfaces

### Home (`/`)

The Watchability Index feed. Not scoped to one competition.

- Hero spotlight (best matches today / next 7 days, or off-season empty cards)
- Results bar (finished matches)
- Three columns: Today, Tomorrow, This week
- Region waterfall (All / Europe / Americas → country → club) and the competitions drawer

Reads the pre-calculated feed (`fixtures_feed_cache.json` hydrated into the HTML, then `/api/fixtures` as fallback).

### Hot List (`/recommended`)

Ranked "must watch" / recommended matches. Drawer filters live here too.

Reads `/api/fixtures/recommended`.

### Standings (`/group/standings`, and `/group/{A–L}` for tournaments with groups)

The table view. For a league this is a single table. For World Cup / Nations League the same page shows Group A–L tabs plus a Best 3rd tab.

Reads `/api/group/{letter}?tournament_id=…` (and `/api/group/thirds` for Best 3rd, which currently does **not** pass `tournament_id`).

### Bracket (`/bracket`)

Knockout tree / Monte Carlo. Hidden in the header for a plain league.

Reads `/api/bracket?tournament_id=…`.

### Calendar (`/calendar`)

Month grid of fixtures for the selected competition.

Reads `/api/fixtures/calendar?tournament_id=…`.

### Team profile (`/team/{name}` and `/country/{name}`)

Not in the header. Opened from a team name on a match card. Both URLs serve `frontend/team.html`.

Reads `/api/countries/{name}`.

## What is not a public page

These exist in the repo or as URLs but are not separate products:

- `frontend/css/styles.css` — `@import` shim, not a view
- `/group/A` … `/group/L` — aliases of Standings when the competition has groups
- `/country/…` — alias of `/team/…`
- Admin JSON (`/api/admin/seed-all`, `/update`, …) — not linked in the UI
- Dead prototype scripts and backup stylesheets were removed in the architecture epic; they are not shadow routes

## Issue #28

The ticket title talks about a "Group page". For a league that surface is **Standings**. The page was not removed.

Whether the original bug ("shows every competition at once") is still true is a separate check: `group.js` now sends `tournament_id` from `localStorage`. Confirm on `/group/standings` with a league selected before treating #28 as live.
