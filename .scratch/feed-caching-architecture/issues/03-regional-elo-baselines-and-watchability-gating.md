# 03 — Regional ELO Baselines & Watchability Hot List Gating

**What to build:** Configure regional ELO baselines for non-European clubs (CONMEBOL ~1600, MLS ~1500) and update watchability scoring logic in `backend/scoring.py` / `backend/services/tournament.py` to suppress regular-season non-European matches from the default global Hot List feed unless tagged as Major Derbies, late-stage knockouts, or filtered under the **Americas** region tab.

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Assign regional baseline ELOs for CONMEBOL (~1600) and MLS (~1500) teams lacking `ClubElo` ratings
- [ ] Update watchability gating logic to suppress non-European regular-season matches from global default feed
- [ ] Ensure Major Derbies (`is_major_derby == True`) and late knockouts (`Quarter-final`, `Semi-final`, `Final`) remain visible on global Hot List
- [ ] Verify selecting **Americas** region tab displays full CONMEBOL/MLS match feed
