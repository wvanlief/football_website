# 01 — Local Badge Asset Caching & Dynamic Logo Delivery

**What to build:** End-to-end local badge asset storage and dynamic delivery. During team ingestion, download team crest PNGs to static local storage. Add `logo_url` to backend API payloads for teams and fixtures. Update all frontend pages (Home, Standings, Bracket, Team Profile) to render team badges dynamically from `logo_url`, removing all hardcoded JS badge dictionaries.

**Blocked by:** None — can start immediately.

**Status:** closed

- [x] Backend database schema includes `logo_url` field for all `Team` records.
- [x] Team ingestion downloads crest PNGs to `/static/badges/{api_id}.png` and handles fallbacks.
- [x] Static file router mounts `/static` to serve badge images with cache headers.
- [x] All API payloads (`/api/fixtures`, `/api/competitions`, `/api/teams/`) include `logo_url`.
- [x] Hardcoded `CLUB_BADGES` dictionaries removed from frontend JS files; badges render dynamically everywhere.

