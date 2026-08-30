# Deferred Decisions & Future Work

Decisions and improvements deferred during grilling sessions. Each item includes enough context to act on independently.

## Seeding & Data Population

### Skip squad fetching during re-seeding
- **Context**: Squad API calls cost 1 call per team. For 200+ club teams across 15 competitions, that's 2+ days of quota just for player data.
- **Decision**: Added `fetch_squads: bool = False` to `fetch_and_seed_teams`. `seed_all_default_competitions` uses `fetch_squads=False` to seed teams + fixtures across all 15 competitions in ~16 API calls total.
- **When**: Full squad backfill deferred until a player-facing feature is built.

### Single-competition admin seed endpoint (`/api/admin/seed-one`) (COMPLETED)
- **Context**: European cup draws happen at specific dates. The admin should be able to refresh a single competition's fixtures without re-seeding everything.
- **Decision**: Added `/api/admin/seed-one?league_id=X&confirm=true` endpoint and `seed-one` CLI command.
- **When**: Implemented in Issue #85.

### Expand seeder competition list to all 15 targets (COMPLETED)
- **Context**: `seed_all_default_competitions` expanded to cover Big 5 domestic leagues (PL, La Liga, Serie A, Bundesliga, Ligue 1), 3 European Cups (UCL, UEL, UECL), 5 Domestic Cups (FA Cup, Copa del Rey, Coppa Italia, DFB Pokal, Coupe de France), and 2 International tournaments (World Cup, Nations League).
