# Agent Configuration

Welcome! This file documents the conventions and configurations that AI coding agents should follow when working in this repository.

## Agent skills

### Issue tracker

Issues are tracked using GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Using default canonical triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repository layout. See `docs/agents/domain.md`.

### European-cup stamping

Stamp, unstamped leftovers, overlay insert-beside, feed hiding vs calendar. See `docs/agents/european-cup-stamping.md`.

## Development & Verification Guidelines

### 1. Mandatory Local Verification Protocol
- **Local Testing First**: Never ask the user to deploy or push changes to production (Railway) to test a fix.
- **Local Replica**: Always run and test changes locally using `uvicorn backend.main:app --port 8000` connected to the local SQLite database (`football_games.db`).
- **Database Re-Sync**: Use `python -m backend.scripts.sync_production_db <DATABASE_PUBLIC_URL>` to refresh local data whenever production alignment is needed.

### 2. Browser Testing & Token Efficiency
- **Lightweight Scripts First**: Use local Python scripts (`urllib.request`, `pytest`, Playwright) for API response times, DOM checks, and HTTP status verification.
- **Single-Shot Browser Snapshots**: Avoid multi-turn interactive browser subagent loops. When visual inspection is needed, use single-shot navigation tasks (`Navigate and take 1 snapshot`).

### 3. Empirical Diagnostic Discipline
- **Verify Before Asserting**: Never formulate hypotheses about database contents, missing schemas, or league start dates without running an explicit SQL query or inspecting server logs.
- **No Swallowed Errors**: Always inspect full stack traces before forming a diagnostic hypothesis.

### 4. Feed & Cache Integrity
- **Non-Empty Cache Guarantee**: Pre-calculated feed builders (`feed_builder.py`) must never emit `total_fixtures: 0` if active tournaments exist in PostgreSQL/SQLite.
- **Off-Season Gating**: Ensure scheduled fixture filters strictly gate past-dated matches (`matchDateStr >= todayStr`) to prevent legacy matches from rendering in upcoming views.

### 5. Pull Request & Merge Etiquette
- **Never Self-Merge**: Agents must not merge their own pull requests. A PR exists so a human can review the diff before it reaches `main`; merging it yourself removes the review gate and makes the PR pointless.
- **Forbidden Commands**: Do not run `gh pr merge` (including `--auto`, `--squash`, `--rebase`), and do not push directly to `main`. Stop after `gh pr create` and hand the PR URL to the user.
- **Explicit Authorization Only**: Merge only when the user names the PR and asks for it to be merged in that message. A prior instruction to "close the issues" or "update the board" is not merge authorization.
- **Let GitHub Close Issues**: Reference issues with `Closes #<n>` in the PR body rather than closing them manually. GitHub closes the issues and moves the project board items to Done when the PR merges.

### 6. Engineering Rules

Hard constraints for code changes. Rules 2–4 and the date gate in rule 7 are specified in sections 1, 3, and 4; they are named here so the full set of ten stays in one place.

1. **Smallest-layer-first.** Change the layer that owns the bug. A UI filter stays in the UI unless the records themselves are missing or wrong.
2. **Prove the root cause.** Follow section 3: trace the data path, inspect the records, name the failing layer, and state the evidence before editing.
3. **No unverified claims.** Follow section 3: confirm acceptance criteria against the diff or runtime behaviour. Say "fixed", "resolved", "verified", or "tested" only after that check has actually run.
4. **No production-first testing.** Follow section 1: reproduce and regression-test locally before any deploy.
5. **Preserve scope.** A request to hide, filter, or relabel matches stays in that layer. Expand into an updater rewrite, a migration, a scoring rewrite, a cache redesign, or a frontend rewrite only when the original layer cannot solve it and the evidence says so.
6. **One source of truth.** The database holds canonical fixture data. The feed cache is a performance copy. The frontend presents that data. Keep one business definition of eligibility, windows, and tiers.
7. **Upcoming means future.** A `Scheduled` status is not enough. An upcoming fixture has an allowed status and a kickoff at or after now. Scheduled feed filters use the section 4 gate `matchDateStr >= todayStr`.
8. **No stale fallback.** Choose the next fixture only from a candidate set that still contains future records. Leave a past season's earliest `Scheduled` row out of that set.
9. **Regression test user-reported bugs.** A production bug gets a regression test that reproduces the original failure, the intended fix, and one adjacent case.
10. **Honest empty states.** When the future set is empty, show that empty state. Leave fabricated, stale, and past matches out of the gap.
