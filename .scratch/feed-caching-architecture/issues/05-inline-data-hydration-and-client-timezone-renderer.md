# 05 — Inline Data Hydration & Client Timezone Renderer

**What to build:** Inject `fixtures_feed_cache.json` directly into `index.html` via an inline `<script id="initial-fixtures-data" type="application/json">` tag. Refactor `frontend/js/app.js` to parse embedded JSON on page load, convert match times to local timezone (`Intl.DateTimeFormat`), render cards instantly (<10ms) without skeleton loading screens, and handle 0ms in-memory filtering.

**Blocked by:** 04 — Pre-Calculated Feed Generator & Railway Service Configuration Reminder

**Status:** completed

- [x] Inject pre-computed JSON into `index.html` template via `<script id="initial-fixtures-data">`
- [x] Refactor `frontend/js/app.js` to parse embedded JSON on `DOMContentLoaded` without secondary API fetch
- [x] Resolve viewer timezone via browser `Intl.DateTimeFormat` and sort matches into local "Today", "Tomorrow", "This Week"
- [x] Verify region filtering (`All`, `Europe >`, `Americas >`) and country search execute in 0ms in-memory
- [x] Verify page load completes in <10ms with zero skeleton loading screens
