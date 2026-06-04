from sqlalchemy.orm import Session
from backend.database import Fixture

def get_all_fixtures(db: Session) -> list[Fixture]:
    return db.query(Fixture).all()

def count_fixtures(db: Session) -> int:
    return db.query(Fixture).count()

def get_recommended_fixtures(db: Session, min_score: float = 75.0) -> list[Fixture]:
    return db.query(Fixture).filter(Fixture.watchability_score >= min_score).all()

def get_finished_group_stage_fixtures_for_teams(db: Session, team_names: list[str]) -> list[Fixture]:
    return db.query(Fixture).filter(
        (Fixture.stage == "Group Stage") &
        (Fixture.status == "Finished") &
        (Fixture.home_team_name.in_(team_names)) &
        (Fixture.away_team_name.in_(team_names))
    ).all()

def get_finished_fixtures_for_country(db: Session, country_name: str) -> list[Fixture]:
    return db.query(Fixture).filter(
        (Fixture.status == "Finished") & 
        ((Fixture.home_team_name == country_name) | (Fixture.away_team_name == country_name))
    ).all()

def get_future_fixtures_for_country(db: Session, country_name: str) -> list[Fixture]:
    return db.query(Fixture).filter(
        (Fixture.status != "Finished") & 
        ((Fixture.home_team_name == country_name) | (Fixture.away_team_name == country_name))
    ).all()

def get_fixtures_for_group(db: Session, team_names: list[str]) -> list[Fixture]:
    return db.query(Fixture).filter(
        (Fixture.home_team_name.in_(team_names)) & (Fixture.away_team_name.in_(team_names))
    ).all()

def get_fixtures_by_stage(db: Session, stage: str) -> list[Fixture]:
    return db.query(Fixture).filter(Fixture.stage == stage).all()
