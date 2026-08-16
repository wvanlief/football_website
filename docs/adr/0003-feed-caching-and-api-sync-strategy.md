# 3. Inline Data Hydration, Global 1-Call API Sync & Watchability Gating Strategy

## Context
When loading the main feed (`/api/fixtures`), the backend previously queried all fixtures across 33 active tournaments from PostgreSQL and calculated watchability scores and narrative reasons dynamically in Python on every HTTP request. With thousands of fixtures, this took 25–45 seconds, causing HTTP 504 timeouts and leaving browser skeleton loading cards stuck on screen.

Simultaneously, the API updater iterated through all 33 competitions sequentially calling `fixtures?league=X&season=Y`, hitting API-Football's minute rate limit safeguard (`1 call/min`) after the first competition and failing all subsequent league updates.

Furthermore, non-European clubs (MLS, CONMEBOL) lacked `ClubElo` ratings and defaulted to `1500 ELO`, causing 1500-vs-1500 matches to receive 100% competitiveness scores and artificially outrank European top matches on the global Hot List.

## Decision
1. **Inline Data Hydration (0 Extra Network Calls)**:
   - Instead of fetching `/api/fixtures` via an asynchronous secondary network request after the HTML page loads, the pre-computed JSON dataset is embedded directly inside `<script id="initial-fixtures-data" type="application/json">` within `index.html`.
   - On page load, client JavaScript parses the inline JSON instantly (<10ms), converts match dates into the viewer's local timezone (`Intl.DateTimeFormat`), and populates the cards without skeleton loading screens.
   - All UI filters (Region chips `All` / `Europe` / `Americas`, Country search, Watchability filters) operate directly on the in-memory dataset in **0ms** without sending any server requests.
   - Heavy fixture enrichment (narrative reasons, ELO calculations, competitiveness) runs **twice a week** (Mondays and Fridays).

2. **Global Single-Call API Sync & Railway Cron Schedules**:
   - Daily results sync replaces 33 sequential league calls with 1 global date call (`GET /fixtures?date=TODAY`).
   - **`admin-update-cron` Railway Schedule**: Set to run once daily at **4:00 AM UTC** (`0 4 * * *`) instead of 8:00 AM UTC, ensuring yesterday's final match scores are sealed before morning peak traffic.
   - **`backend-updater-cron` Railway Schedule**: Set to run **every 15 minutes** (`*/15 * * * *`) instead of every 5 minutes during active windows, consuming ~40 calls max on peak Saturdays (60%+ daily quota safety buffer).

3. **Regional Baseline & Watchability Gating**:
   - Apply regional baseline ELOs for CONMEBOL (~1600) and MLS (~1500).
   - Suppress non-European regular season matches from the global Hot List feed unless tagged as **Major Derbies**, late-stage knockouts, or filtered under the **Americas** region tab.

## Consequences
- Homepage load time drops from 35,000ms to **<10ms** with zero extra network calls and zero skeleton loader freezes.
- Filtering by region (`Europe`, `Americas`) or country search executes in **0ms** in browser memory with zero server load.
- Daily API-Football request consumption drops from 33+ calls down to 2–5 calls per day for daily schedule sync.
- Peak Saturday live score polling stays strictly under the 100 calls/day free tier quota.
- Hot List rankings remain clean, prioritizing top European blockbusters while surfacing non-European matches only for major derbies and critical knockouts.
