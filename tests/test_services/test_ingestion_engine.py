from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import pytest
from backend.database import Competition, Tournament, Fixture
from backend.services.ingestion.engine import IngestionEngine, seed_competition
from backend.services.ingestion.preflight import IngestionAborted


@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
def test_engine_seed_competition_primary_fd(mock_fd_fetch, db_session):
    """IngestionEngine.seed_competition successfully populates competition via primary provider."""
    mock_fd_fetch.return_value = [
        {
            "id": 8001,
            "utcDate": "2026-08-22T14:00:00Z",
            "status": "SCHEDULED",
            "matchday": 1,
            "stage": "REGULAR_SEASON",
            "homeTeam": {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal"},
            "awayTeam": {"id": 66, "name": "Manchester United FC", "shortName": "Man United"}
        }
    ]

    engine = IngestionEngine()
    result = engine.seed_competition(
        db=db_session,
        competition_name="Premier League Engine Test",
        competition_type="League",
        format_engine="league",
        season="2026/27",
        api_league_id=39,
        api_season=2026
    )

    assert result.created == 1
    comp = db_session.query(Competition).filter_by(name="Premier League Engine Test").first()
    assert comp is not None

    tourney = db_session.query(Tournament).filter_by(competition_id=comp.id).first()
    assert tourney is not None

    fixtures = db_session.query(Fixture).filter_by(tournament_id=tourney.id).all()
    assert len(fixtures) == 1
    assert fixtures[0].api_id == "fd_8001"


@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
@patch("backend.services.providers.api_football.ApiFootballProvider.fetch_fixtures")
def test_engine_preflight_aborts_data_loss(mock_af_fetch, mock_fd_fetch, db_session):
    """Preflight guard aborts ingestion when providers return <50% of existing DB fixture count."""
    comp = Competition(name="La Liga Guard Test", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    now_utc = datetime.now(timezone.utc)
    # Pre-populate 10 fixtures
    for i in range(10):
        db_session.add(Fixture(
            tournament_id=tourney.id,
            api_id=f"exist_{i}",
            date_utc=now_utc,
            stage="Regular Season",
            status="Scheduled"
        ))
    db_session.commit()

    # Providers fail / return only 1 fixture (10% of 10 -> below 50% threshold)
    mock_fd_fetch.return_value = []
    mock_af_fetch.return_value = [
        {
            "fixture": {"id": 999, "date": "2026-08-22T14:00:00Z", "status": {"short": "NS"}},
            "teams": {"home": {"id": 1, "name": "Real Madrid"}, "away": {"id": 2, "name": "Barcelona"}},
            "goals": {"home": None, "away": None},
            "league": {"round": "Regular Season - 1"}
        }
    ]

    engine = IngestionEngine()
    with pytest.raises(IngestionAborted):
        engine.seed_competition(
            db=db_session,
            competition_name="La Liga Guard Test",
            season="2026/27",
            api_league_id=140
        )

    # Verify original 10 fixtures remain untouched in DB
    existing_after = db_session.query(Fixture).filter_by(tournament_id=tourney.id).all()
    assert len(existing_after) == 10
