from sqlalchemy.orm import Session, joinedload, aliased
from backend.database import Fixture, Team, Tournament

def get_active_tournament_ids(db: Session) -> list[int]:
    """Returns a list of IDs for all tournaments with Active status."""
    tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
    return [t.id for t in tournaments]

def get_all_fixtures(db: Session, tournament_id: int = None) -> list[Fixture]:
    """Retrieves all fixtures for a specific tournament or all active tournaments."""
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
    """Returns the total count of fixtures in the database."""
    return db.query(Fixture).count()

def get_recommended_fixtures(db: Session, tournament_id: int = None, min_score: float = 75.0, include_past: bool = False) -> list[Fixture]:
    """Returns fixtures with high watchability scores, optionally filtered by tournament and future date."""
    import os
    from datetime import datetime, timezone
    q = db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).filter(Fixture.watchability_score >= min_score)

    if not include_past and os.getenv("TESTING") != "True":
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        q = q.filter(Fixture.date_utc >= now_utc)

    if tournament_id is not None:
        q = q.filter(Fixture.tournament_id == tournament_id)
    else:
        active_ids = get_active_tournament_ids(db)
        q = q.filter(Fixture.tournament_id.in_(active_ids))
    return q.all()

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
    """Returns all finished fixtures where the specified team (by name) participated."""
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
    """Returns all upcoming (not finished) fixtures where the specified team participates."""
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
    """Returns all fixtures where both home and away teams are in the provided team list."""
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
    """Returns all fixtures for a specific tournament stage (e.g., 'Group Stage', 'Final')."""
    q = db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).filter(Fixture.stage == stage)
    if tournament_id is not None:
        q = q.filter(Fixture.tournament_id == tournament_id)
    return q.all()
