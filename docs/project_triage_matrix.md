# FindFootball.Games — Master Triage Matrix

All recommendations, bugs, architecture changes, and feature ideas extracted from every available source, deduplicated and classified.

---

## Triage Dimensions

Rather than a simple priority list, each item is classified along **two axes**:

| Axis | Levels | Definition |
|------|--------|------------|
| **Scope** (effort) | 🟢 **Quick Win** — under 1 sitting, no arch risk | 🟡 **Medium** — a few sessions, touches multiple files | 🔴 **Large** — multi-day, architectural change |
| **Readiness** (how close to implementation) | 💡 **Idea** — concept only, needs design | 📐 **Shaped** — problem + direction clear, needs spec | 🔧 **Implementation-Ready** — spec exists or fix is obvious |

This gives a 3×3 matrix. Items in the top-right (🟢🔧) are the lowest-hanging fruit; items in the bottom-left (🔴💡) are the most speculative and expensive.

```
                    💡 Idea          📐 Shaped          🔧 Impl-Ready
  ┌────────────────┬────────────────┬────────────────┐
  │ 🟢 Quick Win   │  Cheap but     │  Quick design  │  ★ DO FIRST ★  │
  │                │  underspecified │  needed        │  Grab & go     │
  ├────────────────┼────────────────┼────────────────┤
  │ 🟡 Medium      │  Needs both    │  Design then   │  Schedule it   │
  │                │  design+build  │  build          │                │
  ├────────────────┼────────────────┼────────────────┤
  │ 🔴 Large       │  Strategic bet │  Major project │  Epic, but     │
  │                │  needs research│  needs planning │  well defined  │
  └────────────────┴────────────────┴────────────────┘
```

---

## Sources Legend

