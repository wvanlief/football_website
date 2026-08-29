# Spec 0004: Consolidate Fixture Ingestion Pipeline & Data Loss Safeguards

## Problem Statement

The data ingestion and seeding architecture suffers from high friction, logic duplication across six shallow modules, and severe vulnerability to production data wipes. Previously, seeding executed destructive SQL `DELETE` operations before fetching external API data; if external data providers failed or returned empty payloads due to rate limits or key suspensions, existing tournaments, teams, fixtures, and odds were permanently nuked—leaving only partial default data or a blank database.

Furthermore, team resolution, fixture upserts, and odds initialization were independently reimplemented in multiple files, causing circular imports and requiring every bug fix to be applied across multiple places.

## Solution

Consolidate the fixture ingestion and database seeding pipeline into a single, deep ingestion service with strict, non-destructive safety guarantees. Enforce a zero-deletion rule across all ingestion paths (strictly `INSERT` and `UPDATE`), establish a pre-flight guard that aborts any operation where fetched data drops below 50% of existing database fixtures, unify team resolution using the cross-provider mapping architecture, and inject shared upserters into format adapters to break circular module dependencies.

## User Stories

1. As a website visitor, I want competition fixture data to remain intact even during external API downtime or rate-limiting, so that I never see a blank database or missing tournament matches.
2. As a site operator, I want all database seeding and syncing operations to be strictly additive (`INSERT` / `UPDATE`), so that no routine data refresh can accidentally drop existing teams, fixtures, or odds history.
3. As a developer, I want a pre-flight safeguard that checks fetched fixture counts against existing database fixtures before committing changes, so that low-fixture responses are automatically blocked.
4. As an administrator, I want re-running a seed or update task to deduplicate odds and ELO history entries by date, so that duplicate time-series records are never inserted into the database.
5. As a developer, I want a single unified team resolution service that resolves external provider IDs via entity mapping tables, so that provider integrations remain consistent across all competitions.
6. As a developer, I want format adapters to receive shared upserters and resolvers via dependency injection, so that circular imports between adapters, updater services, and seeders are eliminated.
7. As a developer, I want obsolete re-export shims and hardcoded fake data scripts deleted from the codebase, so that database seeding logic is maintainable and relies on real API data providers.

## Implementation Decisions

### Modules & Architecture
- **Deep Ingestion Package**: Consolidate seeding, syncing, team resolution, and fixture upserting under a single deep service package.
- **Strictly Additive Pipeline**: Enforce an architectural invariant prohibiting any `DELETE` or ORM deletion operations within the ingestion and sync lifecycle.
- **Pre-Flight Safety Guard**: Intercept all seeding and syncing tasks before database mutation. If the count of fetched fixtures is less than 50% of the existing fixture count for a populated tournament, raise an exception and abort with zero database changes.
- **Unified Team Resolver**: Replace duplicate team lookup code with a single team resolution engine. Follow resolution precedence: `ExternalTeamMapping` lookup → normalized `Team.name` lookup → new `Team` creation with external mapping registration. Preserve `Team.api_id` as a denormalized field for static image badge URLs.
- **Shared Fixture Upserter**: Implement a single fixture upserter shared by both initial seeding and ongoing updates. Match existing fixtures by `api_id` or `(home_team_id, away_team_id)` within a ±12-hour UTC window.
- **Deduplicated Odds & ELO History**: Insert `FixtureOdds` and `EloHistory` records as time-series snapshots, skipping insertion if a snapshot for the same entity and date already exists.
- **Format Adapters Refactoring**: Refactor format adapters to accept the team resolver and fixture upserter via constructor injection, removing inline resolution logic and breaking circular module imports.
- **Cleanup of Obsolete Modules**: Remove shallow re-export modules and hardcoded fake data seeder scripts in favor of data-driven provider pipelines. Extract CLI execution logic into a dedicated CLI module.

### Invariant Principles
- Ingestion is strictly `INSERT` or `UPDATE`.
- Pre-flight checks pass unconditionally for initial tournament seeding (when existing fixture count is 0).

## Testing Decisions

### Seams
- **Primary Integration Seam**: Test at the high-level Ingestion Service boundary (`seed()` and `sync()`) and Format Adapter sync methods. Mock external provider HTTP endpoints while asserting end-to-end database state, pre-flight abort behaviors, and non-destructive updates.

### Guidelines
- Focus test assertions on observable behavior (fixture creation, odds deduplication, pre-flight aborts) rather than internal implementation steps.
- Verify that re-running seeding operations multiple times remains completely idempotent.
- Prior Art: Existing tests in `tests/test_services/test_multi_source_fallback.py` and `tests/test_services/test_updater.py`.

## Out of Scope

- Deleting or purging invalid database records (purging requires explicit administrative tool execution outside ingestion).
- Modifying real-time live score update windows or WebSocket connections.
- Altering the watchability index scoring formula or ELO proximity metrics.

## Further Notes

- Aligns with ADR `0001-no-automatic-seeding-on-startup.md` and ADR `0002-multi-source-data-ingestion-fallback.md`.
