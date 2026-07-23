from sqlalchemy.orm import Session, joinedload, aliased
from backend.database import Fixture, Team, Tournament

def get_active_tournament_ids(db: Session) -> list[int]:
    t_2026 = db.query(Tournament).filter(Tournament.status == "Active", Tournament.season_name == "2026").all()
    if t_2026:
        return [t.id for t in t_2026]
    return [t.id for t in db.query(Tournament).filter(Tournament.status == "Active").all()]

def get_all_fixtures(db: Session, tournament_id: int = None) -> list[Fixture]:
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
    return db.query(Fixture).count()

def get_recommended_fixtures(db: Session, tournament_id: int = None, min_score: float = 75.0, include_past: bool = False) -> list[Fixture]:
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
    q = db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).filter(Fixture.stage == stage)
    if tournament_id is not None:
        q = q.filter(Fixture.tournament_id == tournament_id)
    return q.all()
