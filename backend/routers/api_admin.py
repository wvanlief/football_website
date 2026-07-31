import os
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.updater import update_results_and_odds, update_live_scores

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
    try:
        result = update_results_and_odds(db)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message")
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Update task failed: {str(e)}"
        )

@router.post("/update-live", dependencies=[Depends(verify_admin_token)])
def trigger_live_update(force: bool = False, db: Session = Depends(get_db)):
    """
    Secured endpoint to trigger database live-score updates dynamically.
    Only updates when matches are in progress unless forced.
    """
    try:
        result = update_live_scores(db, force=force)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message")
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Live update task failed: {str(e)}"
        )

@router.post("/seed-all", dependencies=[Depends(verify_admin_token)])
def trigger_seed_all(db: Session = Depends(get_db)):
    """
    Secured endpoint to trigger full database seeding across all major competitions (World Cup, Premier League, Champions League, La Liga, Copa del Rey, Nations League).
    """
    try:
        from backend.services.seeder import seed_all_default_competitions
        details = seed_all_default_competitions(db)
        return {"status": "success", "message": "All default competitions seeded successfully.", "details": details}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Seeding task failed: {str(e)}"
        )



