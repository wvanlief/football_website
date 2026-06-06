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
    Returns a list of all countries in the tournament.
    """
    teams = db.query(Team).all()
    tts = db.query(TournamentTeam).all()
    team_group_map = {tt.team_id: tt.group_name for tt in tts}
    
    # Sort alphabetically by team name
    sorted_teams = sorted(teams, key=lambda t: t.name)
    
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
