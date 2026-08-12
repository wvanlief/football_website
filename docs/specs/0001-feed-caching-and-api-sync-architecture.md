# Spec: Inline Data Hydration, Global API Sync & Watchability Gating Architecture

## Problem Statement
The user experiences two major issues:
1. **Homepage Loading Failures (Empty Skeleton Cards)**: When visiting `findfootball.games`, `/api/fixtures` executes heavy Python loops over 12,000+ database rows calculating ELOs, watchability scores, and narrative explanations on every HTTP request. This causes HTTP 504 Gateway Timeouts, leaving the website stuck showing empty skeleton loading placeholders.
2. **API Rate Limiting & Unsynced European Results**: The API updater executes 33 sequential requests (one per league) per run, triggering the `api_football` rate limiter (`1 call/min`) after the first competition and failing all subsequent league updates. Furthermore, non-European clubs default to 1500 ELO, causing equal-ELO matches (100% competitiveness) to artificially outrank European top leagues.

## Solution
1. **Inline Data Hydration (0 Extra HTTP Network Calls)**: Instead of executing a separate client-side API fetch to `/api/fixtures` after the page loads, the pre-computed JSON dataset is embedded directly inside an inline `<script id="initial-fixtures-data" type="application/json">` tag within the HTML response. The browser parses the embedded JSON instantly, converts match times to the user's local timezone, and renders cards in **<10ms** with zero skeleton loading screens.
2. **Twice-Weekly Heavy Enrichment & Daily Score Sync**: Heavy fixture enrichment (calculating narrative reasons, ELO adjustments, and watchability scores) runs **twice a week** (Mondays and Fridays after weekend and European mid-week matchdays). Daily updates only update match scores and statuses, keeping background tasks extremely fast.
3. **Global Single-Call API Sync**: Replace per-league looping with single global date calls (`GET /fixtures?date=TODAY`). Set Railway cron schedules to **4:00 AM UTC daily** (`admin-update-cron`) and **every 15 minutes** during active windows (`backend-updater-cron`).
4. **Watchability Gating & Regional Baselines**: Apply CONMEBOL (~1600) and MLS (~1500) regional baselines. Non-European matches are gated from the default global Hot List unless flagged as **Major Derbies** (e.g. *Boca vs River*, *Flamengo vs Fluminense*), **late-stage knockouts** (Quarter-finals, Semi-finals, Finals), or explicitly filtered under the **Americas** region tab.
5. **Database Deduplication**: Provide a migration script to merge duplicate `"2026"` and `"2026/27"` tournaments (starting with Belgian Pro League) and remove duplicate fixture rows.

## User Stories
1. As a website visitor, I want the homepage feed to render immediately (<10ms) upon loading without making secondary API calls or showing skeleton loading boxes.
2. As a website visitor, I want match times automatically converted to my local timezone (Paris, New York, Tokyo, etc.) and placed in accurate "Today", "Tomorrow", and "This Week" columns.
3. As a website visitor, I want region chips (`All`, `Europe >`, `Americas >`) and country search filters to update the feed in **0ms** in-memory without page reloads or server requests.
4. As a website visitor, I want to see accurate finished scores for European leagues (Belgian Pro League, Eredivisie, Premier League, La Liga, Serie A), so that I am up to date on recent results.
5. As a football fan, I want the global Hot List to highlight top European blockbusters, critical global derbies (*Boca vs River*), and late knockout matches, while regular non-European league matches are suppressed unless I select the **Americas** tab.
6. As a system administrator, I want API consumption to remain strictly below 100 requests/day, so that the service runs safely within free API tiers without rate-limit blocks.
7. As a system administrator, I want Railway cron jobs configured to optimal schedules (Daily sync at 04:00 UTC, live polling every 15 mins), so that system updates run efficiently without wasted execution.

## Implementation Decisions
- **Inline Data Hydration Engine**: FastAPI HTML template endpoint injects pre-built JSON payload directly into `index.html` via `<script id="initial-fixtures-data">`.
- **Client-Side Hydration & Timezone Converter**: `frontend/js/app.js` reads embedded JSON on `DOMContentLoaded`, resolves viewer timezone via browser `Intl.DateTimeFormat`, sorts matches into local "Today", "Tomorrow", and "This Week" buckets, and renders UI cards.
- **In-Memory Filtering**: Region filtering (`All` | `Europe` | `Americas`), country search, and watchability filters execute on the in-memory `activeFixtures` dataset in 0ms without server requests.
- **Twice-Weekly Heavy Enrichment Schedule**: Full enrichment (narratives, ELOs, watchability scores) executes on Mondays and Fridays. Daily updates perform lightweight score/status updates.
- **Global API Sync Pipeline**: `update_results_and_odds()` queries `GET /fixtures?date=TODAY` instead of iterating per league ID.
- **Regional ELO Baselines & Hot List Gating**: Non-European matches use regional baselines (CONMEBOL ~1600, MLS ~1500) and are suppressed from the default global Hot List feed unless:
  1. Tagged as a registered **Major Derby** (`is_major_derby == True`), OR
  2. Classified as a **late-stage critical knockout** (`stage in ('Quarter-final', 'Semi-final', 'Final')`), OR
  3. The user explicitly selects the **Americas** region filter tab.
- **Database Deduplication Script**: Python script `backend/scripts/cleanup_belgian_league.py` deduplicates Belgian Pro League tournaments (`"2026"` vs `"2026/27"`) and duplicate fixtures.
- **Railway Cron Schedules**:
  - `admin-update-cron`: `0 4 * * *` (Once daily at 04:00 UTC).
  - `backend-updater-cron`: `*/15 * * * *` (Every 15 minutes during active match windows).

## Testing Decisions
- **Seams for Testing**:
  - **Inline Hydration Seam**: Test `/` endpoint returning `index.html` containing valid embedded JSON in `<script id="initial-fixtures-data">`.
  - **Timezone Resolution Seam**: Test client JavaScript correctly categorizing UTC timestamps into local "Today" and "Tomorrow" relative to target timezones (`America/New_York`, `Europe/Paris`, `Asia/Tokyo`).
  - **In-Memory Filter Seam**: Test filtering `activeFixtures` by region (`Europe`, `Americas`) producing correct match subsets in 0ms.
  - **Global Sync Seam**: Test `update_results_and_odds()` making a single API call for today's date and updating DB fixture statuses.
  - **Watchability Gating Seam**: Test that unranked 1500 vs 1500 matches without derby/knockout flags are excluded from global Hot List recommendations unless filtered by Americas tab.
  - **Deduplication Script Seam**: Test `cleanup_belgian_league.py` on local database to confirm duplicate fixtures are removed and legacy tournament status set to `"Completed"`.

## Out of Scope
- Custom in-house ELO calculation engine for non-European clubs (logged in `TODO.md` under Prio 1 for post-World Cup phase).
- Third-party bookmaker odds comparison matrix.
- Real-time WebSocket match events streaming.

## Further Notes
- Railway Cron UI settings need to be updated manually in the Railway dashboard:
  - Update `admin-update-cron` schedule to `0 4 * * *` (Daily at 4 AM UTC).
  - Update `backend-updater-cron` schedule to `*/15 * * * *` (Every 15 minutes).
