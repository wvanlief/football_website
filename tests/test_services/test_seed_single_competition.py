import pytest
from unittest.mock import patch, MagicMock

from backend.database import Competition, Tournament, Fixture
from backend.services.seeder import seed_single_competition, seed_european_cups, retire_european_draw_placeholders


@patch("backend.services.seeder.sync_european_cup_from_api")
@patch("backend.services.seeder.fetch_and_seed_teams")
def test_seed_single_competition_european_cup(mock_fetch_teams, mock_live_sync, db_session, monkeypatch):
    monkeypatch.delenv("FOOTBALL_API_KEY", raising=False)
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    # Seeding single European cup (e.g. Champions League, league_id=2)
    result = seed_single_competition(db_session, league_id=2)
    assert result["status"] == "success"
    assert result["league_id"] == 2
    assert "details" in result
    
    # Check that UEFA Champions League was created in DB
    ucl_comp = db_session.query(Competition).filter(Competition.name == "UEFA Champions League").first()
    assert ucl_comp is not None
    assert ucl_comp.api_league_id == 2
    
    # Check that UEFA Europa League was NOT seeded when filtering by league_id=2
    uel_comp = db_session.query(Competition).filter(Competition.name == "UEFA Europa League").first()
    assert uel_comp is None
    mock_live_sync.assert_not_called()


@patch("backend.services.seeder.sync_european_cup_from_api")
@patch("backend.services.seeder.fetch_and_seed_teams")
def test_seed_single_european_cup_overlays_live_api(mock_fetch_teams, mock_live_sync, db_session, monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_KEY", "test-key")
    mock_live_sync.return_value = {"status": "success", "created": 144, "updated": 48, "retired": 189}

    result = seed_single_competition(db_session, league_id=2)

    assert result["status"] == "success"
    mock_live_sync.assert_called_once()
    assert mock_live_sync.call_args.args[1] == 2
    assert result["details"]["live_api_sync"]["created"] == 144


def test_retire_european_draw_placeholders_keeps_api_mapped_fixtures(db_session):
    from datetime import datetime, timezone

    from backend.database import Team, TournamentTeam

    comp = Competition(name="UCL Placeholder Retire", type="Cup", format_engine="league_phase_knockout")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()
    home = Team(name="Liverpool Retire", team_type="Club")
    away = Team(name="Atletico Retire", team_type="Club")
    db_session.add_all([home, away])
    db_session.flush()
    db_session.add_all([
        TournamentTeam(tournament_id=tourney.id, team_id=home.id),
        TournamentTeam(tournament_id=tourney.id, team_id=away.id),
    ])
    now = datetime(2026, 9, 9, 19, 0, tzinfo=timezone.utc)
    live = Fixture(
        tournament_id=tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        date_utc=now,
        stage="League Phase",
        status="Scheduled",
        api_id="140001",
    )
    stale = Fixture(
        tournament_id=tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        date_utc=datetime(2026, 9, 17, 21, 0, tzinfo=timezone.utc),
        stage="League Phase",
        status="Scheduled",
        api_id=None,
    )
    db_session.add_all([live, stale])
    db_session.commit()

    removed = retire_european_draw_placeholders(db_session, tourney.id)
    db_session.commit()

    remaining = db_session.query(Fixture).filter(Fixture.tournament_id == tourney.id).all()
    assert removed == 1
    assert len(remaining) == 1
    assert remaining[0].api_id == "140001"


@patch("backend.services.seeder.fetch_and_seed_teams")
@patch("backend.services.seeder.seed_competition")
def test_seed_single_competition_default_league(mock_seed_comp, mock_fetch_teams, db_session):
    # Setup mock return
    mock_upsert = MagicMock()
    mock_upsert.created = 380
    mock_upsert.updated = 0
    mock_upsert.odds_added = 380
    mock_seed_comp.return_value = mock_upsert

    result = seed_single_competition(db_session, league_id=39)
    assert result["status"] == "success"
    assert result["competition"] == "Premier League"
    assert result["league_id"] == 39
    assert result["fixtures_created"] == 380
    mock_seed_comp.assert_called_once()


@patch("backend.services.seeder.fetch_and_seed_teams")
@patch("backend.services.seeder.seed_competition")
def test_seed_single_competition_custom_db_competition(mock_seed_comp, mock_fetch_teams, db_session):
    # Insert custom competition in DB
    custom_comp = Competition(
        name="Scottish Cup",
        type="Cup",
        format_engine="cup",
        api_league_id=5555
    )
    db_session.add(custom_comp)
    db_session.commit()

    mock_upsert = MagicMock()
    mock_upsert.created = 60
    mock_upsert.updated = 5
    mock_upsert.odds_added = 60
    mock_seed_comp.return_value = mock_upsert

    result = seed_single_competition(db_session, league_id=5555)
    assert result["status"] == "success"
    assert result["competition"] == "Scottish Cup"
    assert result["league_id"] == 5555
    assert result["fixtures_created"] == 60


def test_seed_single_competition_invalid_id(db_session):
    with pytest.raises(ValueError) as excinfo:
        seed_single_competition(db_session, league_id=9999999)
    assert "9999999" in str(excinfo.value)
