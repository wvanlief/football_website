from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db, Competition
from backend.schemas.tournament import CompetitionSelectorOut

router = APIRouter(prefix="/api/competitions", tags=["Competitions"])

@router.get("", response_model=List[CompetitionSelectorOut])
def list_competitions(db: Session = Depends(get_db)):
    """
    Returns a list of all competitions and their associated tournament editions.
    """
    return db.query(Competition).options(joinedload(Competition.tournaments)).all()
