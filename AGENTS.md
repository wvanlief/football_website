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
- **Database Re-Sync**: Use `.\.venv\Scripts\python.exe -m backend.scripts.sync_production_db <DATABASE_PUBLIC_URL>` to refresh local data whenever production alignment is needed.

### 1a. Environment: Use the Project venv (Python 3.10+)
The codebase uses PEP 604 unions (`str | int`) in runtime annotations, so **Python 3.9 cannot even import `backend.main`** — it dies with `TypeError: unsupported operand type(s) for |`. On Windows the bare `python` command is often the Microsoft Store stub and `py -3` may resolve to 3.9, so always go through the project venv.

- **Never invoke bare `python` / `py -3`**: use the venv interpreter explicitly (`.venv\Scripts\python.exe` on Windows, `.venv/bin/python` on POSIX).
- **First-time setup** (`.venv/` is gitignored). Test-only dependencies are not in `requirements.txt` and must be installed alongside it:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest httpx
```

- **Verify the interpreter before diagnosing failures**: `.\.venv\Scripts\python.exe -c "import sys, fastapi; print(sys.version)"`. An import error at collection time is almost always the wrong interpreter, not a code defect.

### 1b. Verification Commands
Run both before handing work back. A green test suite alone does not prove the pages render, since the frontend is untested vanilla JS.

- **Test suite** (124 tests, ~45s; `pytest.ini` sets `testpaths=tests` and `pythonpath=.`, so run from the repo root):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

- **Smoke check** — needs the server running in a separate shell, then exits non-zero on failure:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000
.\.venv\Scripts\python.exe -m backend.scripts.smoke_check
```

`backend/scripts/smoke_check.py` covers all 6 page routes, `shared.js` delivery and its canonical exports, helper re-definition drift in page scripts, badge assets, core API endpoints, and the section 4 feed/off-season invariants. Extend it rather than writing throwaway scripts, and add cases there when a regression escapes it. Pass `--base-url` to point at another host. Exit codes: `0` pass, `1` check failed, `2` server unreachable.

### 2. Browser Testing & Token Efficiency
- **Lightweight Scripts First**: Use local Python scripts (`urllib.request`, `pytest`, Playwright) for API response times, DOM checks, and HTTP status verification.
- **Single-Shot Browser Snapshots**: Avoid multi-turn interactive browser subagent loops. When visual inspection is needed, use single-shot navigation tasks (`Navigate and take 1 snapshot`).

### 3. Empirical Diagnostic Discipline
- **Verify Before Asserting**: Never formulate hypotheses about database contents, missing schemas, or league start dates without running an explicit SQL query or inspecting server logs.
- **No Swallowed Errors**: Always inspect full stack traces before forming a diagnostic hypothesis.
- **Assert Criteria Against Source, Not Regex Alone**: When verifying issue acceptance criteria, a grep miss is not proof of a defect. Confirm intent by reading the diff (`git show <sha> -- <path>`) or executing the behaviour, since patterns like a `__new__`-based singleton or a module-level default satisfy "single instance" requirements without removing the class name.

### 4. Feed & Cache Integrity
- **Non-Empty Cache Guarantee**: Pre-calculated feed builders (`feed_builder.py`) must never emit `total_fixtures: 0` if active tournaments exist in PostgreSQL/SQLite.
- **Off-Season Gating**: Ensure scheduled fixture filters strictly gate past-dated matches (`matchDateStr >= todayStr`) to prevent legacy matches from rendering in upcoming views.

### 5. Pull Request & Merge Etiquette
- **Never Self-Merge**: Agents must not merge their own pull requests. A PR exists so a human can review the diff before it reaches `main`; merging it yourself removes the review gate and makes the PR pointless.
- **Forbidden Commands**: Do not run `gh pr merge` (including `--auto`, `--squash`, `--rebase`), and do not push directly to `main`. Stop after `gh pr create` and hand the PR URL to the user.
- **Explicit Authorization Only**: Merge only when the user names the PR and asks for it to be merged in that message. A prior instruction to "close the issues" or "update the board" is not merge authorization.
- **Let GitHub Close Issues**: Reference issues with `Closes #<n>` in the PR body rather than closing them manually. GitHub closes the issues and moves the project board items to Done when the PR merges.
