# findfootball.games — Codebase Review

Source: manual review of `wvanlief/football_website` (commit `e3dc8da`, post-rollback) —
repo structure, test run, dependency file, and dead-code check.
Purpose: input for an agent to plan and execute follow-up work. Each action item is
independent and can be picked up on its own.

---

## 1. Scoring / Overall Assessment

| Area | Rating | Note |
|---|---|---|
| Domain logic depth | Strong | ELO, Monte Carlo sim, watchability scoring, 2-legged ties, promotion/relegation |
| Documentation discipline | Strong | ADRs, specs, backlog with reasoning, prior post-mortem doc |
| Test coverage (breadth) | Good | 76 tests across routers/services/CRUD |
| Test suite health (reliability) | **Broken** | Passes in isolation, fails as a suite — see 3.1 |
| Deploy safety | **Weak** | No CI, no test gate, no review step before prod |
| Code organization | Weak | Several oversized "god files," duplicated logic across layers |
| Repo hygiene | Weak | ~5,200 lines of dead frontend code committed and unused |
| Dependency management | Weak | No version pinning, no lockfile |

**One-line summary:** the domain logic and planning discipline are genuinely above
personal-project average; the weak point is entirely in the safety net between
"code is written" and "code is live" — that gap is what turned a filtering bug into
a multi-hour production incident.

---

## 2. Strengths (keep doing this)

- Multi-source data ingestion with fallback chain (football-data.org → API-Football).
- Real football-domain logic: ELO, Monte Carlo simulation, watchability scoring,
  2-legged tie aggregate propagation, Nations League promotion/relegation.
- Alembic migrations properly tracked.
- Admin endpoints gated behind a token; a rate limiter service exists.
- Existing test coverage spans routers, CRUD, and services — standings, settling,
  simulation, weights, multi-source fallback.
- Strong documentation habit: ADRs (`docs/adr/`), specs (`docs/specs/`), a reasoned
  backlog (`docs/backlog.md`), and — notably — a prior post-mortem doc for a related
  incident (`07-post-mortem-cross-pollination-root-cause-and-prevention.md`).

---

## 3. Weaknesses / Risks (findings, not yet actioned)

### 3.1 Test suite is broken when run as a whole
Running `pytest` on the full suite: **24 passed, 52 errors.** Every failing test
passes individually. Root cause: `tests/conftest.py` uses one shared, module-level
`engine` against a single file-based SQLite DB, with `create_all` / `drop_all` /
`os.remove` per test — this collides under a full run. The safety net currently
does not work, and nobody would know without running the whole suite explicitly.

### 3.2 No CI, no deploy gate
No `.github/workflows`. `predeploy.py` only runs Alembic migrations — it does not
run tests and does not touch the fixtures cache. There is no PR/review step; pushes
go straight to Railway. This is the structural root cause of the recent incident:
nothing stood between AI-generated code and production.

### 3.3 Committed build artifact (`fixtures_feed_cache.json`)
The homepage's fixture feed cache is generated code, but it's committed to git and
read from disk before any DB query. This alone caused an empty-cache bug and a
truthiness bug, and complicated diagnosis of the recent World Cup regression.

### 3.4 Dead code at meaningful scale
- `frontend/js/prototype-ui.js` — 793 lines, not referenced by any HTML file.
- `frontend/css/styles-backup-pre-overhaul.css` — 4,342 lines, not referenced.
- `frontend/css/archived-styles.css` — 115 lines, not referenced.

Combined, this is more dead code than the live CSS/JS it sits next to. Risk isn't
just repo bloat — it's real confusion (for you and for any AI agent grepping the
repo) about which file is authoritative.

### 3.5 Fixture-eligibility logic is implemented three separate times
- `backend/services/feed_builder.py` (cache fallback query)
- `backend/services/tournament.py::get_grouped_fixtures` (live API route)
- `frontend/js/app.js` (client-side grouping)

