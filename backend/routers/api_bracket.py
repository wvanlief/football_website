from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.tournament import BracketResponse
from backend.services.tournament import simulate_bracket

router = APIRouter(prefix="/api/bracket", tags=["Bracket"])

@router.get("", response_model=BracketResponse)
def get_bracket(db: Session = Depends(get_db)):
    """
    Simulates the group stage and predicts the knockout tournament bracket using ELO and form.
    """
    return simulate_bracket(db)
