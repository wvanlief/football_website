# Spec 0005: Replace API-Football with Football-Data.org and OpenFootball

## Problem Statement

The API-Football account used by findfootball.games is suspended, so every live HTTP call to that provider fails. Daily results sync, live-score polling, competition seeding, team/squad fetch, and the UEFA Champions League overlay all still depend on it. Champions League 2026/27 League Phase fixtures are missing or stuck on a static draw bootstrap because the live overlay explicitly disables Football-Data.org and requires an API-Football key. Club badges also hotlink the API-Sports CDN, so crests break or leak a dead vendor. Visitors cannot trust upcoming UCL matchdays (league phase starts 8–10 September 2026) or other live schedules.

## Solution

Remove API-Football as a live data source. Ingest fixtures, results, and teams from Football-Data.org as the primary provider (Champions League is on its free plan). When Football-Data.org returns nothing, fall back to the public-domain openfootball/football.json community datasets for the domestic leagues that repo actually publishes. Keep The Odds API and ClubElo unchanged. Re-ingest UEFA Champions League 2026/27 from Football-Data.org onto the existing draw-seeded tournament, matching fixtures by teams and kickoff window, then retire leftover placeholder rows. Serve badges from local cached assets or Football-Data.org crests, never from the API-Sports CDN.

This updates the provider chain in ADR 0002: Football-Data.org becomes primary, openfootball replaces API-Football as secondary, and TheSportsDB remains deferred.

## User Stories

1. As a football fan, I want the 2026/27 UEFA Champions League League Phase fixtures on the site, so that I can see the real matchdays starting 8–10 September 2026.
2. As a football fan, I want UCL pairings and kickoff times to match the official schedule, so that I do not plan around invented or stale draw placeholders.
3. As a football fan, I want finished UCL and top-league scores to appear after matches end, so that watchability and standings stay current without API-Football.
4. As a football fan, I want live or delayed in-play scores for competitions Football-Data.org covers, so that I can follow matches on matchday without a suspended vendor.
5. As a football fan, I want Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Primeira Liga, Championship, and Brasileirão schedules to keep updating, so that the Hot List is not empty outside UCL.
6. As a football fan, I want team crests to render from local or Football-Data.org assets, so that cards and tables are not blank when API-Sports media URLs die.
7. As a football fan, I want World Cup 2026 fixtures to remain available from the static tournament dataset, so that international coverage does not vanish when API-Football is removed.
8. As a football fan, I want Europa League and Conference League to keep showing their static league-phase draw until another provider is added, so that those competitions do not disappear during the cutover.
9. As a website visitor, I want `/api/fixtures` and the pre-calculated feed cache to include re-ingested UCL matches, so that the homepage and calendar show the same data.
10. As a website visitor, I want the UCL group page (`format_engine` `league_phase_knockout`) to list League Phase fixtures only, so that the 36-team table and matrix stay consistent.
11. As a site operator, I want zero outbound requests to API-Football or the API-Sports media CDN, so that a suspended account cannot block ingestion or badge loading.
12. As a site operator, I want daily results sync to use a single Football-Data.org date-range matches query, so that all covered competitions update without a per-league loop.
13. As a site operator, I want live-score polling during active match windows to use Football-Data.org matches, so that the 15-minute cron no longer calls API-Football.
14. As a site operator, I want competition seeding to succeed when only a Football-Data.org key is present, so that operators are not forced to keep a dead API-Football secret.
15. As a site operator, I want the European-cup live overlay to run whenever a Football-Data.org key is configured, so that UCL is not gated on `FOOTBALL_API_KEY`.
16. As a site operator, I want leftover scheduled draw placeholders (no provider fixture id) retired after a successful live overlay, so that duplicate or fake UCL rows do not remain.
17. As a site operator, I want existing mapped fixtures to be updated in place rather than deleted, so that watchability scores, odds history, and standings are not wiped (spec 0004 additive invariant).
18. As a site operator, I want a pre-flight guard to still abort if a provider returns far fewer fixtures than already stored, so that an empty Football-Data.org outage cannot shrink a populated tournament.
19. As a site operator, I want bookmaker odds to keep syncing through The Odds API independently of fixture providers, so that watchability odds are preserved.
20. As a site operator, I want ClubElo rating sync to keep running independently of fixture providers, so that ELO-based watchability does not depend on API-Football.
21. As a site operator, I want environment variable names for Football-Data.org unified, so that the seeder, updater, and format adapters all read the same key.
22. As a site operator, I want the rate limiter to stop reserving quota for API-Football, so that daily limits reflect providers we actually call.
23. As a developer, I want the ingestion engine fallback chain to be Football-Data.org then openfootball, so that a primary outage still seeds covered domestic leagues.
24. As a developer, I want an openfootball provider that normalizes community JSON into the same domain fixture payload as Football-Data.org, so that the fixture upserter stays provider-agnostic.
25. As a developer, I want openfootball used only for competitions that repo publishes (2026/27 top domestic leagues and 2026 Brasileirão), so that we do not invent a Champions League path the community dataset does not have.
26. As a developer, I want team resolution to keep using external mapping tables and NameNormalizer, so that Football-Data.org and openfootball names do not create duplicate clubs.
27. As a developer, I want Football-Data.org fixture ids stored with a provider prefix on `Fixture.api_id`, so that ids do not collide with legacy World Cup or draw-seeded rows.
28. As a developer, I want `Competition.api_league_id` to remain an opaque catalog identifier (UCL stays `2` for admin seed), so that CLI seeding by league id does not require a schema migration.
29. As a developer, I want `Team.api_id` retained as a denormalized badge-cache key where local files already exist, so that `/static/badges/{id}.png` keeps working without meaning “API-Football team id”.
30. As a developer, I want `Team.badge_url` to never construct an API-Sports media URL, so that server-rendered crest links stay on local or Football-Data.org crests.
31. As a developer, I want the frontend crest helper to stop rewriting local badge paths into API-Sports CDN URLs, so that the browser does not depend on a suspended vendor.
32. As a developer, I want format adapters to stop calling API-Football for results and live scores, so that per-tournament fallback sync cannot resurrect the dead client.
33. As a developer, I want World Cup seeding to skip the API-Football fixture fetch and use the static dataset, so that international seeding does not fail the whole seed run.
34. As a developer, I want team seeding for covered competitions to use Football-Data.org teams (including crest URLs), so that new clubs get badges without squad endpoints.
35. As a developer, I want documentation, ADRs, and the domain glossary to describe global date sync via Football-Data.org matches rather than API-Football `/fixtures?date=` and `/fixtures?live=all`, so that future agents do not reintroduce the suspended client.
36. As a developer, I want tests that mock Football-Data.org and openfootball HTTP (not API-Football) at the seed and updater boundaries, so that CI proves the new chain without hitting the network.
37. As a developer, I want tests to fail if production runtime still imports or calls an API-Football client, so that the cutover cannot silently keep a dead dependency.
38. As an administrator, I want to re-seed a single European cup by existing catalog league id and get a live Football-Data.org overlay for UCL, so that local and production refresh stay one command.
39. As an administrator, I want to run the daily updater locally against SQLite after UCL re-ingest, so that scores and the feed cache rebuild without deploying to Railway first.
40. As an administrator, I want ingestion logs to name Football-Data.org or openfootball rather than API-Football, so that failed syncs are diagnosable.
41. As an administrator, I want uncovered competitions (domestic cups, Super Lig, MLS, Libertadores, and similar) left as existing database rows, so that the cutover does not delete historical fixtures we cannot currently refresh.
42. As a QA tester, I want UCL Matchday 1 through 8 counts to match a 36-team League Phase (144 fixtures) after overlay, so that missing-game reports can be checked empirically.
43. As a QA tester, I want Liverpool vs Atlético Madrid on 9 September 2026 to remain the Matchday 1 Anfield fixture after overlay, so that a known official pairing is a regression check.
44. As a QA tester, I want badge requests in the browser not to hit `media.api-sports.io`, so that visual verification of the vendor cut is possible.

