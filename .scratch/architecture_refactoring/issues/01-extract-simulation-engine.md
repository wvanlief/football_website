# 01 — Extract Simulation Core Engine

**What to build:**
A consolidated, database-isolated `SimulationService` (in `backend/services/simulation.py`) that encapsulates all mathematical Poisson goal generation and Monte Carlo simulation algorithms. This decouples the simulation logic from the database query projections inside `tournament.py`.

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Move Poisson goal calculation (`poisson_random`), group stage simulation (`simulate_group_stage`), bracket simulation (`simulate_bracket`), and Monte Carlo loops (`run_monte_carlo_simulation`) from `tournament.py` to `simulation.py`.
- [ ] Expose a clean, programmatic service interface from `SimulationService` with `run_simulation` and `get_probabilities` methods.
- [ ] Add unit tests verifying simulation outcomes directly through the service interface.
