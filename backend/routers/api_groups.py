from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.tournament import GroupDetailsResponse, ThirdPlacedTeamStanding
from backend.services.tournament import get_group_details, get_all_third_placed_teams

router = APIRouter(prefix="/api/group", tags=["Groups"])

@router.get("/thirds", response_model=List[ThirdPlacedTeamStanding])
def get_thirds_standings(
    tournament_id: int = Query(None, description="Filter by tournament ID"),
    db: Session = Depends(get_db)
):
    """
    Returns the standings of all third-placed teams across the groups.
    """
    return get_all_third_placed_teams(db, tournament_id=tournament_id)

@router.get("/{group_letter}", response_model=GroupDetailsResponse)
def get_group(
    group_letter: str,
    tournament_id: int = Query(None, description="Filter by tournament ID"),
    tz: str = Query("UTC", description="Target timezone"),
    db: Session = Depends(get_db)
):
    """
    Returns group standings and fixtures.
    """
    # Exclude "thirds" case if it somehow leaks
    if group_letter.lower() == "thirds":
        raise HTTPException(status_code=400, detail="Use the /thirds endpoint instead")
    details = get_group_details(db, group_letter, tz, tournament_id=tournament_id)
    if not details:
        raise HTTPException(status_code=404, detail="Group not found")
    return details


