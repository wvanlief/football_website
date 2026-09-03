"""Atomic fixture lifecycle domain service.

``finish_fixture`` is the single authoritative entry point for marking a match
as complete.  It executes the three mandatory post-match steps in one call:

1. **Settlement** — sets final scores, status, winner, and team win/draw/loss
   streaks via ``settling.settle_result``.
2. **Watchability** — recalculates the watchability score and percentile for
   the fixture via ``scoring.update_fixture_score``.
3. **Standings** — updates the tournament standings cache for the fixture's
   tournament via ``standings.recalculate_tournament_team_standings``.

The session is *flushed* after each step so that later steps see consistent
state, but the caller remains responsible for the final ``db.commit()``.  This
lets callers batch multiple ``finish_fixture`` calls before committing.

All other code that previously called ``settle_result`` + ``update_fixture_score``
directly must be migrated to call ``finish_fixture`` instead, so that the three
steps can never be accidentally split.  The one exception is
``fixture_upserter.py``, which runs inside the ingestion pipeline and calls
``finish_fixture`` with ``update_standings=False`` because standings are
recalculated globally after the entire batch completes.
"""

from sqlalchemy.orm import Session

from backend.database import Fixture
from backend.scoring import update_fixture_score
from backend.services.settling import settle_result
from backend.services.standings import recalculate_tournament_team_standings


def finish_fixture(
    fixture: Fixture,
    home_score: int | None,
    away_score: int | None,
    db: Session,
    *,
    update_standings: bool = True,
) -> None:
    """Mark a fixture as finished and update all derived state atomically.

    Parameters
    ----------
    fixture:
        The ORM ``Fixture`` instance to settle.  Must have ``home_team`` and
        ``away_team`` relationships loaded (or loadable) by the session.
    home_score:
        Final goals scored by the home team.  ``None`` is accepted for edge
        cases where the score feed is incomplete; streaks are not updated in
        that case (same behaviour as ``settle_result``).
    away_score:
        Final goals scored by the away team.
    db:
        Active SQLAlchemy session.  The caller commits.
    update_standings:
        When ``False``, the standings-cache recalculation is skipped.  Use
        this inside batch ingestion pipelines that recalculate standings once
        after the whole batch.
    """
    # Step 1 — settlement (scores, status, winner, team streaks)
    settle_result(fixture, home_score, away_score)
    db.flush()

    # Step 2 — watchability score
    update_fixture_score(fixture, db)
    db.flush()

    # Step 3 — standings cache
    if update_standings and fixture.tournament_id is not None:
        recalculate_tournament_team_standings(db, fixture.tournament_id)
        db.flush()
