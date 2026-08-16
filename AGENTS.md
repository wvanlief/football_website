# Agent Configuration

Welcome! This file documents the conventions and configurations that AI coding agents should follow when working in this repository.

## Agent skills

### Issue tracker

Issues are tracked using GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Using default canonical triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repository layout. See `docs/agents/domain.md`.

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
