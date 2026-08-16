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




