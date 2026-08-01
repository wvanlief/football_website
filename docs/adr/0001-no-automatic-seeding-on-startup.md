# 1. No Automatic Seeding on Startup

## Context
On July 31, 2026, an unconditional startup seeding routine was deployed to production. On container initialization, the application executed `seed_all_default_competitions()`, attempting to fetch fixtures and squads across all supported leagues from external APIs. Because container restarts occurred automatically on Railway, the app rapidly exhausted the free tier quota (100 requests/day).

Furthermore, database seeding is a heavyweight operation that should run once to populate persistence, whereas production deployments must remain fast, stateless, and idempotent.

## Decision
We removed all automatic database seeding from the application startup lifecycle (`main.py` -> `lifespan`). Application startup now exclusively invokes `init_db()` (SQLAlchemy schema initialization).

All seeding operations are strictly manual and triggered via the protected `/api/admin/seed-all?confirm=true` endpoint or administrative CLI scripts.

## Consequences
- Deployments and container restarts consume **0 external API calls**.
- Database schema initialization remains idempotent.
- Seeding data into new environments requires an explicit administrative action.
