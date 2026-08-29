# 07 — Obsolete Module Cleanup & CLI Extraction

**What to build:** Delete `ingestor.py` and `seed_phase8.py`. Extract CLI arguments to `backend/cli.py` and update imports across `main.py` and `api_admin.py`.

**Blocked by:** 06 — Format Adapter Refactoring & Dependency Injection

**Status:** completed

- [x] Remove `backend/ingestor.py`
- [x] Remove `backend/seed_phase8.py`
- [x] Create `backend/cli.py` for administrative CLI scripts
- [x] Update imports in `main.py`, `api_admin.py`, and test files
- [x] Run complete test suite (`pytest tests/`) to ensure green build
