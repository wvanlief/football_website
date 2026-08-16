from unittest.mock import patch
from datetime import datetime, timezone

from backend.database import Competition, Tournament, Team, Fixture
from backend.services.format_adapters import CompetitionSyncAdapter

def test_league_id_guardrail_prevents_cross_pollination(db_session):
    """
    Verifies that CompetitionSyncAdapter skips incoming API fixtures
    whose league_id does not match the target competition's api_league_id.
    """
    # 1. Create target competition (DFB Pokal, api_league_id=81)
    dfb_pokal = Competition(
        name="DFB Pokal",
        type="Cup",
        api_league_id=81,
        format_engine="cup"
    )
    db_session.add(dfb_pokal)
    db_session.flush()

    tourney = Tournament(
        competition_id=dfb_pokal.id,
        season_name="2026/27",
        status="Active"
    )
    db_session.add(tourney)
    
    home_team = Team(name="Bayern Munich", api_id=157, team_type="Club")
    away_team = Team(name="Dortmund", api_id=165, team_type="Club")
    db_session.add_all([home_team, away_team])
    db_session.commit()

    # 2. Mock incoming API response containing a World Cup fixture (league_id=1)
    mismatched_payload = {
        "response": [
            {
                "fixture": {
                    "id": 999999,
                    "date": datetime.now(timezone.utc).isoformat(),
                    "status": {"short": "NS"}
                },
                "league": {
                    "id": 1,  # World Cup ID (Mismatched for DFB Pokal ID 81)
                    "round": "Group Stage"
                },
                "teams": {
                    "home": {"id": 157, "name": "Bayern Munich"},
                    "away": {"id": 165, "name": "Dortmund"}
                },
                "goals": {"home": None, "away": None}
            }
        ]
    }

    adapter = CompetitionSyncAdapter()

    with patch("backend.services.updater.call_football_api", return_value=mismatched_payload), \
         patch("backend.services.elo.fetch_clubelo_ratings", return_value={}):
        created, updated = adapter.sync_results(db_session, tourney)

    # 3. Assert guardrail skipped the mismatched World Cup fixture
    assert created == 0
    fixture_count = db_session.query(Fixture).filter(Fixture.tournament_id == tourney.id).count()
    assert fixture_count == 0

    # 4. Mock incoming API response with matching DFB Pokal league_id (league_id=81)
    matching_payload = {
        "response": [
            {
                "fixture": {
                    "id": 888888,
                    "date": datetime.now(timezone.utc).isoformat(),
                    "status": {"short": "NS"}
                },
                "league": {
                    "id": 81,  # Matches DFB Pokal ID 81
                    "round": "Round of 32"
                },
                "teams": {
                    "home": {"id": 157, "name": "Bayern Munich"},
                    "away": {"id": 165, "name": "Dortmund"}
                },
                "goals": {"home": None, "away": None}
            }
        ]
    }

    with patch("backend.services.updater.call_football_api", return_value=matching_payload), \
         patch("backend.services.elo.fetch_clubelo_ratings", return_value={}):
        created, updated = adapter.sync_results(db_session, tourney)

    # 5. Assert matching fixture was created
    assert created == 1
    fixture = db_session.query(Fixture).filter(Fixture.tournament_id == tourney.id).first()
    assert fixture is not None
    assert fixture.api_id == "888888"
