from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend.database import Competition, Tournament, Team, Fixture
from backend.services.format_adapters import CompetitionSyncAdapter


def _pl_setup(db_session):
    comp = Competition(
        name="Premier League",
        type="League",
        api_league_id=39,
        format_engine="league",
    )
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(
        competition_id=comp.id,
        season_name="2026/27",
        status="Active",
    )
    db_session.add(tourney)

    home_team = Team(name="Arsenal", team_type="Club")
    away_team = Team(name="Chelsea", team_type="Club")
    db_session.add_all([home_team, away_team])
    db_session.flush()

    fixture = Fixture(
        tournament_id=tourney.id,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        stage="Regular Season",
        status="Scheduled",
        date_utc=datetime.now(timezone.utc),
        winner_id=None,
    )
    db_session.add(fixture)
    db_session.commit()
    return tourney, fixture


def test_competition_code_guardrail_prevents_cross_pollination(db_session, monkeypatch):
    """Incoming Football-Data.org matches for a different competition must not update this tournament."""
    monkeypatch.setenv("FOOTBALL_DATA_ORG_KEY", "test-fd-key")
    tourney, fixture = _pl_setup(db_session)
    kickoff = fixture.date_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    mismatched_payload = {
        "matches": [
            {
                "id": 999999,
                "utcDate": kickoff,
                "status": "FINISHED",
                "homeTeam": {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal"},
                "awayTeam": {"id": 61, "name": "Chelsea FC", "shortName": "Chelsea"},
                "score": {"fullTime": {"home": 2, "away": 1}},
                "competition": {"code": "CL", "name": "UEFA Champions League"},
            }
        ]
    }
    fetch = MagicMock(return_value=mismatched_payload)
    adapter = CompetitionSyncAdapter(fetch_json_with_retry=fetch)
    created, updated = adapter.sync_results(db_session, tourney)

    assert created == 0
    assert updated == 0
    db_session.refresh(fixture)
    assert fixture.status == "Scheduled"
    assert fixture.home_score is None

    matching_payload = {
        "matches": [
            {
                "id": 888888,
                "utcDate": kickoff,
                "status": "FINISHED",
                "homeTeam": {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal"},
                "awayTeam": {"id": 61, "name": "Chelsea FC", "shortName": "Chelsea"},
                "score": {"fullTime": {"home": 3, "away": 1}},
                "competition": {"code": "PL", "name": "Premier League"},
            }
        ]
    }
    fetch.return_value = matching_payload
    created, updated = adapter.sync_results(db_session, tourney)

    assert created == 0
    assert updated == 1
    db_session.refresh(fixture)
    assert fixture.status == "Finished"
    assert fixture.home_score == 3
    assert fixture.away_score == 1
    assert fixture.api_id == "fd_888888"
