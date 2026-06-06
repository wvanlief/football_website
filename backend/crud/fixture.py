from sqlalchemy.orm import Session, joinedload, aliased
from backend.database import Fixture, Team

def get_all_fixtures(db: Session) -> list[Fixture]:
    return db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).all()

def count_fixtures(db: Session) -> int:
    return db.query(Fixture).count()

def get_recommended_fixtures(db: Session, min_score: float = 75.0) -> list[Fixture]:
    return db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).filter(Fixture.watchability_score >= min_score).all()

def get_finished_group_stage_fixtures_for_teams(db: Session, team_names: list[str]) -> list[Fixture]:
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    return db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).join(HomeTeam, Fixture.home_team_id == HomeTeam.id).join(AwayTeam, Fixture.away_team_id == AwayTeam.id).filter(
        (Fixture.stage == "Group Stage") &
        (Fixture.status == "Finished") &
        (HomeTeam.name.in_(team_names)) &
        (AwayTeam.name.in_(team_names))
    ).all()

def get_finished_fixtures_for_country(db: Session, country_name: str) -> list[Fixture]:
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    return db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).join(HomeTeam, Fixture.home_team_id == HomeTeam.id).join(AwayTeam, Fixture.away_team_id == AwayTeam.id).filter(
        (Fixture.status == "Finished") & 
        ((HomeTeam.name == country_name) | (AwayTeam.name == country_name))
    ).all()

def get_future_fixtures_for_country(db: Session, country_name: str) -> list[Fixture]:
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    return db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).join(HomeTeam, Fixture.home_team_id == HomeTeam.id).join(AwayTeam, Fixture.away_team_id == AwayTeam.id).filter(
        (Fixture.status != "Finished") & 
        ((HomeTeam.name == country_name) | (AwayTeam.name == country_name))
    ).all()

def get_fixtures_for_group(db: Session, team_names: list[str]) -> list[Fixture]:
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    return db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).join(HomeTeam, Fixture.home_team_id == HomeTeam.id).join(AwayTeam, Fixture.away_team_id == AwayTeam.id).filter(
        (HomeTeam.name.in_(team_names)) & (AwayTeam.name.in_(team_names))
    ).all()

def get_fixtures_by_stage(db: Session, stage: str) -> list[Fixture]:
    return db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).filter(Fixture.stage == stage).all()
