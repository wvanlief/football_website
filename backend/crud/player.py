from sqlalchemy.orm import Session
from backend.database import Player

def get_players_by_team(db: Session, team_name: str) -> list[Player]:
    return db.query(Player).filter(Player.team_name == team_name).all()

def get_top_players_by_team(db: Session, team_name: str, limit: int = 3) -> list[Player]:
    return db.query(Player).filter(Player.team_name == team_name).order_by(Player.form_score.desc()).limit(limit).all()
