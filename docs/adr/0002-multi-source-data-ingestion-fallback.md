# 2. Multi-Source Data Ingestion & Provider Fallback Architecture

Date: 2026-08-07

## Status

Accepted

## Context

Our application findfootball.games relies on external football data APIs (schedules, match fixtures, team metadata, and live scores). Single-provider dependence on API-Football introduced a vulnerability where account suspensions, rate-limits, or API outages complete halted data ingestion.

We need a multi-source ingestion engine that can seamlessly combine **Football-Data.org**, **TheSportsDB**, **The Odds API**, and **API-Football** without causing duplicate database records or breaking database queries.

## Decision

1. **Priority Fallback Chain**: Match fixtures and schedules are ingested using a fallback order per competition: `Football-Data.org` -> `API-Football` -> `TheSportsDB`. If a primary provider returns an error, timeout, or rate-limit response, the engine automatically fails over to the next provider.
2. **External Entity Mapping Tables**: Decouple external provider IDs from core `Team` and `Competition` models using relational mapping tables (`ExternalTeamMapping` and `ExternalCompetitionMapping` storing `provider_name`, `external_id`, and `internal_id`).
3. **Dedicated Odds Route**: Live and pre-match bookmaker odds remain decoupled from schedule sync and are routed strictly through `The Odds API`.
4. **Live Scoring Scope**: Live score polling remains unchanged for now using the current lightweight single-source update engine.

## Consequences

* **Pros**:
  * Eliminates single-point-of-failure vulnerability for fixture ingestion.
  * Extensible to future API providers (e.g. Sportmonks) without modifying the `teams` or `competitions` schema.
  * Zero duplication of fixture or team rows across provider failovers.
* **Cons**:
  * Requires explicit mappings (`ExternalTeamMapping`) created on first ingestion.
