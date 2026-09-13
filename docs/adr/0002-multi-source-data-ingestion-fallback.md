# 2. Multi-Source Data Ingestion & Provider Fallback Architecture

Date: 2026-08-07

## Status

Accepted (updated 2026-09-13: API-Football removed as a live source)

## Context

Our application findfootball.games relies on external football data APIs (schedules, match fixtures, team metadata, and live scores). Single-provider dependence on API-Football introduced a vulnerability where account suspensions, rate-limits, or API outages completely halted data ingestion.

We need a multi-source ingestion engine that can seamlessly combine **Football-Data.org**, **openfootball**, **TheSportsDB**, and **The Odds API** without causing duplicate database records or breaking database queries. API-Football is no longer a live HTTP source.

## Decision

1. **Priority Fallback Chain**: Match fixtures and schedules are ingested using a fallback order per competition: `Football-Data.org` -> `openfootball` -> `TheSportsDB`. If a primary provider returns an error, timeout, empty payload, or has no mapping for the competition, the engine automatically fails over to the next provider.
2. **External Entity Mapping Tables**: Decouple external provider IDs from core `Team` and `Competition` models using relational mapping tables (`ExternalTeamMapping` and `ExternalCompetitionMapping` storing `provider_name`, `external_id`, and `internal_id`). `Team.api_id` and `Competition.api_league_id` remain opaque catalog / badge-cache identifiers, not live API-Football lookup keys.
3. **Dedicated Odds Route**: Live and pre-match bookmaker odds remain decoupled from schedule sync and are routed strictly through `The Odds API`.
4. **Live Scoring Scope**: Daily results and live-score polling use Football-Data.org matches (`GET /v4/matches` with `dateFrom`/`dateTo`), not a per-league loop or a retired vendor client.

## Consequences

* **Pros**:
  * Eliminates single-point-of-failure vulnerability for fixture ingestion.
  * Extensible to future API providers (e.g. Sportmonks) without modifying the `teams` or `competitions` schema.
  * Zero duplication of fixture or team rows across provider failovers.
* **Cons**:
  * Requires explicit mappings (`ExternalTeamMapping`) created on first ingestion.
  * Competitions not covered by Football-Data.org free plan or published openfootball datasets stay on existing rows until TheSportsDB or another provider is used.
