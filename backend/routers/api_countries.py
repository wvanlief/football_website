from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db, Team, TournamentTeam
from backend.schemas.tournament import CountryDetailsResponse, CountrySimpleOut
from backend.services.tournament import get_country_details

router = APIRouter(prefix="/api/country", tags=["Countries"])

@router.get("", response_model=List[CountrySimpleOut])
def get_all_countries(db: Session = Depends(get_db)):
    """
    Returns a list of all countries in the tournament, sorted by next upcoming match.
    """
    from datetime import datetime
    from backend.database import Fixture
    
    teams = db.query(Team).all()
    tts = db.query(TournamentTeam).all()
    team_group_map = {tt.team_id: tt.group_name for tt in tts}
    
    # Get all scheduled/live fixtures ordered by date
    upcoming_fixtures = (
        db.query(Fixture)
        .filter(Fixture.status != "Finished")
        .order_by(Fixture.date_utc.asc())
        .all()
    )
    
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
    
    return [
        CountrySimpleOut(
            name=t.name,
            elo=t.elo,
            group_name=team_group_map.get(t.id)
        )
        for t in sorted_teams
    ]

@router.get("/{country_name}", response_model=CountryDetailsResponse)
def get_country(country_name: str, tz: str = Query("UTC", description="Target timezone"), db: Session = Depends(get_db)):
    """
    Returns country profile, ELO, top players, form results, and future fixtures.
    """
    details = get_country_details(db, country_name, tz)
    if not details:
        raise HTTPException(status_code=404, detail="Country not found")
    return details
