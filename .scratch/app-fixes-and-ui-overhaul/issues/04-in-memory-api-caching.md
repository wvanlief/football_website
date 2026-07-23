# 04 — In-Memory API Payload Response Caching

**What to build:** In-memory response caching (60s TTL) for heavy fixture endpoints (`/api/fixtures`, `/api/fixtures/recommended`). Pre-calculate and cache enriched JSON payloads to serve requests under 10ms. Automatically invalidate cache on live score updates.

**Blocked by:** 02 — Active 2026 Season & Date Anchor Filtering

**Status:** ready-for-agent

- [ ] In-memory response cache implemented for `/api/fixtures` and `/api/fixtures/recommended`.
- [ ] API response times for home page requests dropped below 10ms.
- [ ] Background updater triggers cache invalidation upon live score updates.
