# 04 — Pre-Calculated Feed Generator & Railway Service Configuration Reminder

**What to build:** Implement a background worker task that pre-computes the feed dataset (rolling window `-14 days` to `+30 days`) and writes `fixtures_feed_cache.json`. Include a mandatory user prompt/reminder at the end of implementation to configure the Railway Cron Service.

**Blocked by:** 02 — Global Single-Call API Sync Engine & Rate Limit Upgrade, 03 — Regional ELO Baselines & Watchability Hot List Gating

**Status:** ready-for-agent

- [ ] Build background feed pre-computer module generating `fixtures_feed_cache.json`
- [ ] Configure twice-weekly heavy enrichment schedule (narratives, ELOs, watchability scores) on Mondays and Fridays
- [ ] Configure daily lightweight score/status updates for pre-calculated JSON feed
- [ ] **Mandatory Railway Reminder**: Prompt user to set up Railway Cron Service `admin-update-cron` schedule to `0 4 * * *` (Daily at 4 AM UTC) and `backend-updater-cron` schedule to `*/15 * * * *` (Every 15 minutes)
