"""Season-overlay fixture identity.

Seeding and engine overlays ask this module whether an incoming provider match
is an existing fixture, then stamp that row. Matching does not delete rows and
does not change home or away.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.database import Fixture, Tournament


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def find_existing_fixture(
    db: Session,
    tournament: Optional[Tournament],
    api_id: Optional[str],
    home_team: Optional[Any],
    away_team: Optional[Any],
    date_utc: datetime,
    stage: Optional[str],
) -> Optional[Fixture]:
    """Match by provider id, then a unique home/away row, then stage, then kickoff window."""
    if not tournament:
        return None

    if api_id:
        fixture = db.query(Fixture).filter(
            Fixture.tournament_id == tournament.id,
            Fixture.api_id == api_id,
        ).first()
        if fixture:
            return fixture

    if not home_team or not away_team:
        return None

    pairing = db.query(Fixture).filter(
        Fixture.tournament_id == tournament.id,
        Fixture.home_team_id == home_team.id,
        Fixture.away_team_id == away_team.id,
    ).all()

    # One pairing in this tournament is the official row, even when the
    # provider match id changed or another source already stamped it.
    # Multiple legs stay on ±12h after dropping other same-provider stamps.
    if len(pairing) == 1:
        return pairing[0]

    provider_prefix = api_id.split("_", 1)[0] + "_" if api_id and "_" in api_id else None
    if provider_prefix:
        pairing = [
            candidate for candidate in pairing
            if not (candidate.api_id and candidate.api_id != api_id
                    and str(candidate.api_id).startswith(provider_prefix))
        ]

    if len(pairing) == 1:
        return pairing[0]

    if stage:
        staged = [candidate for candidate in pairing if candidate.stage == stage]
        if len(staged) == 1:
            return staged[0]

    provider_stamp = bool(api_id) and str(api_id).startswith(("fd_", "of_", "tsdb_", "fa_", "hl_"))

    kickoff = _as_utc(date_utc)
    if kickoff is None:
        return None
    window_start = kickoff - timedelta(hours=12)
    window_end = kickoff + timedelta(hours=12)
    for candidate in pairing:
        cand_dt = _as_utc(candidate.date_utc)
        if cand_dt is None:
            continue
        if not (window_start <= cand_dt <= window_end):
            continue
        if not provider_stamp and stage and candidate.stage != stage:
            continue
        return candidate
    return None


def stamp_fixture(fixture: Fixture, api_id: Optional[str]) -> None:
    """Record a provider id on an existing row. Does not change home or away."""
    if api_id:
        fixture.api_id = api_id