## Implementation Decisions

### Provider chain (updates ADR 0002)
- Primary live fixture and results provider: Football-Data.org v4 (free-plan competitions, including UEFA Champions League).
- Secondary fallback: openfootball/football.json public GitHub JSON, daily community updates, no API key. Only for datasets that exist for the active season.
- Tertiary TheSportsDB: not implemented in this spec (existing tech-debt ticket remains).
- Odds stay on The Odds API. Club ratings stay on ClubElo.
- No new paid API (Sportmonks, unofficial ESPN/SofaScore) in this spec.

### Remove API-Football as a live dependency
- Delete or fully stop importing the API-Football provider client and any helper that performs HTTP to API-Sports football v3.
- Daily global results sync must query Football-Data.org matches for yesterday and today (dateFrom/dateTo), not a global API-Football fixtures-by-date call.
- Live-score polling during active windows must query Football-Data.org matches, not API-Football live-all.
- Format adapters must not accept or invoke an API-Football client for results or live scores.
- World Cup seed must not attempt an API-Football fixture pull; static World Cup data is the source.
- European-cup live overlay must not disable Football-Data.org and must not require an API-Football key.
- Rate limiter must drop the API-Football quota entry.
- Unify Football-Data.org credentials on a single environment variable (`FOOTBALL_DATA_ORG_KEY`), accepting current aliases only as read fallbacks during cutover.

### Ingestion engine
- Fallback order: Football-Data.org, then openfootball when the primary returns no normalized fixtures for a mapped competition.
- Keep spec 0004 guarantees: strictly additive upserts, pre-flight fixture-count guard, NameNormalizer plus external mapping tables, fixture match by provider id or home/away within ±12 hours UTC.
- Openfootball payloads must use `provider_name` `openfootball` and resolve teams through the existing team resolver.
- Football-Data.org match ids continue to be stored as prefixed fixture `api_id` values (`fd_{id}`) to avoid identifier clashes.

