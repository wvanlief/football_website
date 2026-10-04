from typing import Optional
from sqlalchemy.orm import Session, joinedload, aliased
from backend.database import Fixture, Team, Tournament
from backend.services.eligibility import (
    active_tournament_ids,
    eligible_fixtures,
    recommended_fixtures,
)


def get_active_tournament_ids(db: Session) -> list[int]:
    """Returns a list of IDs for all tournaments with status 'Active'."""
    return active_tournament_ids(db)


def get_eligible_fixtures(
    db: Session,
    tournament_id: Optional[int] = None,
    window_days_past: int = 14,
    window_days_future: int = 30,
    now_utc=None,
) -> list[Fixture]:
    """Eligible fixtures for the homepage feed. Rules live in ``eligibility``."""
    return eligible_fixtures(
        db,
        tournament_id=tournament_id,
        window_days_past=window_days_past,
        window_days_future=window_days_future,
        now_utc=now_utc,
    )

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
    include_past: bool = False,
    now=None,
) -> list[Fixture]:
    """Recommended fixtures. Threshold and fallback live in ``eligibility``."""
    return recommended_fixtures(
        db,
        tournament_id=tournament_id,
        min_score=min_score,
        min_count=min_count,
        include_past=include_past,
        now=now,
    )

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

def get_fixtures_for_group(db: Session, team_names: list[str], tournament_id: int = None, stage: str = None) -> list[Fixture]:
    """Returns fixtures where both teams are in the provided list, optionally limited to one stage."""
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
    if stage is not None:
        q = q.filter(Fixture.stage == stage)
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
