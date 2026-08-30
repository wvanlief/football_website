from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session, joinedload, aliased
from backend.database import Fixture, Team, Tournament

def get_active_tournament_ids(db: Session) -> list[int]:
    """Returns a list of IDs for all tournaments with status 'Active'."""
    tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
    return [t.id for t in tournaments]

def get_eligible_fixtures(
    db: Session,
    tournament_id: Optional[int] = None,
    window_days_past: int = 14,
    window_days_future: int = 30,
    now_utc: Optional[datetime] = None
) -> list[Fixture]:
    """
    Returns eligible fixtures for active tournaments (or a specific tournament)
    within a rolling window (-window_days_past to +window_days_future).
    
    If no fixtures exist within the rolling window (off-season), performs a
    strictly future-gated fallback query (date_utc >= now_utc) up to 100 fixtures.
    Legacy past fixtures are NEVER returned in off-season fallback.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    if now_utc.tzinfo is not None:
        now_naive = now_utc.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        now_naive = now_utc

    window_start = now_naive - timedelta(days=window_days_past)
    window_end = now_naive + timedelta(days=window_days_future)

    if tournament_id is not None:
        target_ids = [tournament_id]
    else:
        target_ids = get_active_tournament_ids(db)
        if not target_ids:
            target_ids = [t.id for t in db.query(Tournament.id).all()]

    if not target_ids:
        return []

    # 1. Rolling window query
    fixtures = (
        db.query(Fixture)
        .options(joinedload(Fixture.home_team), joinedload(Fixture.away_team))
        .filter(
            Fixture.tournament_id.in_(target_ids),
            Fixture.date_utc >= window_start,
            Fixture.date_utc <= window_end
        )
        .order_by(Fixture.date_utc.asc())
        .all()
    )

    # 2. Strictly future-gated fallback if off-season (no fixtures in rolling window)
    if not fixtures:
        fixtures = (
            db.query(Fixture)
            .options(joinedload(Fixture.home_team), joinedload(Fixture.away_team))
            .filter(
                Fixture.tournament_id.in_(target_ids),
                Fixture.date_utc >= now_naive
            )
            .order_by(Fixture.date_utc.asc())
            .limit(100)
            .all()
        )

    return fixtures

def get_all_fixtures(db: Session, tournament_id: int = None) -> list[Fixture]:
    """
    Returns all fixtures for a tournament or all active tournaments if tournament_id is None.
    Eagerly loads home and away teams.
    """
    q = db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    )
    if tournament_id is not None:
        q = q.filter(Fixture.tournament_id == tournament_id)
    else:
        active_ids = get_active_tournament_ids(db)
        q = q.filter(Fixture.tournament_id.in_(active_ids))
    return q.all()

def count_fixtures(db: Session) -> int:
    """Returns the total count of all fixtures in the database."""
    return db.query(Fixture).count()

def get_recommended_fixtures(
    db: Session,
    tournament_id: int = None,
    min_score: float = 65.0,
    min_count: int = 0,
    include_past: bool = False
) -> list[Fixture]:
    """
    Returns fixtures with watchability scores in the Recommended+ tier (>= 65.0).
    Filters to future fixtures only unless include_past=True or in testing mode.
    If min_count > 0 and fewer than min_count fixtures meet the threshold,
    falls back to the top min_count highest-rated upcoming fixtures.
    """
    import os
    from datetime import datetime, timezone
    
    base_q = db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team),
        joinedload(Fixture.tournament).joinedload(Tournament.competition),
        joinedload(Fixture.odds_history)
    )
    
    if not include_past and os.getenv("TESTING") != "True":
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        base_q = base_q.filter(Fixture.date_utc >= now_utc)

    if tournament_id is not None:
        base_q = base_q.filter(Fixture.tournament_id == tournament_id)
    else:
        active_ids = get_active_tournament_ids(db)
        if not active_ids:
            active_ids = [t.id for t in db.query(Tournament.id).all()]
        if active_ids:
            base_q = base_q.filter(Fixture.tournament_id.in_(active_ids))
        else:
            return []

    # 1. Query fixtures meeting the Recommended threshold (>= 65.0 / Top 20%)
    fixtures = (
        base_q.filter(Fixture.watchability_score >= min_score)
        .order_by(Fixture.watchability_score.desc())
        .all()
    )

    # 2. Quiet-week fallback: If min_count > 0 and fewer than min_count matches qualify, fetch top min_count matches
    if min_count > 0 and len(fixtures) < min_count:
        fallback_fixtures = (
            base_q.filter(Fixture.watchability_score.isnot(None))
            .order_by(Fixture.watchability_score.desc())
            .limit(min_count)
            .all()
        )
        # Combine unique fixtures maintaining highest score order
        seen_ids = {f.id for f in fixtures}
        for f in fallback_fixtures:
            if f.id not in seen_ids:
                fixtures.append(f)
                seen_ids.add(f.id)
        fixtures.sort(key=lambda x: x.watchability_score or 0, reverse=True)

    return fixtures

def get_finished_group_stage_fixtures_for_teams(db: Session, team_names: list[str], tournament_id: int = None, stage: str = "Group Stage") -> list[Fixture]:
    """Returns finished fixtures for a specific stage where both teams are in the provided team list."""
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    q = db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).join(HomeTeam, Fixture.home_team_id == HomeTeam.id).join(AwayTeam, Fixture.away_team_id == AwayTeam.id).filter(
        (Fixture.stage == stage) &
        (Fixture.status == "Finished") &
        (HomeTeam.name.in_(team_names)) &
        (AwayTeam.name.in_(team_names))
    )
    if tournament_id is not None:
        q = q.filter(Fixture.tournament_id == tournament_id)
    return q.all()

def get_finished_fixtures_for_country(db: Session, country_name: str, tournament_id: int = None) -> list[Fixture]:
    """Returns all finished fixtures involving a specific team/country."""
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    q = db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).join(HomeTeam, Fixture.home_team_id == HomeTeam.id).join(AwayTeam, Fixture.away_team_id == AwayTeam.id).filter(
        (Fixture.status == "Finished") & 
        ((HomeTeam.name == country_name) | (AwayTeam.name == country_name))
    )
    if tournament_id is not None:
        q = q.filter(Fixture.tournament_id == tournament_id)
    return q.all()

def get_future_fixtures_for_country(db: Session, country_name: str, tournament_id: int = None) -> list[Fixture]:
    """Returns all upcoming (non-finished) fixtures involving a specific team/country."""
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    q = db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).join(HomeTeam, Fixture.home_team_id == HomeTeam.id).join(AwayTeam, Fixture.away_team_id == AwayTeam.id).filter(
        (Fixture.status != "Finished") & 
        ((HomeTeam.name == country_name) | (AwayTeam.name == country_name))
    )
    if tournament_id is not None:
        q = q.filter(Fixture.tournament_id == tournament_id)
    return q.all()

def get_fixtures_for_group(db: Session, team_names: list[str], tournament_id: int = None) -> list[Fixture]:
    """Returns all fixtures (any status) where both teams are in the provided team list."""
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    q = db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).join(HomeTeam, Fixture.home_team_id == HomeTeam.id).join(AwayTeam, Fixture.away_team_id == AwayTeam.id).filter(
        (HomeTeam.name.in_(team_names)) & (AwayTeam.name.in_(team_names))
    )
    if tournament_id is not None:
        q = q.filter(Fixture.tournament_id == tournament_id)
    return q.all()

def get_fixtures_by_stage(db: Session, stage: str, tournament_id: int = None) -> list[Fixture]:
    """Returns all fixtures for a specific tournament stage (e.g., 'Group Stage', 'Round of 16')."""
    q = db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).filter(Fixture.stage == stage)
    if tournament_id is not None:
        q = q.filter(Fixture.tournament_id == tournament_id)
    return q.all()
