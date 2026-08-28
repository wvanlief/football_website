from sqlalchemy.orm import Session
from backend.database import Team, TournamentTeam

def get_team_by_name(db: Session, name: str) -> Team:
    """Returns a team by exact name match, or None if not found."""
    return db.query(Team).filter(Team.name == name).first()

def get_teams_by_group(db: Session, group_name: str, tournament_id: int = None) -> list[Team]:
    """
    Returns all teams in a specific group.
    Supports Nations League division+group format (e.g., 'A1' = division A, group 1).
    """
    from backend.database import Tournament
    is_nations_league = False
    if tournament_id is not None:
        t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if t and t.competition and t.competition.format_engine == "nations_league":
            is_nations_league = True

    if is_nations_league and group_name and len(group_name) >= 2:
        div = group_name[0]
        grp = group_name[1:]
        q = db.query(Team).join(TournamentTeam).filter(
            TournamentTeam.division == div,
            TournamentTeam.group_name == grp
        )
    else:
        q = db.query(Team).join(TournamentTeam).filter(TournamentTeam.group_name == group_name)
        
    if tournament_id is not None:
        q = q.filter(TournamentTeam.tournament_id == tournament_id)
    return q.all()

def count_teams_in_group(db: Session, group_name: str, tournament_id: int = None) -> int:
    """
    Returns the number of teams in a specific group.
    Supports Nations League division+group format (e.g., 'A1' = division A, group 1).
    """
    from backend.database import Tournament
    is_nations_league = False
    if tournament_id is not None:
        t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if t and t.competition and t.competition.format_engine == "nations_league":
            is_nations_league = True

    if is_nations_league and group_name and len(group_name) >= 2:
        div = group_name[0]
        grp = group_name[1:]
        q = db.query(Team).join(TournamentTeam).filter(
            TournamentTeam.division == div,
            TournamentTeam.group_name == grp
        )
    else:
        q = db.query(Team).join(TournamentTeam).filter(TournamentTeam.group_name == group_name)
        
    if tournament_id is not None:
        q = q.filter(TournamentTeam.tournament_id == tournament_id)
    return q.count()

def get_all_teams(db: Session, tournament_id: int = None) -> list[Team]:
    """Returns all teams, optionally filtered by tournament participation."""
    if tournament_id is not None:
        return db.query(Team).join(TournamentTeam).filter(TournamentTeam.tournament_id == tournament_id).all()
    return db.query(Team).all()