### Champions League re-ingest
- UEFA Champions League remains `format_engine` `league_phase_knockout`, season `2026/27`, catalog `api_league_id` 2.
- Bootstrap from the existing European draw JSON is allowed; live overlay from Football-Data.org is required for dates and pairings.
- After overlay, retire scheduled fixtures in that tournament that still have a null provider fixture id.
- Then rescore fixtures, recalculate standings, and rebuild the pre-calculated fixtures feed cache.
- Europa League and Conference League are not on Football-Data.org free coverage and have no 2026/27 openfootball JSON; leave them on the static draw for this spec.

### Openfootball coverage map
- 2026/27: England 1 and 2, Germany 1, Spain 1, Italy 1, France 1, Netherlands 1, Portugal 1.
- 2026 calendar: Brazil 1.
- Do not add a Champions League openfootball path until upstream publishes that season.

### Badges and identifiers
- `logo_url` remains the canonical stored crest.
- `Team.badge_url` and the frontend crest helper must not emit or rewrite to `media.api-sports.io`.
- Prefer existing local `/static/badges/` files; otherwise store Football-Data.org team crest URLs on `logo_url` during team seed.
- Do not migrate away `Team.api_id` or `Competition.api_league_id`; they stay as opaque identifiers / local badge keys, not live API-Football lookup keys.

### Competitions without a live provider
- Leave existing rows in place. Do not DELETE tournaments to “clean up” uncovered cups and Americas competitions.
- Future coverage is TheSportsDB or a paid Football-Data.org plan, not this spec.

### Documentation
- Update ADR 0002’s fallback chain and live-scoring note.
- Update the domain glossary’s global sync and live polling bullets so they no longer name API-Football endpoints.

## Testing Decisions

### What makes a good test
- Assert observable outcomes: database fixtures created/updated, placeholder rows retired, statuses and scores written, feed-facing data present, and no HTTP to API-Football.
- Mock provider HTTP at the fetch boundary; do not hit the network in unit tests.
- Do not assert internal helper call counts except a single regression that production updater/seeder/engine modules no longer import an API-Football client.

### Seams
Prefer existing high seams; do not add new ones.

1. **Primary ingestion and sync seam** (existing): `seed_competition` / ingestion engine and `update_results_and_odds` / `update_live_scores`. Mock Football-Data.org and openfootball responses. Assert tournament fixtures, fallback when primary is empty, pre-flight abort on sparse payloads, and that results/live paths succeed with no API-Football client.
2. **European-cup overlay seam** (existing): `seed_single_competition` / European-cup live overlay for catalog league id 2. Assert overlay is not gated on an API-Football key, uses Football-Data.org, matches or inserts League Phase rows, and retires scheduled placeholders with null provider ids. Keep the known pairing Liverpool vs Atlético Madrid on 2026-09-09 as a fixture-level assertion after overlay when that payload is supplied.
3. **Badge resolution seam** (existing model/frontend helper): `Team.badge_url` and the shared crest helper must not produce API-Sports media URLs when `logo_url` is local or a Football-Data.org crest.

Do not unit-test provider JSON parsing in isolation if the primary seam already covers normalized upserts.

### Prior art
- `tests/test_services/test_ingestion_engine.py` (Football-Data.org primary seed, pre-flight abort)
- `tests/test_services/test_multi_source_fallback.py` (provider failover; rewrite away from API-Football)
- `tests/test_services/test_updater.py` (global date and live sync)
- `tests/test_services/test_seed_single_competition.py` (UCL overlay and placeholder retire)
- `tests/test_services/test_european_draw_invariants.py` (draw JSON invariants; keep)
- `tests/test_services/test_api_football_provider.py` (replace or delete; must not keep the live client as required production code)

### Local verification (not CI)
- With `FOOTBALL_DATA_ORG_KEY`, seed UCL, run the updater, confirm ~144 League Phase fixtures, rebuild feed cache, and spot-check the UCL UI. Do not require a Railway deploy to prove the fix.

## Out of Scope

- Implementing TheSportsDB (tracked separately).
- Paying for Football-Data.org Standard, livescores add-on, or any new vendor.
- Squad and player ingestion previously planned against API-Football.
- Dropping `Team.api_id` / `Competition.api_league_id` columns or rewriting the ELO name-review JSON key names.
- Re-ingesting Europa League or Conference League from a live API (no free Football-Data.org / openfootball source for 2026/27).
- Changing watchability scoring, Monte Carlo simulation, or feed-cache HTTP architecture.
- Unofficial ESPN/SofaScore clients.

## Further Notes

- Supersedes the API-Football secondary in ADR 0002; does not reopen mapping tables from spec 0003 or additive/pre-flight rules from spec 0004.
- Related tickets: TheSportsDB fallback remains #52; full squad ingestion from API-Football is #84 and should be retitled or closed later because that vendor is gone.
- Football-Data.org free coverage is twelve competitions; delayed scores on the free plan are acceptable for this spec. Live scores improve only if the operator later buys the livescores add-on without code-coupling to API-Football.
- openfootball/champions-league currently ends at 2025/26; do not treat GitHub community JSON as a UCL 2026/27 source.
- Local-first: seed and updater against SQLite before any production sync.
