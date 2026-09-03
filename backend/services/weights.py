from sqlalchemy.orm import Session
from backend.crud.fixture import get_all_fixtures
from backend.scoring import score

def normalize_weights(w: dict) -> dict:
    """Normalizes a weights dictionary so the sum equals 1.0."""
    total = w["elo"] + w["odds"] + w["form"] + w["narrative"]
    if total == 0:
        return {k: 0.25 for k in w}
    return {k: w[k] / total for k in w}

def recalculate_all_fixture_scores(db: Session, weights: dict):
    """Recalculates watchability scores for all fixtures using the provided weights."""
    fixtures = get_all_fixtures(db)
    for fixture in fixtures:
        score(fixture, db, weights)
    db.commit()
