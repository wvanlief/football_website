# Domain Glossary & Model Conventions (findfootball.games)

## Team Badges & Assets
- **`logo_url`**: Canonical URL string stored on the `Team` model pointing to the team's crest image (`/static/badges/{api_id}.png` for clubs, a Football-Data.org crest URL, or flagcdn for national teams). Never an API-Sports media CDN URL.
- **`badge_url`**: Resolved crest URL on `Team` for API payloads. Prefers stored `logo_url`, then `/static/badges/{api_id}.png` (`api_id` is an opaque local cache key), then flagcdn. Must not construct or emit `media.api-sports.io` URLs.
- **Badge Caching**: Club badges already on disk under static assets are served from `/static/badges/{api_id}.png`. New clubs can store a Football-Data.org crest on `logo_url`. National flags use flagcdn.

## Season & Date Filtering
- **Date Anchoring**: Fixture recommendations and hot lists must filter strictly against `datetime.now(target_tz)` for active/upcoming matches, anchored to current or upcoming matchdays.
- **Active Season Filtering**: Only query fixtures for active current seasons (`season_name == "2026"`) to prevent past resolved seasons (e.g. 2025) from polluting the hot list.

## Competition Format & UI Routing
- **`format_engine`**: Determines UI rendering layout and the header label for the table view (one HTML page: `group.html`):
  - `league`: Header says **Standings** (`/group/standings`). Single table. Bracket tab hidden.
  - `league_phase_knockout`: Header says **Standings** (`/group/standings`). Single 36-team table (Top 8 auto-R16, 9-24 playoff, 25-36 eliminated). Bracket enabled for knockout.
  - `cup`: Header hides the table link. Pure knockout on **Bracket**.
  - `group_knockout` / `nations_league`: Header says **Groups** (`/group/A`). Group tables + knockout on **Bracket**.
- Public surfaces and routes: `docs/site-map.md`.

## Performance & Pre-Calculated Feed Caching
- **Pre-Calculated Feed JSON**: `/api/fixtures` reads from a pre-built static JSON document (`fixtures_feed_cache.json`) built by a background worker. Zero live DB scans on HTTP requests.
- **Twice-Weekly Heavy Enrichment**: Heavy fixture enrichment (narrative scoring, ELO calculations, competitiveness) runs twice a week (Monday/Friday). Score updates read existing pre-computed fields.

## Multi-Source Fixture Ingestion
- **Priority Fallback Chain**: Season fixture ingestion tries `Football-Data.org` → `openfootball` → `Football-API` (for competitions outside Football-Data.org's map) → `TheSportsDB` per competition when a source fails, returns no fixtures, or lacks a mapping. The daily date overlay uses Football-API for competitions outside Football-Data.org coverage and Highlightly for active competitions missing from that date's Football-API response or when the response fails or is empty. Odds remain on The Odds API; live scores remain on Football-Data.org.
- **TheSportsDB coverage**: Last-resort season source for cups the earlier providers miss on the free plan or published datasets — notably **UEFA Europa League** and **UEFA Conference League**.
- **Opaque identifiers**: `Team.api_id` is a denormalized local badge-cache key (`/static/badges/{api_id}.png`), not a live API-Football team id. `Competition.api_league_id` is an opaque catalog identifier (UCL remains `2` for admin seed).
- **Stamp**: Overlay writes a provider fixture id onto `Fixture.api_id` (`fd_…` from Football-Data.org, `of_…` from openfootball, `tsdb_…` from TheSportsDB, `fa_…` from Football-API, or `hl_…` from Highlightly). That is the stamp. Unstamped means `api_id` is null or blank — a local seed/draw row not linked to a provider event. Unstamped is not “unplayed”, and leftover SELECT results are not a delete list. See `docs/agents/european-cup-stamping.md`.

## Global API Sync & Quota Management
- **Single-Call Daily Sync**: Yesterday and today’s scores update via one Football-Data.org matches query (`GET /v4/matches?dateFrom=YESTERDAY&dateTo=TODAY`). The daily fixture overlay also makes one Football-API `/fixtures?date=` call for each date, then queries Highlightly by date and active league name for competitions absent from that response or when it fails or is empty. Live polling does not use either overlay provider.
- **Live Score Polling**: 15-minute polling during active match windows uses Football-Data.org matches for in-window live or delayed scores. There is no API-Football `/fixtures?live=all` call.

## Watchability Gating & Regional Baselines
- **Regional ELO Baselines**: CONMEBOL clubs (~1600) and MLS (~1500) use regional baselines until custom in-house ELO engine is implemented.
- **Non-European Watchability Gating**: Regular non-European matches are suppressed from the global Hot List unless tagged as **Major Derbies**, late-stage knockouts, or filtered via the **Americas** region tab.

## Dynamic Watchability Ranking & Tiers
- **Intrinsic Watchability Score**: The underlying numerical score (0-100) computed from ELO, betting odds, form, and narrative. Treated as a ranking metric rather than a primary user-facing label.
- **Global Percentile**: Percentile rank representing intrinsic match quality relative to the full season distribution (p80 = Top 20% / ~65.4, p95 = Top 5% / ~71.7, p99 = Top 1% / ~80.1).
- **Contextual View Rank**: Relative position computed within a specific display horizon (e.g., `#1 Match Today` in the daily bucket; `Top 3 this Week` in weekly views).
- **Recommendation Tiers**:
  - `Must Watch`: Global Top 5% (score $\ge 72$) or Top 2 matches in active 8-day window.
  - `Recommended`: Global Top 20% (score $\ge 65$) or Top 5 matches in active 8-day window.
  - `Average`: Standard fixtures outside top percentiles.
  - `Recommended Feed Fallback`: If fewer than 7 matches qualify in the active upcoming window, fallback to the Top 7 highest-rated upcoming matches.
  - `_Avoid_`: Fixed score cutoffs (e.g. `>= 75.0`), hardcoded static gem thresholds.
