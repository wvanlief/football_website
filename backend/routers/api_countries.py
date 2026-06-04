from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.tournament import CountryDetailsResponse
from backend.services.tournament import get_country_details

router = APIRouter(prefix="/api/country", tags=["Countries"])

@router.get("/{country_name}", response_model=CountryDetailsResponse)
def get_country(country_name: str, tz: str = Query("UTC", description="Target timezone"), db: Session = Depends(get_db)):
    """
    Returns country profile, ELO, top players, form results, and future fixtures.
    """
    details = get_country_details(db, country_name, tz)
    if not details:
        raise HTTPException(status_code=404, detail="Country not found")
    return details
