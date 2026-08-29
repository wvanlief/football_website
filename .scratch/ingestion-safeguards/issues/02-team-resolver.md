# 02 — Unified Team Resolver & Mapping Engine

**What to build:** A centralized `TeamResolver` class in `backend/services/ingestion/team_resolver.py` that resolves API team identifiers to database `Team` entities. Uses `ExternalTeamMapping` first, falls back to normalized name matching, and auto-creates teams with mapping entries.

**Blocked by:** 01 — Preflight Safety Guard & Non-Destructive Invariant

**Status:** completed

- [x] Implement `TeamResolver` class in `backend/services/ingestion/team_resolver.py`
- [x] Integrate with `NameNormalizer` and `ExternalTeamMapping` CRUD utilities
- [x] Ensure resolution precedence: External mapping → Normalized name → Create new Team
- [x] Write unit tests verifying mapping creation and team resolution
