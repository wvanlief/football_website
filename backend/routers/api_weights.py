from fastapi import APIRouter

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
