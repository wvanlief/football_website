from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.ingestor import seed_database

router = APIRouter(tags=["Weights & Config"])

# Static configuration weights on server
scoring_weights = {
    "elo": 0.50,
    "odds": 0.30,
    "form": 0.15,
    "narrative": 0.05
}

@router.get("/api/weights")
def get_weights():
    return scoring_weights

@router.post("/api/refresh")
def refresh_data(db: Session = Depends(get_db)):
    seed_database(db)
    return {"status": "success"}
