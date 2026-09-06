from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import Tournament, get_db
from backend.schemas.tournament import CombinedBracketResponse
from backend.services.simulation import simulate_bracket, run_monte_carlo_simulation, get_tournament_bracket_tree

router = APIRouter(prefix="/api/bracket", tags=["Bracket"])


def _bracket_payload(db: Session, tournament_id: Optional[int]):
    tourney = None
    if tournament_id is not None:
        tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    elif tournament_id is None:
        tourney = db.query(Tournament).filter(Tournament.status == "Active").first()
        if tourney:
            tournament_id = tourney.id

    engine = "group_knockout"
    if tourney and tourney.competition:
        engine = tourney.competition.format_engine or engine

    if engine == "group_knockout":
        return simulate_bracket(db, tournament_id=tournament_id)
    return get_tournament_bracket_tree(db, tournament_id=tournament_id)


@router.get("", response_model=CombinedBracketResponse)
def get_bracket(
    tournament_id: int = Query(None, description="Filter by tournament ID"),
    db: Session = Depends(get_db)
):
    """
    Returns bracket data for the selected tournament.
    World Cup-style group+knockout uses Monte Carlo; other engines use stored knockout fixtures.
    """
    return _bracket_payload(db, tournament_id)


@router.post("/simulate", response_model=CombinedBracketResponse)
def trigger_simulation(
    tournament_id: int = Query(None, description="Filter by tournament ID"),
    db: Session = Depends(get_db)
):
    """
    Runs a fresh Monte Carlo simulation (10,000 runs) and caches the results.
    """
    return run_monte_carlo_simulation(db, tournament_id=tournament_id)

