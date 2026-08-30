# Domain Glossary & Model Conventions (findfootball.games)

## Team Badges & Assets
- **`logo_url`**: Canonical URL string stored on the `Team` model pointing to the team's crest image (`/static/badges/{api_id}.png` for clubs, or flagcdn URL for national teams).
- **Badge Caching**: All team badges are downloaded and stored locally on disk under static assets during ingestion to eliminate third-party CDN latency and quota usage.

## Season & Date Filtering
- **Date Anchoring**: Fixture recommendations and hot lists must filter strictly against `datetime.now(target_tz)` for active/upcoming matches, anchored to current or upcoming matchdays.
- **Active Season Filtering**: Only query fixtures for active current seasons (`season_name == "2026"`) to prevent past resolved seasons (e.g. 2025) from polluting the hot list.

## Competition Format & UI Routing
- **`format_engine`**: Determines UI rendering layout:
  - `league`: Single 20-team table, bracket tab disabled.
  - `league_phase_knockout`: Single 36-team flat table (Top 8 auto-R16, 9-24 playoff, 25-36 eliminated), bracket enabled for knockout stage. Filtered strictly to `League Phase` fixtures.
  - `cup`: Pure knockout bracket tree (R1 through Final), group standings tab disabled.
  - `group_knockout` / `nations_league`: Group tables + Knockout Bracket Tree.

## Performance & Pre-Calculated Feed Caching
- **Pre-Calculated Feed JSON**: `/api/fixtures` reads from a pre-built static JSON document (`fixtures_feed_cache.json`) built by a background worker. Zero live DB scans on HTTP requests.
- **Twice-Weekly Heavy Enrichment**: Heavy fixture enrichment (narrative scoring, ELO calculations, competitiveness) runs twice a week (Monday/Friday). Score updates read existing pre-computed fields.

## Global API Sync & Quota Management
- **Single-Call Daily Sync**: Schedules and results update via single global date calls (`GET /fixtures?date=TODAY`). Individual per-league looping is disabled.
- **Live Score Polling**: 15-minute polling intervals during active match windows using `GET /fixtures?live=all`.

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




