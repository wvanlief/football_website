from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.fixture import GroupedFixturesResponse, FixtureOut, CalendarFixtureOut
from backend.services.tournament import (
    get_grouped_fixtures,
    get_recommended_fixtures,
    get_calendar_fixtures,
    get_fixture_details_by_id,
)

router = APIRouter(prefix="/api/fixtures", tags=["Fixtures"])

@router.get("", response_model=GroupedFixturesResponse)
def get_fixtures(tz: str = Query("UTC", description="Target timezone"), db: Session = Depends(get_db)):
    """
    Returns fixtures grouped by Today, Tomorrow, and This Week. Today and Tomorrow are sorted by ascending time, while This Week is sorted by watchability.
    """
    return get_grouped_fixtures(db, tz)

@router.get("/recommended", response_model=List[FixtureOut])
def get_recommended(tz: str = Query("UTC", description="Target timezone"), db: Session = Depends(get_db)):
    """
    Returns fixtures with watchability score >= 75%.
    """
    return get_recommended_fixtures(db, tz)

@router.get("/calendar", response_model=List[CalendarFixtureOut])
def get_calendar(tz: str = Query("UTC", description="Target timezone"), db: Session = Depends(get_db)):
    """
    Returns minimal fixture info for the calendar page (last 7 days and upcoming 30 days).
    """
    return get_calendar_fixtures(db, tz)

@router.get("/{fixture_id}", response_model=FixtureOut)
def get_fixture_detail(fixture_id: int, tz: str = Query("UTC", description="Target timezone"), db: Session = Depends(get_db)):
    """
    Returns full details for a single fixture.
    """
    fixture_data = get_fixture_details_by_id(db, fixture_id, tz)
    if not fixture_data:
        raise HTTPException(status_code=404, detail="Fixture not found")
    return fixture_data