| Code | Source Document |
|------|----------------|
| **GPT** | [codebase-review-GPT-130826.md](file:///c:/Users/user/PycharmProjects/football_website/docs/codebase-review-GPT-130826.md) |
| **CL** | [codebase-review-claude-130826.md](file:///c:/Users/user/PycharmProjects/football_website/docs/codebase-review-claude-130826.md) |
| **TODO** | [TODO.md](file:///c:/Users/user/PycharmProjects/football_website/TODO.md) |
| **BL** | [backlog.md](file:///c:/Users/user/PycharmProjects/football_website/docs/backlog.md) |
| **WF** | [wayfinder-map-ui-overhaul.md](file:///c:/Users/user/PycharmProjects/football_website/docs/wayfinder-map-ui-overhaul.md) |
| **ARCH** | [Architecture review conversation](file:///C:/Users/user/.gemini/antigravity-ide/brain/c30a6084-b918-4d57-929e-97a53a9b222b/implementation_plan.md) |
| **CR** | [Code review of ingestion refactor](file:///C:/Users/user/.gemini/antigravity-ide/brain/7e87bcdf-8d1c-4015-b650-8c06ac6a23c0/code_review.md) |
| **DB** | [database_analysis.md](file:///c:/Users/user/PycharmProjects/football_website/database_analysis.md) |
| **SPEC** | [docs/specs/](file:///c:/Users/user/PycharmProjects/football_website/docs/specs) |
| **ADR** | [docs/adr/](file:///c:/Users/user/PycharmProjects/football_website/docs/adr) |
| **GH** | GitHub Issues |
| **CTX** | [CONTEXT.md](file:///c:/Users/user/PycharmProjects/football_website/CONTEXT.md) |
| **POP** | [data_population_strategy.md](file:///c:/Users/user/PycharmProjects/football_website/data_population_strategy.md) |

---

## Category 1: 🐛 Bugs & Broken Behavior

| # | Item | Scope | Readiness | Sources | Notes |
|---|------|-------|-----------|---------|-------|
| B1 | **Test suite fails when run as a whole** — 52 errors due to shared SQLite engine and `create_all`/`drop_all`/`os.remove` collision | 🟢 | 🔧 | CL §3.1 | Fix `conftest.py`: switch to in-memory SQLite with `StaticPool` or unique temp file per test. Post-ingestion refactor showed 91 passing — verify if this is still broken. |
| B2 | **Inconsistent team badge display** — some badges missing, some showing wrong logos (Sparta Praha → Besiktas, Dinamo Zagreb → Gent, Qarabag no logo) | 🟢 | 🔧 | TODO P1, SPEC-0001 | SPEC-0001 addressed this but TODO still lists it — verify current state. |
| B3 | **Group page shows all competitions** — group/bracket pages don't filter to selected competition | 🟡 | 📐 | TODO P1 | CL §3.8 suggests shared root cause with duplicated filtering logic (B6). |
| B4 | **Bracket defaults to World Cup tree** for all competitions | 🟡 | 📐 | TODO P1, SPEC-0001 | May be resolved by format_engine routing. Verify current state. |
| B5 | **Calendar watchability only shows 3 Man Utd matches ≥75** — calibration or filtering bug | 🟡 | 📐 | TODO P1 | Likely related to threshold brittleness (see F5) or score concentration. Needs investigation. |
| B6 | **Fixture-eligibility logic implemented 3 separate times** — feed_builder, tournament.py, app.js each independently decide date windows and eligibility | 🟡 | 🔧 | CL §3.5 | Recurring bug class — caused at least 2 production incidents. Consolidation spec exists conceptually. |
| B7 | **ELO 1500 default for non-European clubs** inflates competitiveness scores — 1500-vs-1500 matches score 100% competitiveness | 🟡 | 📐 | TODO P1, CTX, ADR-0003 | Partial mitigation via regional baselines (CTX), but true fix needs in-house ELO engine. |
| B8 | **Redundant OR condition in fixture settling** — `status == "Finished" or (... and status == "Finished")` | 🟢 | 🔧 | CR §8 | Dead code — second branch is subset of first. |
| B9 | **`assert_no_deletes` is a dead no-op** | 🟢 | 🔧 | CR §3 | Either delete or implement as real runtime assertion. |
| B10 | **Country code fallback is fragile** — `norm_name[:3].upper()` produces incorrect codes ("Wolverhampton" → "WOL") | 🟡 | 📐 | CR §6 | Now centralized in TeamResolver — affects all providers. Needs proper country code mapping. |
| B11 | **Red dot CSS artifacts** on search bar container | 🟢 | 🔧 | SPEC-0001 | Pure CSS fix. |
| B12 | **Stale match display** — past-dated "Scheduled" fixtures rendered as upcoming | 🟡 | 🔧 | GPT §4.9, CL §3.3 | Root cause addressed in feed builder but recurring bug class. Needs regression test. |
| B13 | **`IngestorService` is a Middle Man** — thin wrapper delegating to seeder with no logic | 🟢 | 🔧 | CR §7 | Delete or collapse into `IngestionEngine`. |
| B14 | **ELO history deduplication not implemented** — re-running seed creates duplicate `EloHistory` rows | 🟡 | 🔧 | CR Spec §1 | Odds dedup exists but ELO history dedup was missed per spec-0004. |

---

## Category 2: 🏗️ Architecture & Technical Debt

| # | Item | Scope | Readiness | Sources | Notes |
|---|------|-------|-----------|---------|-------|
| A1 | **No CI / no deploy gate** — pushes go straight to Railway with no test or review step | 🟡 | 🔧 | CL §3.2 | Add GitHub Actions: `pytest` on push/PR. Structural root cause of production incident. |
| A2 | **Committed build artifact** (`fixtures_feed_cache.json`) — should be `.gitignored` and generated at startup | 🟢 | 🔧 | CL §3.3 | Add to `.gitignore`, generate at deploy. |
| A3 | **Dead frontend code** — ~5,200 lines of unreferenced CSS/JS (prototype-ui.js, styles-backup, archived-styles.css) | 🟢 | 🔧 | CL §3.4, WF | Confirmed unreferenced by any HTML file. WF links to them as "backups" but they're dead. |
| A4 | **Unpinned dependencies** — `requirements.txt` uses `>=` everywhere, no lockfile | 🟢 | 🔧 | CL §3.7 | Pin versions or introduce `pip-tools`/`poetry`. |
| A5 | **God files** — `tournament.py` (894 lines), `seeder.py` (921→reduced but still large), `simulation.py` (706), `format_adapters.py` (600) | 🔴 | 📐 | CL §3.6 | Split by responsibility: fetch / transform / persist. CI needed first (A1). |
| A6 | **Duplicated `call_football_api`** in seeder.py and api_football.py | 🟢 | 🔧 | CR §1 | Delete from seeder, import from provider. |
| A7 | **Duplicated `fetch_json` wrapper** in format_adapters.py and updater.py | 🟢 | 🔧 | CR §2 | Consolidate into `backend.utils`. |
| A8 | **Hardcoded magic `2026` season fallback** in IngestionEngine | 🟢 | 🔧 | CR §4 | Replace with named constant or explicit error. |
| A9 | **`FixtureUpserter._ensure_fixture_odds` potential N+1** — loads all odds then filters in Python | 🟡 | 📐 | CR §5 | Use SQL `EXISTS` with date filter instead. |
| A10 | **`seed_competition` creates new IngestionEngine per call** — ~28 instantiations in `seed_all_default_competitions` | 🟢 | 📐 | CR §9 | Share one engine instance across batch seed. |
| A11 | **Hardcoded data in seeder.py** — `ELO_RATINGS`, `GROUPS`, `SPOTLIGHT_PLAYERS`, `get_fallback_matches` (~600 lines) | 🟡 | 📐 | CR Spec §2, ARCH | Move to JSON config files or replace with real API data. |
| A12 | **No staging/preview deploy** — AI-driven changes go straight to prod | 🟡 | 💡 | CL §5 | Consider Railway preview environments or branch deploys. |
| A13 | **TheSportsDB third fallback provider** not implemented | 🟡 | 💡 | CR §3, ADR-0002 | ADR-0002 specifies 3-provider chain but only 2 exist. |
| A14 | **Data population Phase 3 incomplete** — Serie A (135) still pending fetch & seed | 🟡 | 🔧 | POP §Phase 3 | Execute the remaining Serie A ingestion commands. |
| A15 | **Data population Phases 4-6 not started** — European Cups, Domestic Cups + Nations League, Live Updater activation | 🔴 | 🔧 | POP §Phases 4-6 | Well-specified execution plan exists but not yet executed. |
| A16 | **Canonical definitions not centralized** — "fixture", "upcoming", "competition", "region", "watchability", "recommendation tier" each defined ad-hoc | 🟡 | 📐 | GPT §6.3 | Create a single definitions module consumed by all layers. |

---

## Category 3: 🎨 UI/UX & Product

| # | Item | Scope | Readiness | Sources | Notes |
|---|------|-------|-----------|---------|-------|
| U1 | **Mobile view adaptation & bottom tab bar** — open wayfinder ticket #25 | 🟡 | 🔧 | WF, GH #25 | Last remaining ticket from UI overhaul. Spec exists. |
| U2 | **Homepage too dashboard-like** — too many competing concepts (nav, filters, results strip, recommendations, ELO, dates…) | 🔴 | 📐 | GPT §4.1 | Reduce density; make recommendation the dominant UI element. |
| U3 | **Value proposition not communicated** — homepage shows "matches + metadata" instead of "best matches to watch" | 🔴 | 📐 | GPT §4.2 | Strategic UX change — needs design. |
| U4 | **Too much raw model info exposed** — ELO and metrics shown at first level | 🟡 | 📐 | GPT §4.3 | Implement progressive disclosure: Teams+Watchability → Why → Advanced. |
| U5 | **Watchability score lacks context** — "84" doesn't explain what it means | 🟡 | 📐 | GPT §4.4 | Add explanation tooltip or descriptor. |
| U6 | **Add score percentile context** — show "82 · Top 4% this week" | 🟡 | 📐 | GPT §4.5, §5.3 | Backend needs percentile calculation per time window. |
| U7 | **Overlapping recommendation labels** — Hot, Recommended, Must Watch, Upcoming Gems, Watchability | 🟡 | 📐 | GPT §4.7 | Standardize to: Must Watch / Recommended / Other. |
| U8 | **Arbitrary 75+ threshold is brittle** — stops working as fixture universe changes | 🟡 | 📐 | GPT §4.6 | Switch to dynamic ranking: Top 5%, Best 5 today, Top 10 this week. |
| U9 | **Better empty states** — never show stale data to avoid empty UI | 🟢 | 📐 | GPT §7 QW7 | "No matches found. Refreshing…" instead of confidently wrong data. |
| U10 | **Freshness indicator** — "Data updated 2 min ago" | 🟢 | 📐 | GPT §7 QW5 | Frontend display of last cache refresh timestamp. |
| U11 | **Gameweek/Matchday pagination** — slider bar for Gameweek 1-38 | 🟡 | 💡 | TODO Future, WF Not Yet Specified | Calendar slider showing hot matches per gameweek. |
| U12 | **Calendar needs team logos and gameweek segmentation** | 🟡 | 🔧 | SPEC-0001 §9 | SPEC exists but verify current implementation state. |

---

## Category 4: ✨ New Features

| # | Item | Scope | Readiness | Sources | Notes |
|---|------|-------|-----------|---------|-------|
| F1 | **"Best Match Today" hero** — single most prominent element on homepage | 🟡 | 📐 | GPT §5.1 | The product's core answer to "What should I watch?" |
| F2 | **"Why Watch?" explanations** — 2-4 short reasons on match cards | 🟡 | 📐 | GPT §5.2, §7 QW2 | Model already has inputs (competitiveness, form, stakes, odds). Convert to human-readable reasons. |
| F3 | **Favorite team filtering** — localStorage-based initially, no accounts needed | 🟡 | 📐 | GPT §5.4, §7 QW6, TODO Future | High retention value. Relatively limited implementation cost. |
| F4 | **Favorite competition filtering** | 🟡 | 📐 | GPT §5.4, TODO Future | Can pair with F3. |
| F5 | **Dynamic ranking** replacing fixed thresholds — Top 5% / Best 5 today / Top 10 this week | 🟡 | 📐 | GPT §5.8 | Backend calculates relative position instead of absolute score cutoff. |
| F6 | **Match detail page** — rich page with Why, Prediction, Form, Odds, ELO, Stakes, Key Players | 🔴 | 📐 | GPT §5.6 | Significant new page. Needs design. |
| F7 | **Shareable match cards** — social cards for sharing recommendations | 🟡 | 💡 | GPT §5.7, TODO P2 | OG image generation, social export format. |
| F8 | **Daily/weekly recommendation loop** — "Tonight's 3 must-watch", "Best match today", "5 matches this week" | 🟡 | 💡 | GPT §5.5 | Content generation system — could be automated or manual. |
| F9 | **Social media export** — export good matches to Insta/TikTok | 🟡 | 💡 | TODO P2 | Needs card generation + platform integration. |
| F10 | **Team historical data** | 🟡 | 💡 | TODO P2 | History in the Form box. |
| F11 | **Odds movement tracking** | 🟡 | 💡 | TODO P2 | Time-series odds visualization. |
| F12 | **Reactivate Monte Carlo simulation** — currently disabled to keep admin cron fast | 🟡 | 📐 | TODO P2 | Run async or on separate schedule. |
| F13 | **Match timeline** | 🔴 | 💡 | TODO P3 | Live match event stream. Needs external data source. |
| F14 | **Player historical data** | 🔴 | 💡 | TODO P3 | Requires full squad ingestion first. |
| F15 | **Head-to-head data** | 🟡 | 💡 | TODO P3 | Historical fixture query + display. |
| F16 | **Best odds from different bookmakers** | 🟡 | 💡 | TODO P3 | Multi-bookmaker comparison. |
| F17 | **Spotlight Calendar** — "Top 5 Blockbusters" carousel looking 30 days ahead | 🟡 | 💡 | TODO Future | Curated major derby lookahead. |
| F18 | **Full squad ingestion** — all players from API-Football squads | 🔴 | 📐 | TODO Future, BL | Currently only 3-player spotlight. Costs 200+ API calls. |
| F19 | **Single-competition admin seed endpoint** (`/api/admin/seed-one`) | 🟢 | 🔧 | Done | Implemented in Issue #85. |
| F20 | **In-house ELO calculation engine** for non-European clubs (CONMEBOL, MLS, CAF, AFC) | 🔴 | 💡 | TODO P1 | Calculate ELO from match results instead of relying on external sources. |
| F21 | **Personalized recommendations** — "Your best matches this week" | 🔴 | 💡 | GPT §5.4 | Depends on F3 (favorites). Could work without accounts using localStorage. |

---

## Category 5: 📝 Documentation & Process

| # | Item | Scope | Readiness | Sources | Notes |
|---|------|-------|-----------|---------|-------|
| D1 | **Establish canonical product rules** — explicit definitions for fixture universe, discovery feed, exploration | 🟡 | 📐 | GPT §4.8 | The Americas/Europe incident exposed ambiguity around these concepts. |
| D2 | **Production smoke tests** | 🟡 | 📐 | GPT §10 Phase 0 | Automated checks that critical paths work after deploy. |
| D3 | **Freshness monitoring** | 🟡 | 📐 | GPT §10 Phase 0 | Alert when feed data is stale beyond threshold. |
| D4 | **Regression tests for date/status/competition filtering** | 🟡 | 🔧 | GPT §10 Phase 0 | The "stale fixture" bug class has recurred ≥2 times. |
| D5 | **Product decision principles document** | 🟢 | 🔧 | GPT §12 | Already drafted in GPT review — formalize as `docs/product-principles.md`. |
| D6 | **Engineering rules for AI agents** | 🟢 | 🔧 | GPT §11 | Already drafted — formalize in AGENTS.md (partially done). |

---

## Prioritized Action Plan (Suggested Phases)

### Phase 0 — Stop the Bleeding (Quick Wins, ~1 sitting)

> [!TIP]
> These are all 🟢🔧 — grab and go. Zero architectural risk.

| Item | Action |
|------|--------|
| A2 | Add `fixtures_feed_cache.json` to `.gitignore` |
| A3 | Delete dead frontend files (prototype-ui.js, styles-backup, archived-styles.css) |
| A4 | Pin dependency versions in `requirements.txt` |
| A6 | Delete duplicate `call_football_api` from seeder.py |
| A7 | Consolidate duplicate `fetch_json` wrapper |
| A8 | Replace magic `2026` with named constant |
| B8 | Fix redundant OR condition in fixture_upserter.py |
| B9 | Delete or implement `assert_no_deletes` |
| B11 | Fix red dot CSS artifacts |
| B13 | Remove `IngestorService` Middle Man |
| D5 | Formalize product decision principles |
| D6 | Formalize engineering rules in AGENTS.md |

---

### Phase 1 — Restore the Safety Net (~2 sessions)

| Item | Action |
|------|--------|
| B1 | Fix `conftest.py` DB isolation |
| A1 | Add GitHub Actions CI (pytest on push/PR) |
| B14 | Implement ELO history date deduplication |
| D4 | Add regression tests for date/status/competition filtering |
| B12 | Add regression test for stale match display |

---

### Phase 2 — Fix the Recurring Bug Class (~2-3 sessions)

| Item | Action |
|------|--------|
| B6 | Consolidate 3 fixture-eligibility implementations into 1 |
| A16 | Centralize canonical definitions |
| B3+B4 | Investigate group/bracket page filtering (likely shares root cause with B6) |
| B5 | Investigate calendar watchability calibration |
| B10 | Fix country code fallback in TeamResolver |

---

### Phase 3 — Core Recommendation Experience (multi-session)

| Item | Action |
|------|--------|
| U7 | Standardize recommendation vocabulary (Must Watch / Recommended / Other) |
| F1 | Build "Best Match Today" hero component |
| F2 | Add "Why Watch?" explanations to match cards |
| U6 | Add score percentile context |
| F5 | Implement dynamic ranking (replace fixed 75+ threshold) |
| U9 | Better empty states |
| U10 | Freshness indicator |
| U4 | Implement progressive disclosure for model metrics |
| U1 | Complete mobile view (#25) |

---

### Phase 4 — Retention & Personalization

| Item | Action |
|------|--------|
| F3 | Favorite team filtering (localStorage) |
| F4 | Favorite competition filtering |
| F8 | Daily/weekly recommendation loops |
| F21 | Personalized "Your best matches" |

---

### Phase 5 — Match Depth & Sharing

| Item | Action |
|------|--------|
| F6 | Match detail page |
| F7 | Shareable match cards |
| F9 | Social media export |
| F10 | Team historical data |
| F11 | Odds movement tracking |
| F12 | Reactivate Monte Carlo simulation |

---

### Phase 6 — Advanced Features & Infrastructure

| Item | Action |
|------|--------|
| A5 | Split god files (requires CI from Phase 1) |
| A12 | Set up staging/preview environment |
| F20 | In-house ELO engine |
| F18 | Full squad ingestion |
| F13 | Match timeline |
| F14 | Player historical data |
| F15 | H2H data |
| F16 | Best odds comparison |
| A13 | TheSportsDB third fallback provider |

---

### Ongoing / Operational

| Item | Action |
|------|--------|
| A14 | Complete Serie A data population |
| A15 | Execute data population Phases 4-6 |
| F19 | Build admin seed-one endpoint (COMPLETED - #85) |
| D2 | Implement production smoke tests |
| D3 | Set up freshness monitoring |
| D1 | Formalize product rules document |

---

## Summary Statistics

| Category | Count |
|----------|-------|
| 🐛 Bugs | 14 |
| 🏗️ Architecture / Tech Debt | 16 |
| 🎨 UI/UX | 12 |
| ✨ New Features | 21 |
| 📝 Docs & Process | 6 |
| **Total unique items** | **69** |

| Scope | Count |
|-------|-------|
| 🟢 Quick Win | 19 |
| 🟡 Medium | 37 |
| 🔴 Large | 13 |

| Readiness | Count |
|-----------|-------|
| 🔧 Implementation-Ready | 28 |
| 📐 Shaped | 30 |
| 💡 Idea | 11 |

> [!IMPORTANT]
> **19 items are Quick Wins that are Implementation-Ready** — these can be turned into GitHub issues immediately and executed without further design. The Phase 0 list above captures 12 of them for the first sitting.
