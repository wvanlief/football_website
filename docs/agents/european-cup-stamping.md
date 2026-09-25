# European-cup stamping

How leftover Champions League, Europa League, and Conference League rows relate to overlay, the homepage feed, and human SQL review. Read this before deleting production fixtures, “fixing” duplicate UCL rows, or assuming unstamped means fake.

Tracker: leftover review is #145 (human SQL only). Follow-ups from the 2026-09-17 production pass are #165.

## Stamp

A **stamp** is a provider fixture id on `fixtures.api_id`.

- Football-Data.org: `fd_575331`
- TheSportsDB: `tsdb_…`

Overlay is additive (#142): match an existing row by provider id, then unique home/away in that tournament, then kickoff window; on match, stamp and update date/stage; on no match, INSERT. It must not DELETE and must not change home or away.

**Unstamped** means `api_id` is null or blank. The row is a local seed/draw leftover until overlay links it. Unstamped is not “unplayed”: Liverpool vs Atlético Madrid on 2026-09-09 is Finished and stamped (`fd_575331`).

## Leftover SELECT (#145)

Scheduled, unstamped, 2026/27 European cups, and no stamped twin with the **same** `tournament_id` + `home_team_id` + `away_team_id`. That result is not a delete list.

- Official pairing still in the result (example: Liverpool vs Atlético, or Barcelona vs Aston Villa with no `fd_…` row) → overlay missed it → leave the row.
- Invented knockout placeholders (Play-offs through Final before those rounds exist in the provider) → human may delete.
- Unstamped row whose stamped twin already exists with the same team ids → overlay inserted beside the draw row; the unstamped id is the leftover.

There is no admin purge. Seeder `retire_european_draw_placeholders` is a no-op. Cascaded fixture odds go with a deleted fixture. Do not delete teams.

## Production snapshot (2026-09-17)

Query production via gitignored `.env.local/secrets` (`DATABASE_PUBLIC_URL` or a raw URL). Do not put `DATABASE_PUBLIC_URL` in `.env`: `backend/database.py` prefers it over SQLite, so local uvicorn would hit Postgres.

| Competition | Stamped | Unstamped | Leftover SELECT |
| --- | ---: | ---: | ---: |
| UEFA Champions League | 192 | 140 | 106 |
| UEFA Europa League | 44 | 189 | 189 |
| UEFA Conference League | 158 | 153 | 153 |

Leftover SELECT total **448**. Knockout placeholders (Play-offs through Final) are invented. League-phase leftovers mix official unstamped pairings with the old draw calendar. Europa’s 144 leftover league-phase rows are the full local EL calendar; overlay only stamped 44 other rows.

Known official 2026-11-03 UCL slots:

| Unstamped id | Pairing | Stamped twin (same team ids) |
| --- | --- | --- |
| 12074 | Shakhtar Donetsk vs Sporting CP | 12193 `fd_575377` |
| 12076 | Atlético Madrid vs Bayern München | 12196 `fd_575381` |
| 12081 | Manchester United vs Roma | 12198 `fd_575383` |
| 12077 | Barcelona vs Aston Villa | none |
| 12082 | Villarreal vs Paris Saint Germain | none |

## What the app shows

Once a tournament has **any** stamp, `backend/crud/fixture.py` `_scheduled_unstamped_clause` omits **scheduled unstamped** rows in that tournament. Homepage feed, tournament fixture lists, and recommended use that clause. All three 2026/27 European cups already have stamps, so the 448 leftovers are hidden on those surfaces.

Stamped copies are what the visitor sees (Shakhtar vs Sporting as 12193, not 12074).

Official unstamped rows with **no** twin are hidden too — Barcelona vs Aston Villa on 2026-11-03 is missing from those feeds.

`get_calendar_fixtures` in `backend/services/queries.py` does **not** apply the hide rule. Calendar for a European cup can still list leftovers.

Finished unstamped rows stay eligible. The 448 leftovers are all Scheduled.

## Agent rules

1. Re-count before acting; the snapshot above ages.
2. Human SQL only for DELETE. Do not add a purge job to seeder, updater, or overlay.
3. Do not mass-delete the leftover SELECT.
4. Prefer stamping the existing row over inserting a second official pairing.
5. After overlay, confirm a known official pairing is stamped (Liverpool vs Atlético 2026-09-09) and that a leftover invented pairing is hidden on the homepage.
