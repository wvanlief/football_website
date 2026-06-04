from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.weights import WeightUpdate
from backend.services.weights import normalize_weights, recalculate_all_fixture_scores
from backend.ingestor import seed_database

router = APIRouter(tags=["Weights & Config"])

# In-memory configuration weights
scoring_weights = {
    "elo": 0.50,
    "odds": 0.30,
    "form": 0.15,
    "narrative": 0.05
}

@router.get("/api/weights")
def get_weights():
    return scoring_weights

@router.post("/api/weights")
def update_weights(weights: WeightUpdate, db: Session = Depends(get_db)):
    global scoring_weights
    raw_weights = {
        "elo": weights.elo,
        "odds": weights.odds,
        "form": weights.form,
        "narrative": weights.narrative
    }
    # Normalize weights so they sum to 1.0
    scoring_weights = normalize_weights(raw_weights)
    
    # Recalculate scores for all fixtures using the service
    recalculate_all_fixture_scores(db, scoring_weights)
    
    return {"status": "success", "weights": scoring_weights}

@router.post("/api/refresh")
def refresh_data(db: Session = Depends(get_db)):
    seed_database(db)
    # Re-apply current weights
    recalculate_all_fixture_scores(db, scoring_weights)
    return {"status": "success"}
