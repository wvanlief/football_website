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

## Performance & Caching
- **API Payload Caching**: In-memory response caching (60s TTL) for heavy endpoints (`/api/fixtures`, `/api/fixtures/recommended`).
- **Live Invalidation**: Live score updates immediately invalidate cached payloads for real-time responsiveness under 5ms response times.

## UI Components & Navigation
- **Categorized Competition Selector**: Grouped switcher (Top 5 Leagues, European Cups, International & Domestic Cups) replacing flat horizontal text scrolling pills.
- **Calendar Segmentation**: Gameweek/Weekly date blocks with team crests (`logo_url`) and a High-Watchability filter toggle ($\ge 75\%$).




