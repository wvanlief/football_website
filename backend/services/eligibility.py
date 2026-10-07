"""What the homepage feed and recommended list may show.

Active tournaments, the rolling date window, the off-season future gate, and
the scheduled-unstamped hide rule live here. Recommended's score threshold and
top-up fallback live here once. Callers pass the clock; production uses now.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, TypeVar

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from backend.database import Fixture, Tournament

T = TypeVar("T")

RECOMMENDED_MIN_SCORE = 65.0
RECOMMENDED_MIN_COUNT = 7


def has_provider_fixture_id(api_id) -> bool:
    return api_id is not None and str(api_id).strip() != ""


def active_tournament_ids(db: Session) -> list[int]:
    """Ids of tournaments with status Active."""
    tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
    return [t.id for t in tournaments]


def _as_naive_utc(now_utc: datetime) -> datetime:
    if now_utc.tzinfo is not None:
        return now_utc.astimezone(timezone.utc).replace(tzinfo=None)
    return now_utc


def scheduled_unstamped_clause(db: Session, target_ids: list[int]):
    """Omit scheduled draw leftovers once a tournament has at least one stamped fixture."""
    if not target_ids:
        return True
    stamped_ids = {
        tournament_id
        for tournament_id, api_id in db.query(Fixture.tournament_id, Fixture.api_id)
        .filter(Fixture.tournament_id.in_(target_ids))
        .all()
        if has_provider_fixture_id(api_id)
    }
    if not stamped_ids:
        return True
    return ~and_(
        Fixture.tournament_id.in_(stamped_ids),
        Fixture.status == "Scheduled",
        or_(Fixture.api_id.is_(None), Fixture.api_id == ""),
    )


def _target_ids(db: Session, tournament_id: Optional[int]) -> list[int]:
    if tournament_id is not None:
        return [tournament_id]
    target_ids = active_tournament_ids(db)
    if not target_ids:
        target_ids = [t.id for t in db.query(Tournament.id).all()]
    return target_ids


def eligible_fixtures(
    db: Session,
    tournament_id: Optional[int] = None,
    window_days_past: int = 14,
    window_days_future: int = 30,
    now_utc: Optional[datetime] = None,
) -> list[Fixture]:
    """Fixtures the homepage feed may show for the given clock.

    Rolling window is ``now - window_days_past`` through ``now + window_days_future``.
    When that window is empty, return only kickoffs at or after now (up to 100).
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    now_naive = _as_naive_utc(now_utc)
    window_start = now_naive - timedelta(days=window_days_past)
    window_end = now_naive + timedelta(days=window_days_future)

    target_ids = _target_ids(db, tournament_id)
    if not target_ids:
        return []

    hide_unstamped = scheduled_unstamped_clause(db, target_ids)
    fixtures = (
        db.query(Fixture)
        .options(joinedload(Fixture.home_team), joinedload(Fixture.away_team))
        .filter(
            Fixture.tournament_id.in_(target_ids),
            Fixture.date_utc >= window_start,
            Fixture.date_utc <= window_end,
            hide_unstamped,
        )
        .order_by(Fixture.date_utc.asc())
        .all()
    )
    if fixtures:
        return fixtures

    return (
        db.query(Fixture)
        .options(joinedload(Fixture.home_team), joinedload(Fixture.away_team))
        .filter(
            Fixture.tournament_id.in_(target_ids),
            Fixture.date_utc >= now_naive,
            hide_unstamped,
        )
        .order_by(Fixture.date_utc.asc())
        .limit(100)
        .all()
    )


def select_recommended(
    items: list[T],
    score_of: Callable[[T], float],
    min_score: float = RECOMMENDED_MIN_SCORE,
    min_count: int = RECOMMENDED_MIN_COUNT,
) -> list[T]:
    """Keep rows at or above ``min_score``. If that set is shorter than ``min_count``, take the top scores."""
    ranked = [item for item in items if score_of(item) >= min_score]
    if min_count > 0 and len(ranked) < min_count:
        ranked = sorted(items, key=score_of, reverse=True)[:min_count]
    ranked.sort(key=score_of, reverse=True)
    return ranked


def recommended_fixtures(
    db: Session,
    tournament_id: int = None,
    min_score: float = RECOMMENDED_MIN_SCORE,
    min_count: int = 0,
    include_past: bool = False,
    now: Optional[datetime] = None,
) -> list[Fixture]:
    """Upcoming fixtures for the recommended list, using ``select_recommended``."""
    base_q = db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team),
        joinedload(Fixture.tournament).joinedload(Tournament.competition),
        joinedload(Fixture.odds_history),
    )

    if not include_past and os.getenv("TESTING") != "True":
        now_utc = now or datetime.now(timezone.utc)
        base_q = base_q.filter(Fixture.date_utc >= _as_naive_utc(now_utc))

    target_ids = _target_ids(db, tournament_id)
    if not target_ids:
        return []
    base_q = base_q.filter(Fixture.tournament_id.in_(target_ids))
    base_q = base_q.filter(scheduled_unstamped_clause(db, target_ids))

    candidates = base_q.filter(Fixture.watchability_score.isnot(None)).all()
    return select_recommended(
        candidates,
        lambda row: row.watchability_score or 0,
        min_score=min_score,
        min_count=min_count,
    )
