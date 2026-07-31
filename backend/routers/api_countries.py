from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import backend.crud.team as crud_team
from backend.database import get_db, Team, TournamentTeam
from backend.schemas.tournament import CountryDetailsResponse, CountrySimpleOut
from backend.services.tournament import get_country_details

router = APIRouter(prefix="/api/country", tags=["Countries"])

@router.get("", response_model=List[CountrySimpleOut])
def get_all_countries(
    tournament_id: int = Query(None, description="Filter by tournament ID"),
    db: Session = Depends(get_db)
):
    """
    Returns a list of all countries/teams, sorted by next upcoming match.
    """
    from datetime import datetime, timedelta
    from backend.database import Fixture, Tournament, Competition
    
    active_tournaments = db.query(Tournament).filter(Tournament.status == "Active").all()
    active_ids = [t.id for t in active_tournaments]
    
    if tournament_id is not None:
        teams = crud_team.get_all_teams(db, tournament_id=tournament_id)
    else:
        teams = db.query(Team).join(TournamentTeam).filter(TournamentTeam.tournament_id.in_(active_ids)).all()
        
    tts_query = db.query(TournamentTeam)
    if tournament_id is not None:
        tts_query = tts_query.filter(TournamentTeam.tournament_id == tournament_id)
    else:
        tts_query = tts_query.filter(TournamentTeam.tournament_id.in_(active_ids))
    tts = tts_query.all()
    
    team_group_map = {tt.team_id: tt.group_name for tt in tts}
    
    tourney_map = {t.id: t for t in db.query(Tournament).all()}
    comp_map = {c.id: c for c in db.query(Competition).all()}
    
    team_tourney_map = {}
    for tt in tts:
        tourney = tourney_map.get(tt.tournament_id)
        if tourney:
            comp = comp_map.get(tourney.competition_id)
            team_tourney_map[tt.team_id] = {
                "tournament_id": tourney.id,
                "competition_name": comp.name if comp else None,
                "competition_badge": comp.badge if comp else "⚽"
            }
    
    # Get all scheduled/live fixtures ordered by date
    fixtures_query = db.query(Fixture).filter(Fixture.status != "Finished")
    if tournament_id is not None:
        fixtures_query = fixtures_query.filter(Fixture.tournament_id == tournament_id)
    else:
        fixtures_query = fixtures_query.filter(Fixture.tournament_id.in_(active_ids))
    upcoming_fixtures = fixtures_query.order_by(Fixture.date_utc.asc()).all()
    
    # Map team_id to next match: (date_utc, fixture_id, home_or_away_flag)
    next_match_info = {}
    for f in upcoming_fixtures:
        if f.home_team_id is not None and f.home_team_id not in next_match_info:
            next_match_info[f.home_team_id] = (f.date_utc, f.id, 0)
        if f.away_team_id is not None and f.away_team_id not in next_match_info:
            next_match_info[f.away_team_id] = (f.date_utc, f.id, 1)
            
    # Sort:
    # 1. Teams with upcoming matches sorted chronologically
    # 2. Group home & away teams together (home first)
    # 3. Eliminated/finished teams at the end sorted alphabetically
    sorted_teams = sorted(
        teams,
        key=lambda t: (next_match_info.get(t.id, (datetime.max, 999999, 0)), t.name)
    )
    
    now_naive = datetime.utcnow()
    one_week_later_naive = now_naive + timedelta(days=7)
    
    result = []
    for t in sorted_teams:
        match_info = next_match_info.get(t.id)
        next_date = None
        has_upcoming = False
        if match_info:
            dt = match_info[0]
            next_date = dt.isoformat()
            has_upcoming = (now_naive <= dt <= one_week_later_naive)
            
        t_info = team_tourney_map.get(t.id, {})
        
        result.append(
            CountrySimpleOut(
                name=t.name,
                elo=t.elo,
                logo_url=t.badge_url,
                group_name=team_group_map.get(t.id),
                competition_name=t_info.get("competition_name"),
                competition_badge=t_info.get("competition_badge"),
                tournament_id=t_info.get("tournament_id"),
                next_match_date=next_date,
                has_upcoming_game=has_upcoming
            )
        )
    return result

@router.get("/{country_name}", response_model=CountryDetailsResponse)
def get_country(
    country_name: str,
    tournament_id: int = Query(None, description="Filter by tournament ID"),
    tz: str = Query("UTC", description="Target timezone"),
    db: Session = Depends(get_db)
):
    """
    Returns country profile, ELO, top players, form results, and future fixtures.
    """
    details = get_country_details(db, country_name, tz, tournament_id=tournament_id)
    if not details:
        raise HTTPException(status_code=404, detail="Country not found")
    return details

