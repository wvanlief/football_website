import os
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.updater import update_results_and_odds

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# Token retrieved from environment variables, defaulting to dev-admin-token for local runs
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dev-admin-token")

def verify_admin_token(x_admin_token: str = Header(None, alias="X-Admin-Token")):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token."
        )

@router.post("/update", dependencies=[Depends(verify_admin_token)])
def trigger_update(db: Session = Depends(get_db)):
    """
    Secured endpoint to trigger database updates (scores, odds, ELOs, simulation predictions).
    """
    result = update_results_and_odds(db)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message")
        )
    return result
