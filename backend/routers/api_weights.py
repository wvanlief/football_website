from fastapi import APIRouter

router = APIRouter(tags=["Weights & Config"])

# Static configuration weights on server
scoring_weights = {
    "elo": 0.35,
    "odds": 0.25,
    "form": 0.15,
    "narrative": 0.25
}

@router.get("/api/weights")
def get_weights():
    return scoring_weights