Each independently decides date windows and tournament eligibility. This is why
"wrong matches showing" has now happened at least twice via two *different*
mechanisms (see the existing cross-pollination post-mortem doc vs. the recent
incident) — the intended rule ("only future, eligible fixtures") isn't centralized
anywhere, so it drifts out of sync across layers.

### 3.6 Oversized files ("god files")
`tournament.py` (894 lines), `seeder.py` (921 lines), `simulation.py` (706 lines),
`format_adapters.py` (600 lines). Each mixes multiple concerns (fetch, transform,
persist, format), which makes it easy for unrelated changes to get bundled into one
commit — exactly what happened when a legitimate cache fix and a fallback-query
regression landed together in a single commit during the recent incident.

### 3.7 Unpinned dependencies
`requirements.txt` uses `>=` everywhere, no lockfile. A routine install on a future
deploy can silently pull a breaking version.

### 3.8 Existing TODO items likely share root causes with the above
From your own `TODO.md` (Prio 1): "group page displays all competitions, same for
bracket," "only 3 Manchester United matches hit 75+ watchability," badge display
inconsistency. These read as symptoms of the same duplicated-filtering-logic problem
(3.5) rather than unrelated bugs — worth investigating together rather than
one-off patching each.

---

## 4. Suggestions — Quick Wins

Cheap, independent, high value. No architectural risk.

- [ ] Delete `frontend/js/prototype-ui.js`, `frontend/css/styles-backup-pre-overhaul.css`,
      `frontend/css/archived-styles.css` (confirmed unreferenced by any HTML file).
- [ ] Add `backend/data/fixtures_feed_cache.json` to `.gitignore`; stop committing it.
      Generate it at startup/deploy instead.
- [ ] Fix `tests/conftest.py` DB isolation: switch to in-memory SQLite with
      `StaticPool`, or a unique temp file per test, instead of a shared module-level
      engine. This alone restores the existing 76 tests to being trustworthy.
- [ ] Pin dependency versions in `requirements.txt` (or introduce a lockfile via
      `pip-tools`/`poetry`).

---

## 5. Suggestions — Structural / Larger Effort

- [ ] Add a minimal CI workflow (GitHub Actions): run `pytest` on every push/PR,
      before Railway deploys. Forces a PR-shaped workflow instead of direct pushes
      to `main`.
- [ ] Consolidate the three "which fixtures are eligible" implementations
      (3.5) into a single function used by both the backend cache builder and the
      live API route, with the frontend consuming its output rather than
      re-deriving eligibility client-side. Add a dedicated regression test:
      "off-season fallback returns only future fixtures, respects a cap." This
      specific bug shape has recurred at least twice — worth a permanent test
      rather than manual QA each time.
- [ ] Split `tournament.py` and `seeder.py` by responsibility (fetch vs. transform
      vs. persist) to reduce blast radius per commit.
- [ ] Investigate whether the open TODO Prio-1 items (competitions showing on
      group/bracket pages, watchability calibration only surfacing one team) share
      a root cause with 3.5 before fixing them individually.
- [ ] Consider a staging/preview deploy step before promoting to production,
      given the reliance on AI-agent-driven changes going straight to prod.

---

## 6. Roadmap Proposal

**Phase 1 — Stop the bleeding (quick wins, ~1 sitting)**
Everything in Section 4. Zero architectural risk, immediately reduces confusion
and removes the exact artifact class (`fixtures_feed_cache.json`) that caused the
last incident.

**Phase 2 — Restore the safety net**
Fix test isolation (3.1) → add CI (5, item 1). Once these two land, no future
change reaches production without passing tests, and the existing 76 tests
actually mean something again.

**Phase 3 — Fix the recurring bug class**
Consolidate fixture-eligibility logic (3.5) into one place, backed by a regression
test. Cross-check against the open TODO Prio-1 items to see how many close out as
a side effect.

**Phase 4 — Structural cleanup**
Split the oversized files (3.6) now that CI exists to catch regressions during the
refactor. Evaluate a staging/preview environment.
