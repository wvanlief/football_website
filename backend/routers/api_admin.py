import os
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db, Fixture
from backend.services.updater import update_results_and_odds, update_live_scores
from backend.crud import team as crud_team
from backend.crud import fixture as crud_fixture

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

@router.post("/update-live", dependencies=[Depends(verify_admin_token)])
def trigger_live_update(force: bool = False, db: Session = Depends(get_db)):
    """
    Secured endpoint to trigger database live-score updates dynamically.
    Only updates when matches are in progress unless forced.
    """
    result = update_live_scores(db, force=force)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message")
        )
    return result

@router.post("/fix-knockout-fixtures", dependencies=[Depends(verify_admin_token)])
def fix_knockout_fixtures(db: Session = Depends(get_db)):
    """
    One-time manual fix to set the correct teams for the Final and Third-place
    play-off fixtures while the external data source (worldcup26.ir) has not
    yet been updated.

    Final: Spain vs Argentina
    Third-place play-off: France vs England
    """
    team_names = ["Spain", "Argentina", "France", "England"]
    teams_by_name = {name: crud_team.get_team_by_name(db, name) for name in team_names}

    missing = [name for name, team in teams_by_name.items() if team is None]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not find team(s) in the database: {', '.join(missing)}"
        )

    updated_fixtures = []

    final_fixtures = crud_fixture.get_fixtures_by_stage(db, "Final")
    if not final_fixtures:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not find the Final fixture in the database."
        )
    for fixture in final_fixtures:
        fixture.home_team_id = teams_by_name["Spain"].id
        fixture.away_team_id = teams_by_name["Argentina"].id
        fixture.home_team_placeholder = None
        fixture.away_team_placeholder = None
        updated_fixtures.append(fixture.id)

    third_place_fixtures = crud_fixture.get_fixtures_by_stage(db, "Third-place play-off")
    if not third_place_fixtures:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not find the Third-place play-off fixture in the database."
        )
    for fixture in third_place_fixtures:
        fixture.home_team_id = teams_by_name["France"].id
        fixture.away_team_id = teams_by_name["England"].id
        fixture.home_team_placeholder = None
        fixture.away_team_placeholder = None
        updated_fixtures.append(fixture.id)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to commit fixture updates: {e}"
        )

    return {
        "status": "success",
        "message": "Final and Third-place play-off fixtures updated.",
        "updated_fixture_ids": updated_fixtures,
    }

