# 01 — External Mapping Database Models & Schema Migration

**What to build:** Add new database tables `external_team_mappings` and `external_competition_mappings` via a non-destructive, forward additive Alembic migration. Existing `teams`, `competitions`, and `fixtures` data must remain 100% untouched.

**Blocked by:** None — can start immediately.

**Status:** completed

- [x] Create SQLAlchemy models `ExternalTeamMapping` and `ExternalCompetitionMapping` with foreign keys to `teams.id` and `competitions.id`.
- [x] Add unique constraint on `(provider_name, external_id)` for indexed $O(1)$ lookups.
- [x] Generate non-destructive Alembic migration (`alembic revision --autogenerate`) that only creates new tables without altering or dropping existing columns/data.
- [x] Create CRUD helper utilities to lookup internal team/competition IDs by `(provider_name, external_id)` and auto-insert new mappings.
