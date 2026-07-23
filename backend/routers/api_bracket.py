from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.tournament import CombinedBracketResponse
from backend.services.simulation import simulate_bracket, run_monte_carlo_simulation, get_tournament_bracket_tree

router = APIRouter(prefix="/api/bracket", tags=["Bracket"])

@router.get("", response_model=CombinedBracketResponse)
def get_bracket(
    tournament_id: int = Query(None, description="Filter by tournament ID"),
    db: Session = Depends(get_db)
):
    """
    Returns bracket data. For non-World Cup tournaments, returns dynamic knockout tree fixtures.
    """
    if tournament_id is not None and tournament_id != 1:
        return get_tournament_bracket_tree(db, tournament_id=tournament_id)
    return simulate_bracket(db, tournament_id=tournament_id)

@router.post("/simulate", response_model=CombinedBracketResponse)
def trigger_simulation(
    tournament_id: int = Query(None, description="Filter by tournament ID"),
    db: Session = Depends(get_db)
):
    """
    Runs a fresh Monte Carlo simulation (10,000 runs) and caches the results.
    """
    return run_monte_carlo_simulation(db, tournament_id=tournament_id)

