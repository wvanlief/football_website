# 06 — Production Verification & Chrome DevTools Audit Guide

**What to build:** A step-by-step verification guide for testing the deployed production site (`findfootball.games`). Direct the user on which actions to perform, which Chrome DevTools tabs to inspect (Network tab for 0 `/api/fixtures` call, Console tab for timezone logs), and what outputs to paste to confirm 100% operational success.

**Blocked by:** 05 — Inline Data Hydration & Client Timezone Renderer

**Status:** ready-for-agent

- [ ] Guide user on DevTools Network Tab audit (verify 0 extra `/api/fixtures` fetch on page load)
- [ ] Guide user to verify instant timezone rendering across Today, Tomorrow, and This Week columns
- [ ] Guide user to test Region chips (`Europe >` vs `Americas >`) and verify 0ms in-memory filter switching
- [ ] Collect user verification outputs (Network Tab screenshot/text) and confirm 100% production health
