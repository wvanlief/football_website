# 0005. Dynamic Watchability Ranking and Relative Tiers

## Context
Watchability previously relied on brittle static cutoffs (`>= 75.0` for recommended fixtures and `70.0` for upcoming gems). Empirical analysis across 8,765 fixtures showed that scores concentrate between 35 and 65 (median 59.4, top 20% at 65.4, top 5% at 71.7), leaving 35.5% of calendar weeks with zero matches $\ge 75.0$ and producing empty recommended feeds during quiet weeks.

## Decision
We replace static cutoffs with a dual-layer relative ranking model:
1. **Intrinsic Quality (Global Percentile & Tier)**:
   - Evaluated against the season-wide distribution.
   - `Must Watch`: Global Top 5% ($\ge 72.0$) or Top 2 of active 8-day window.
   - `Recommended`: Global Top 20% ($\ge 65.0$) or Top 5 of active 8-day window.
   - `Average`: Standard fixtures.
2. **Contextual View Ranking (Time Horizons)**:
   - Rank and percentiles are computed dynamically per display horizon (e.g., `#1 Match Today` in daily views, `#1 This Week` in weekly views).
   - Intrinsic match score is separated from view-level ranking so low-scoring quiet days highlight the best available match without misleadingly inflating its global tier.
3. **Guaranteed Non-Empty Feed**:
   - `/api/fixtures/recommended` retrieves upcoming fixtures meeting `Recommended` or `Must Watch` status.
   - If fewer than 7 fixtures qualify in the active rolling window, it automatically falls back to the Top 7 highest-rated upcoming fixtures.

## Consequences
- Recommended and Hot List feeds are guaranteed non-empty throughout the calendar year.
- Frontends can present relative context (e.g., `Top 5% this week`, `#1 Today`) rather than raw ambiguous numbers.
- Consolidates and resolves GitHub Issues #60, #62, and #71 under canonical Issue #71.
