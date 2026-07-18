from sqlalchemy.orm import Session
from backend.database import Team, TournamentTeam

def get_team_by_name(db: Session, name: str) -> Team:
    return db.query(Team).filter(Team.name == name).first()

def get_teams_by_group(db: Session, group_name: str, tournament_id: int = None) -> list[Team]:
    q = db.query(Team).join(TournamentTeam).filter(TournamentTeam.group_name == group_name)
    if tournament_id is not None:
        q = q.filter(TournamentTeam.tournament_id == tournament_id)
    return q.all()

def count_teams_in_group(db: Session, group_name: str, tournament_id: int = None) -> int:
    q = db.query(Team).join(TournamentTeam).filter(TournamentTeam.group_name == group_name)
    if tournament_id is not None:
        q = q.filter(TournamentTeam.tournament_id == tournament_id)
    return q.count()

def get_all_teams(db: Session, tournament_id: int = None) -> list[Team]:
    if tournament_id is not None:
        return db.query(Team).join(TournamentTeam).filter(TournamentTeam.tournament_id == tournament_id).all()
    return db.query(Team).all()
