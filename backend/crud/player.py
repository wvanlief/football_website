from sqlalchemy.orm import Session
from backend.database import Player, PlayerContract, Team

def get_players_by_team(db: Session, team_name: str, contract_type: str = "Country") -> list[Player]:
    return db.query(Player).join(PlayerContract).join(Team).filter(
        (Team.name == team_name) & 
        (PlayerContract.type == contract_type) & 
        (PlayerContract.is_active == True)
    ).all()

def get_top_players_by_team(db: Session, team_name: str, contract_type: str = "Country", limit: int = 3) -> list[Player]:
    return db.query(Player).join(PlayerContract).join(Team).filter(
        (Team.name == team_name) & 
        (PlayerContract.type == contract_type) & 
        (PlayerContract.is_active == True)
    ).order_by(Player.form_score.desc()).limit(limit).all()
