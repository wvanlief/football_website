# 0004. Ingestion League Isolation Guardrails

- **Status**: Accepted
- **Date**: 2026-08-14
- **Context**: Ingestion & Data Sync Architecture

## Context & Problem Statement

During historical seeder and updater executions, 104 World Cup matches from June 2026 were erroneously copied into 21 domestic tournaments (e.g. *DFB Pokal*, *FA Cup*, *Coppa Italia*). 

This occurred because when `CompetitionSyncAdapter.sync_results()` and `sync_global_date_results()` processed API fixture payloads or candidate matches, they looked up team name/ID matches without validating whether the incoming fixture's `league_id` matched the target competition's `api_league_id`.

## Decision Drivers

- **Data Integrity**: Guarantee that domestic club tournaments can never ingest national team fixtures or World Cup matches.
- **Zero Silent Pollution**: Automatically reject any external API fixture item whose `league_id` does not match the target competition ID.
- **Backend Safety**: Ensure the global updater (`GET /fixtures?date=TODAY`) validates tournament alignment before updating PostgreSQL records.

## Considered Options

1. **Option A (Chosen)**: Add strict `league_id` validation guardrails in `CompetitionSyncAdapter.sync_results()` and `sync_global_date_results()`.
2. **Option B**: Rely solely on database cleanup scripts post-ingestion.

## Decision Outcome

**Option A**. Implemented strict league isolation guardrails:

1. **`CompetitionSyncAdapter.sync_results()`**: Extracts `incoming_league_id` from external API items. If `int(incoming_league_id) != int(comp.api_league_id)`, the adapter logs a guardrail skip message and skips the fixture item.
2. **`sync_global_date_results()`**: Verifies candidate fixture `api_league_id` matches incoming `league_id` before updating existing fixtures.
3. **Automated Test Coverage**: Added [tests/test_services/test_ingestion_guardrails.py](file:///c:/Users/WilliamVANLIEFFERING/.gemini/antigravity-ide/scratch/football_website/tests/test_services/test_ingestion_guardrails.py) to verify that cross-pollinated fixtures are rejected.

## Consequences

- **Positive**: Zero risk of cross-pollinated matches across competitions.
- **Positive**: Complete database league isolation across global daily syncs and per-league updaters.
