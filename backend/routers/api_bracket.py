from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.tournament import CombinedBracketResponse
from backend.services.tournament import simulate_bracket, run_monte_carlo_simulation

router = APIRouter(prefix="/api/bracket", tags=["Bracket"])

@router.get("", response_model=CombinedBracketResponse)
def get_bracket(db: Session = Depends(get_db)):
    """
    Simulates the tournament and returns the cached bracket and win probabilities.
    """
    return simulate_bracket(db)

@router.post("/simulate", response_model=CombinedBracketResponse)
def trigger_simulation(db: Session = Depends(get_db)):
    """
    Runs a fresh Monte Carlo simulation (10,000 runs) and caches the results.
    """
    return run_monte_carlo_simulation(db)
