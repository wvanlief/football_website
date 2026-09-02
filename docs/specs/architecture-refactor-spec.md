## Problem Statement

Developers maintaining and extending findfootball.games face severe architectural drag, code duplication, and state fragility across both the frontend and backend layers:

1. **Frontend Industrial-Scale Copy-Paste**: Zero modular sharing exists across the 6 client pages. Over 1,440 lines of duplicate code (country flag tables, team badge resolvers, timezone sniffers, watchability tier mappings, match modal rendering) are copy-pasted across isolated scripts. This causes live divergence bugs (e.g., club badges failing to resolve on secondary pages) and performance penalties (5 redundant geo-IP lookups per user session). Additionally, dead legacy prototype artifacts and fabricated mock match fixtures pollute the repository and mislead off-season users.
2. **Backend Scatter & Lifecycle Fragility**: Match lifecycle management is fragmented: settling a result, updating watchability scores, and calculating team streaks are scattered across 10 paired call sites. Forgetting any paired step leads to silent state corruption (e.g. stale watchability scores or missing streak updates). Furthermore, redundant API client definitions bypass rate limiters, while circular imports and monolithic sync adapters mix data ingestion, fixture matching, and ELO calculations.

## Solution

A comprehensive codebase deepening and modularization pass:

1. **Frontend Modernization**:
   - Introduce a single, lightweight shared client utility module (`frontend/js/shared.js`) loaded across all views that encapsulates country flag mappings, canonical club and national badge URL resolution, session-cached timezone detection, unified watchability rating tiers, and the match details inspector modal.
   - Purge dead prototype files (`prototype-ui.js`), unreferenced stylesheets (`archived-styles.css`, `styles-backup-pre-overhaul.css`), and fabricated mock match fixtures (`HERO_FALLBACK_TODAY`, `HERO_FALLBACK_WEEK`), replacing fallbacks with clean off-season notices.
   - Clean up monolithic stylesheet specificity wars (87 `!important` declarations) and redundant prototype classes (`.proto-variant-c`).
2. **Backend Fixture Lifecycle & Provider Unification**:
   - Extract a cohesive Fixture Lifecycle domain service providing an atomic `finish_fixture` operation that guarantees synchronous execution of match settlement, watchability score updates, and team streak recalculation in a single transactional step.
   - Consolidate all third-party provider calls into a unified, rate-limited API-Football client, standardizing match status mappings across sync and ingestion routines.
   - Decouple format adapters and seeder pipelines into thin orchestrators delegating directly to dedicated ingestion, team resolution, and fixture upserting services, eliminating circular dependencies and mock-detection leaks.

## User Stories

1. As a football fan browsing the calendar or tournament bracket, I want club team crests and national flags to render accurately and consistently across all views, so that I can immediately identify matchups without broken images.
2. As a football fan visiting the site across multiple sub-pages in a single browsing session, I want my timezone to be resolved quickly and cached in session storage, so that match kickoff times display in my local time without redundant network lookups.
3. As a football fan visiting during the off-season or international breaks, I want to see a clear off-season schedule notice rather than fabricated placeholder matches with fake odds and ELO scores, so that I am not misled by invented fixture data.
4. As a football fan opening the match details modal from any page (Hot List, Groups, Recommended, Team Profile, Calendar), I want identical breakdown metrics (narrative reason, watchability drivers, form, and odds), so that my experience is cohesive regardless of navigation path.
5. As a football fan assessing match quality, I want watchability badge tiers (Must Watch, Recommended, Average) to reflect consistent percentile thresholds (score >= 72 for Must Watch, score >= 65 for Recommended) everywhere on the site, so that ratings are unambiguous.
6. As a developer adding a new tournament page, I want to import shared frontend utilities (badge resolution, toast notifications, rating formatters) from a single shared module, so that I do not copy-paste hundreds of lines of boilerplate.
7. As a developer updating watchability tier thresholds or badge logic, I want to modify the classification logic in one place, so that changes immediately propagate across all frontend pages without manual search-and-replace.
8. As a developer executing a match update or settlement cron job, I want an atomic lifecycle interface that records the final score, recalculates watchability metrics, and updates team streaks in one call, so that fixtures never end up in a partially-updated state.
9. As a developer inspecting API sync logs, I want all outgoing requests to API-Football to respect a centralized rate limiter, so that automated ingestion does not exceed quota limits or trigger rate-limit HTTP errors.
10. As a developer writing integration tests for match synchronization, I want sync adapters to accept injected mock providers rather than inspecting runtime mock types in production code, so that tests remain robust and production code remains pure.
11. As a developer maintaining database initialization and seeding, I want seeding routines to delegate directly to dedicated ingestion engines and team resolvers without circular imports, so that startup dependencies form a clean Directed Acyclic Graph (DAG).
12. As a developer maintaining simulation and ranking pipelines, I want tournament probabilities to be queried through a cached service interface rather than scattered raw disk file reads, so that file I/O overhead is minimized and tournament validation is centralized.
13. As an autonomous AI agent working in the codebase, I want unambiguous single-responsibility modules with minimal cognitive surface, so that feature additions and bugfixes can be delivered with high precision and zero unintended regressions.

