# 04 — Provider Adapter Extraction (`ApiFootballProvider`)

**What to build:** Extract `call_football_api` and `ApiFootballProvider` into `backend/services/providers/api_football.py`, conforming to the provider interface.

**Blocked by:** 02 — Unified Team Resolver & Mapping Engine

**Status:** ready-for-agent

- [ ] Create `backend/services/providers/api_football.py`
- [ ] Move `call_football_api` logic into provider module
- [ ] Implement `fetch_fixtures()` returning normalized fixture payloads
- [ ] Write unit tests for `ApiFootballProvider` API payload parsing
