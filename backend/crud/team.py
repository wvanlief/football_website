from sqlalchemy.orm import Session
from backend.database import Team

def get_team_by_name(db: Session, name: str) -> Team:
    return db.query(Team).filter(Team.name == name).first()

def get_teams_by_group(db: Session, group_name: str) -> list[Team]:
    return db.query(Team).filter(Team.group_name == group_name).all()

def count_teams_in_group(db: Session, group_name: str) -> int:
    return db.query(Team).filter(Team.group_name == group_name).count()

def get_all_teams(db: Session) -> list[Team]:
    return db.query(Team).all()
