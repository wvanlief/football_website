import os
from fastapi import APIRouter, Depends, Header, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session

from backend.database import get_db, SessionLocal
from backend.services.updater import update_results_and_odds, update_live_scores

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# Token retrieved from environment variables, defaulting to dev-admin-token for local runs
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dev-admin-token")

def verify_admin_token(x_admin_token: str = Header(None, alias="X-Admin-Token")):
    """Dependency to verify admin token from X-Admin-Token header."""
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token."
        )

def _bg_update_results():
    db = SessionLocal()
    try:
        update_results_and_odds(db)
    except Exception as e:
        print(f"Background update task failed: {e}")
    finally:
        db.close()

def _bg_update_live(force: bool):
    db = SessionLocal()
    try:
        update_live_scores(db, force=force)
    except Exception as e:
        print(f"Background live update task failed: {e}")
    finally:
        db.close()

@router.post("/update", dependencies=[Depends(verify_admin_token)])
def trigger_update(
    background_tasks: BackgroundTasks,
    async_task: bool = Query(False, alias="async"),
    background: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Secured endpoint to trigger database updates (scores, odds, ELOs, simulation predictions).
    Pass ?async=true or ?background=true to run asynchronously in background.
    """
    if async_task or background:
        background_tasks.add_task(_bg_update_results)
        return {"status": "processing", "message": "Batch update task dispatched in background."}

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
def trigger_live_update(
    background_tasks: BackgroundTasks,
    force: bool = False,
    async_task: bool = Query(False, alias="async"),
    background: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Secured endpoint to trigger database live-score updates dynamically.
    Only updates when matches are in progress unless forced.
    Pass ?async=true or ?background=true to run asynchronously in background.
    """
    if async_task or background:
        background_tasks.add_task(_bg_update_live, force)
        return {"status": "processing", "message": "Live update task dispatched in background."}

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
def trigger_seed_all(confirm: bool = False, db: Session = Depends(get_db)):
    """
    Secured endpoint to trigger full database seeding across all major competitions.
    Requires confirm=true query parameter to prevent accidental API quota consumption.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This operation consumes external API calls. Pass ?confirm=true to execute."
        )
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


@router.post("/seed-one", dependencies=[Depends(verify_admin_token)])
def trigger_seed_one(
    league_id: int = Query(..., description="API-Football league ID or competition identifier to seed"),
    confirm: bool = Query(False, description="Confirmation flag required to prevent accidental quota usage"),
    fetch_squads: bool = Query(False, description="Whether to fetch full squad rosters (consumes extra API calls)"),
    db: Session = Depends(get_db)
):
    """
    Secured endpoint to trigger database seeding for a single competition.
    Requires confirm=true query parameter to prevent accidental API quota consumption.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This operation consumes external API calls. Pass ?confirm=true to execute."
        )
    try:
        from backend.services.seeder import seed_single_competition
        result = seed_single_competition(db, league_id=league_id, fetch_squads=fetch_squads)
        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Seeding failed.")
            )
        return result
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve)
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Single-competition seeding task failed: {str(e)}"
        )




