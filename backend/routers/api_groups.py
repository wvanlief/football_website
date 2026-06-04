from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.tournament import GroupDetailsResponse
from backend.services.tournament import get_group_details

router = APIRouter(prefix="/api/group", tags=["Groups"])

@router.get("/{group_letter}", response_model=GroupDetailsResponse)
def get_group(group_letter: str, tz: str = Query("UTC", description="Target timezone"), db: Session = Depends(get_db)):
    """
    Returns group standings and fixtures.
    """
    details = get_group_details(db, group_letter, tz)
    if not details:
        raise HTTPException(status_code=404, detail="Group not found")
    return details