## Implementation Decisions

- **Frontend Shared Utility Module**: Create a unified client module exposing canonical functions for country flag resolution, team crest URL generation with club fallback, session-cached timezone detection (using session storage with fallback to browser `Intl` API), watchability rating badge formatting, toast notifications, and the modal detail inspector.
- **Frontend Asset and Dead Code Cleanup**: Delete unreferenced prototype scripts and deprecated backup stylesheets. Remove vestigial prototype selector prefixes (`.proto-variant-c`) and audit stylesheet specificity.
- **Off-Season Fallback Handling**: Replace hardcoded in-memory dummy match arrays with structured empty-state notices.
- **Atomic Fixture Lifecycle Service**: Introduce a dedicated lifecycle function (`finish_fixture`) in the domain services layer. This function accepts a fixture, scores, and database session, executing in order: score settlement, watchability score updates, and team streak calculations within a single transaction boundary. Standalone calls to partial score updates are restricted.
- **Consolidated Provider Client**: Refactor external API calls into a single provider interface with rate-limiting parameters, standardizing match status short codes via an exported status mapping dictionary.
- **Decoupled Synchronization & Ingestion**: Deconstruct legacy seeder and god-class sync adapters into thin orchestration layers that delegate to Ingestion Engine, Team Resolver, and Fixture Upserter modules. Remove all runtime mock-detection inspection blocks.
- **Centralized Simulation Results Access**: Implement a cached accessor for simulation results and probabilities, eliminating direct path construction and file reads across query and scoring modules.

## Testing Decisions

- **Test Behavior Over Implementation**: Tests must verify observable domain behavior and contracts rather than internal class implementations or file paths.
- **Backend Testing**:
  - Test fixture finishing via the lifecycle service, asserting that settling a match results in correct score state, updated watchability record, and properly updated win/draw/loss streaks on both teams in a single transaction.
  - Test provider client, asserting that request rate-limiting parameters are consistently passed and status short codes are mapped cleanly to domain statuses.
  - Test ingestion pipelines, asserting that seeding and sync operations successfully upsert teams and fixtures without circular import errors.
- **Frontend Testing**:
  - Integration and unit assertions verifying that shared client methods accurately map team badge URLs (clubs and countries), format watchability ratings according to thresholds, and store resolved timezones in session storage without duplicate geo-IP calls.
- **Prior Art**:
  - `tests/test_services/test_updater.py` (live match sync verification)
  - `tests/test_services/test_settling.py` (match result settlement and streak tracking)
  - `tests/test_services/test_tournament.py` (tournament structure and knockout propagation)
  - `tests/test_services/test_ingestion_engine.py` (multi-source ingestion and upserting)

## Out of Scope

- Modifying UI visual themes or altering CSS design tokens beyond cleaning dead selectors and specificity overrides.
- Redesigning the underlying mathematical formula for intrinsic watchability scoring (weights and ELO formula remain as defined).
- Migrating the frontend vanilla JavaScript stack to modern reactive frameworks (React, Vue, etc.) — vanilla JS architecture is retained.

## Further Notes

- Prioritize high-leverage items first: Frontend shared module extraction and Backend Fixture Lifecycle module eliminate the majority of day-to-day maintenance friction and live bugs.
