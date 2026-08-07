# Spec 0003: Multi-Source Data Ingestion & Provider Fallback Architecture

## Problem Statement

Single-provider dependence on API-Football introduced a vulnerability where account suspensions, daily quota exhaustion, or external API downtime completely halted fixture seeding and match result updates across the findfootball.games application. When API-Football is unavailable, users see missing matches, empty competition schedules, or outdated fixtures, degrading the overall experience of the match watchability engine.

## Solution

Build a resilient multi-source data ingestion engine combining **Football-Data.org**, **TheSportsDB**, **The Odds API**, and **API-Football**. Match schedules and fixture scores will be ingested through an automated priority fallback chain (`Football-Data.org` -> `API-Football` -> `TheSportsDB`). Decouple external API identifiers using dedicated mapping tables (`ExternalTeamMapping` and `ExternalCompetitionMapping`) to ensure zero duplicate match or team entries during provider failover.

## User Stories

1. As a football fan, I want competition schedules and fixtures to be populated even when a primary data provider goes offline, so that I can always see upcoming matches.
2. As a website visitor, I want match results and scores to update reliably without interruption during API key suspensions, so that match watchability index scores remain accurate.
3. As a developer, I want external API provider IDs decoupled from core team and competition models, so that new sports data APIs can be added dynamically without database schema migrations.
4. As an administrator, I want automatic fallback between data providers during competition seeding, so that data ingestion never fails silenly or returns 0 matches due to an unhandled API error response.
5. As a site operator, I want bookmaker odds sync to remain routed through a dedicated odds API while fixture ingestion fails over independently, so that watchability odds calculations are preserved.

## Implementation Decisions

### Modules & Services
- **Multi-Source Ingestor Service**: Abstract ingestion service that handles provider priority order (`Football-Data.org` -> `API-Football` -> `TheSportsDB`).
- **Provider Adapters**: Individual API client adapters responsible for normalizing provider-specific raw JSON payloads into standard domain format.
- **Entity Resolution Engine**: Service responsible for resolving external IDs to internal database entities via mapping tables, using `NameNormalizer` as a first-time auto-link fallback.

### Database Schema Changes
- **`external_team_mappings` Table**:
  - `id`: Integer Primary Key
  - `team_id`: Integer Foreign Key to `teams.id`
  - `provider_name`: String (e.g., `"football_data"`, `"api_football"`, `"thesportsdb"`)
  - `external_id`: String (Indexed)
  - Unique Constraint: `(provider_name, external_id)`
- **`external_competition_mappings` Table**:
  - `id`: Integer Primary Key
  - `competition_id`: Integer Foreign Key to `competitions.id`
  - `provider_name`: String
  - `external_id`: String (Indexed)
  - Unique Constraint: `(provider_name, external_id)`

### API Provider Priority Chain
- **Primary**: Football-Data.org (v4 API)
- **Secondary**: API-Football (v3 API)
- **Tertiary**: TheSportsDB (v1/v2 API)
- **Odds Provider**: The Odds API (decoupled)

## Testing Decisions

### Seams
- **Primary Integration Seam**: Test at the high-level `IngestorService` and `seed_competition` / `update_results_and_odds` function boundaries. By mocking raw HTTP responses from providers, test that provider fallback occurs smoothly and that fixture and team records are correctly mapped and deduplicated.

### Guidelines
- Test external observable behavior (e.g. database entity population, fallback execution, and API error surfacing) rather than internal helper methods.
- Prior Art: Existing tests in `tests/test_services/test_updater.py` and `tests/test_services/test_ingestion_cache.py`.

## Out of Scope

- Live score circuit-breaker real-time polling (remains on lightweight single-source engine for now).
- Automatic fetching of team logo badges from secondary providers (existing cached local badges are retained).
- Paid tier API key automated billing or quota management.

## Further Notes

- Documented in ADR `0002-multi-source-data-ingestion-fallback.md` and domain glossary `CONTEXT.md`.
