# 04 — Migrate Simulation Callers to Simulation Service

**What to build:**
Refactor the API routes in `api_bracket.py` and live updater logic in `updater.py` to import and call `SimulationService` instead of legacy functions, completely removing simulation logic from `tournament.py`.

**Blocked by:** 01 — Extract Simulation Core Engine

**Status:** ready-for-agent

- [ ] Update `api_bracket.py` routes to call the `SimulationService` methods.
- [ ] Update the live scorer and updater modules in `updater.py` to trigger simulations using the service.
- [ ] Remove deprecated simulation functions and Poisson math from `tournament.py` to restore it to a lean projection module.
- [ ] Run the complete test suite to verify integration runs smoothly.
