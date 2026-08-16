"""
Pre-Calculated Feed Builder Module
Generates backend/data/fixtures_feed_cache.json containing enriched match fixture data
within a rolling window (-14 days to +30 days) for instant zero-latency serving.
"""
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Ensure backend modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy.orm import Session, joinedload
from backend.database import Fixture, Tournament, Competition, Team, TournamentTeam, PlayerContract
from backend.services.tournament import enrich_fixture, get_timezone

CACHE_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fixtures_feed_cache.json")

def build_fixtures_feed_cache(db: Session, force_enrichment: bool = False) -> dict:
    """
    Pre-calculates and serializes the global fixture feed for active competitions
    in a rolling window (-14 days to +30 days).
    Writes output to fixtures_feed_cache.json.
    """
    print(f"Building pre-calculated feed cache (force_enrichment={force_enrichment})...")
    start_time = time.time()

    now_utc = datetime.now(timezone.utc)
    window_start = now_utc - timedelta(days=14)
    window_end = now_utc + timedelta(days=30)

    # Active tournaments only
    active_tourneys = db.query(Tournament).filter(Tournament.status == "Active").all()
    active_ids = [t.id for t in active_tourneys] if active_tourneys else [t.id for t in db.query(Tournament).all()]

    # Query rolling window fixtures
    fixtures = (
        db.query(Fixture)
        .options(joinedload(Fixture.home_team), joinedload(Fixture.away_team))
        .filter(
            Fixture.tournament_id.in_(active_ids),
            Fixture.date_utc >= window_start,
            Fixture.date_utc <= window_end
        )
        .order_by(Fixture.date_utc.asc())
        .all()
    )

    # If off-season (no fixtures in 30 days), fetch earliest upcoming fixtures
    if not fixtures:
        print("No active fixtures in rolling window (-14 to +30 days). Fetching earliest upcoming fixtures...")
        fixtures = (
            db.query(Fixture)
            .options(joinedload(Fixture.home_team), joinedload(Fixture.away_team))
            .filter(
                Fixture.tournament_id.in_(active_ids),
                Fixture.date_utc >= now_utc
            )
            .order_by(Fixture.date_utc.asc())
            .limit(100)
            .all()
        )

    # Preload maps to avoid N+1 queries
    contracts = db.query(PlayerContract).options(joinedload(PlayerContract.player)).filter(
        PlayerContract.is_active == True
    ).all()
    team_players_map = {}
    for c in contracts:
        team_players_map.setdefault(c.team_id, []).append(c.player)

    tts = db.query(TournamentTeam).filter(TournamentTeam.tournament_id.in_(active_ids)).all()
    team_group_map = {(tt.tournament_id, tt.team_id): tt.group_name for tt in tts}

    target_tz = ZoneInfo("UTC")
    enriched_fixtures = []

    for f in fixtures:
        try:
            fdata = enrich_fixture(f, db, target_tz, team_players_map, team_group_map)
            enriched_fixtures.append(fdata)
        except Exception as e:
            print(f"Warning: Failed to enrich fixture ID {f.id}: {e}")

    feed_payload = {
        "updated_at": now_utc.isoformat(),
        "total_fixtures": len(enriched_fixtures),
        "fixtures": enriched_fixtures
    }

    # Save to disk
    os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)
    with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(feed_payload, f, ensure_ascii=False, indent=2)

    elapsed = round((time.time() - start_time) * 1000, 2)
    print(f"Successfully generated {CACHE_FILE_PATH} with {len(enriched_fixtures)} fixtures in {elapsed}ms.")
    return feed_payload

def load_precalculated_feed_cache() -> dict:
    """Loads pre-calculated feed cache from disk if available."""
    if os.path.exists(CACHE_FILE_PATH):
        try:
            with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {CACHE_FILE_PATH}: {e}")
    return None

if __name__ == "__main__":
    import argparse
    from backend.database import SessionLocal
    
    parser = argparse.ArgumentParser(description="Pre-Calculated Feed Generator")
    parser.add_argument("--force-enrichment", action="store_true", help="Force heavy enrichment calculation")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        build_fixtures_feed_cache(db, force_enrichment=args.force_enrichment)
    finally:
        db.close()
