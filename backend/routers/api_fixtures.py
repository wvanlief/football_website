from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.fixture import GroupedFixturesResponse, FixtureOut
from backend.services.tournament import get_grouped_fixtures, get_recommended_fixtures

router = APIRouter(prefix="/api/fixtures", tags=["Fixtures"])

@router.get("", response_model=GroupedFixturesResponse)
def get_fixtures(tz: str = Query("UTC", description="Target timezone"), db: Session = Depends(get_db)):
    """
    Returns fixtures grouped by Today, Tomorrow, and This Week, sorted by watchability.
    """
    return get_grouped_fixtures(db, tz)

@router.get("/recommended", response_model=List[FixtureOut])
def get_recommended(tz: str = Query("UTC", description="Target timezone"), db: Session = Depends(get_db)):
    """
    Returns fixtures with watchability score >= 75%.
    """
    return get_recommended_fixtures(db, tz)
