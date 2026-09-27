## Parent

Catalog-coverage epic. **Human / Railway only.** Run only after overlay-safety (aliases) is **deployed**. Football-API provider needed for the empty-cup section.

## Actor

William on Railway console + Postgres query UI. AFK agents: do not run these commands.

## Do not

- `seed-all`
- `seed-one --league=140` (La Liga done 2026-09-17; 189 leftovers already deleted)
- Continue a league if `created` ≈ existing season size (La Liga was 189 creates on 380 — **abort and comment**)
- DELETE from seeder; leftover European cups stay #145
- `--fetch_squads`

## 0. UEFA Nations League (do this first)

2026/27 league phase is underway (24 Sep–17 Nov). Saturday 26 Sep and Sunday 27 Sep matchdays are not in the database until this runs. Catalog id is **5**. Not on Football-Data.org, so `seed-one` uses a Highlightly season dump (a few pages). Creates are expected on an empty tournament.

```bash
python -m backend.cli seed-one --league=5
```

Stop if Highlightly returns 0 and the log falls through to a short TheSportsDB list. Record `fixtures_created` / `fixtures_updated`. `seed-one` rebuilds the feed cache.

## A. Football-Data.org kickoff overlay (1 call each)

These have full calendars but many remaining **15:00 UTC** placeholders (snapshot 2026-09-17): Premier League, Ligue 1, Primeira Liga, Eredivisie.

```bash
python -m backend.cli seed-one --league=39
python -m backend.cli seed-one --league=61
python -m backend.cli seed-one --league=94
python -m backend.cli seed-one --league=88
```

One at a time. Record `fixtures_created` / `fixtures_updated`. Expect **mostly updates**. Then feed rebuild (`python -m backend.services.feed_builder` or the import-first `python -c` workaround).

Skip Serie A / Bundesliga unless a later recount shows placeholder times. Skip UCL `seed-one --league=2` unless kickoffs are still wrong; UCL leftover stamping is #165.

## B. Empty cups (Football-API, 1 fixtures call each)

Only after Football-API provider is on production. Spread if quota is tight (≤10 Football-API fixture calls/day in the plan).

| League id | Competition |
|---:|---|
| 45 | FA Cup |
| 48 | EFL Cup |
| 66 | Coupe de France |
| 90 | KNVB Beker |
| 96 | Taça de Portugal |
| 257 | US Open Cup |
| 16 | CONCACAF Champions Cup |

```bash
python -m backend.cli seed-one --league=45
# …repeat per id
```

Empty tournaments: **creates are expected**. Preflight must not abort because stored count is 0.

## C. Stale results / partial calendars (later the same week)

Football-API overlay, still one league at a time:

| League id | Competition | Snapshot issue |
|---:|---|---|
| 179 | Scottish Premiership | 198 rows, 102 leftover 15:00 |
| 144 | Belgian Pro League | 306 rows, 90 leftover 15:00 |
| 203 | Süper Lig | 306 rows, **0 finished** |
| 137 | Coppa Italia | 16 rows, stops 17 Aug |
| 81 | DFB Pokal | 32 rows, stops 2 Sep |
| 71 | Brasileirão | 375/380 |
| 73 | Copa do Brasil | stops 6 Aug |
| 130 | Copa Argentina | stops 30 Aug |
| 13 | Copa Libertadores | later knockout thin |
| 11 | Copa Sudamericana | later knockout thin |

## D. Feed rebuild after each batch

```bash
python -m backend.services.feed_builder
```

## Done when

- [ ] Nations League `seed-one --league=5` recorded; this weekend's games are in the feed
- [ ] Section A four leagues overlaid; created/updated commented
- [ ] Section B empty cups have fixtures > 0 or a commented provider 404/quota stop
- [ ] Section C either done or explicitly deferred with quota note
- [ ] No second La Liga seed
- [ ] Feed cache rebuilt after the last successful overlay
