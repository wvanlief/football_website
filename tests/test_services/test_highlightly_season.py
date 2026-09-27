from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend.database import Competition, Fixture, Team, Tournament
from backend.services.ingestion.engine import IngestionEngine
from backend.services.providers.highlightly import HighlightlyProvider

UEL_MATCH = {
    "id": 1392473362,
    "date": "2026-09-24T19:00:00.000Z",
    "league": {"name": "UEFA Europa League"},
    "homeTeam": {"id": 497, "name": "Roma"},
    "awayTeam": {"id": 212, "name": "FC Porto"},
    "state": {"description": "Not started", "score": {"current": None}},
}

UECL_MATCH = {
    "id": 1393000001,
    "date": "2026-10-02T16:45:00.000Z",
    "league": {"name": "UEFA Europa Conference League"},
    "homeTeam": {"id": 99, "name": "Fiorentina"},
    "awayTeam": {"id": 100, "name": "Real Betis"},
    "state": {"description": "Not started", "score": {"current": None}},
}


def test_highlightly_season_pages_uel(monkeypatch):
    calls = []

    def _fetch(url, headers=None, **kwargs):
        calls.append((url, headers, kwargs.get("provider")))
        if "offset=0" in url:
            return {
                "data": [UEL_MATCH] * 100,
                "pagination": {"totalCount": 188, "offset": 0, "limit": 100},
                "plan": {"tier": "BASIC", "message": "All data available with current plan."},
            }
        return {
            "data": [UEL_MATCH] * 88,
            "pagination": {"totalCount": 188, "offset": 100, "limit": 100},
        }

    monkeypatch.setattr(
        "backend.services.providers.highlightly.fetch_json_with_retry",
        _fetch,
    )
    rows = HighlightlyProvider(api_key="hl-key").fetch_fixtures("UEFA Europa League", 2026)
    assert len(rows) == 188
    assert "leagueName=UEFA+Europa+League" in calls[0][0]
    assert "season=2026" in calls[0][0]
    assert calls[0][1] == {"x-rapidapi-key": "hl-key"}
    assert calls[0][2] == "highlightly"
    assert "offset=100" in calls[1][0]
    assert len(calls) == 2


def test_highlightly_conference_league_uses_alias_after_empty_catalog_name(monkeypatch):
    calls = []

    def _fetch(url, headers=None, **kwargs):
        calls.append(url)
        if "UEFA+Conference+League" in url and "Europa" not in url:
            return {"data": [], "pagination": {"totalCount": 0, "offset": 0, "limit": 100}}
        return {"data": [UECL_MATCH], "pagination": {"totalCount": 1, "offset": 0, "limit": 100}}

    monkeypatch.setattr(
        "backend.services.providers.highlightly.fetch_json_with_retry",
        _fetch,
    )
    rows = HighlightlyProvider(api_key="hl-key").fetch_fixtures("UEFA Conference League", 2026)
    assert rows == [UECL_MATCH]
    assert any("leagueName=UEFA+Conference+League" in url for url in calls)
    assert any("leagueName=UEFA+Europa+Conference+League" in url for url in calls)


def test_engine_uses_highlightly_for_uel_and_skips_thesportsdb(db_session):
    fd = MagicMock()
    fd.fetch_fixtures.return_value = []
    fd.last_request_skipped = False
    hl = HighlightlyProvider(api_key="hl-key")
    hl.fetch_fixtures = MagicMock(return_value=[UEL_MATCH])
    tsdb = MagicMock()
    engine = IngestionEngine(
        fd_provider=fd,
        openfootball_provider=MagicMock(),
        highlightly_provider=hl,
        tsdb_provider=tsdb,
    )
    result = engine.seed_competition(
        db=db_session,
        competition_name="UEFA Europa League",
        competition_type="Cup",
        format_engine="league_phase_knockout",
        season="2026/27",
        api_league_id=3,
        api_season=2026,
    )
    assert result.created == 1
    hl.fetch_fixtures.assert_called_once()
    assert hl.fetch_fixtures.call_args.args[0] == "UEFA Europa League"
    assert hl.fetch_fixtures.call_args.args[1] == 2026
    tsdb.fetch_fixtures.assert_not_called()
    fixture = db_session.query(Fixture).one()
    assert fixture.api_id == "hl_1392473362"
    assert fixture.stage == "League Phase"


def test_highlightly_shifted_kickoff_updates_unique_pairing(db_session):
    comp = Competition(
        name="UEFA Europa League",
        type="Cup",
        format_engine="league_phase_knockout",
        api_league_id=3,
    )
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()
    home = Team(name="Roma", team_type="Club")
    away = Team(name="FC Porto", team_type="Club")
    db_session.add_all([home, away])
    db_session.flush()
    original = Fixture(
        tournament_id=tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        date_utc=datetime(2026, 8, 1, 19, 0, tzinfo=timezone.utc),
        stage="Qualifying",
        status="Scheduled",
    )
    db_session.add(original)
    db_session.commit()

    fd = MagicMock()
    fd.fetch_fixtures.return_value = []
    fd.last_request_skipped = False
    hl = HighlightlyProvider(api_key="hl-key")
    hl.fetch_fixtures = MagicMock(return_value=[UEL_MATCH])
    engine = IngestionEngine(
        fd_provider=fd,
        openfootball_provider=MagicMock(),
        highlightly_provider=hl,
        tsdb_provider=MagicMock(),
    )
    result = engine.seed_competition(
        db=db_session,
        competition_name="UEFA Europa League",
        competition_type="Cup",
        format_engine="league_phase_knockout",
        season="2026/27",
        api_league_id=3,
        api_season=2026,
    )
    assert result.created == 0
    assert result.updated == 1
    db_session.refresh(original)
    assert original.api_id == "hl_1392473362"
    stored = original.date_utc
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored == datetime(2026, 9, 24, 19, 0, tzinfo=timezone.utc)
    assert db_session.query(Fixture).filter_by(tournament_id=tourney.id).count() == 1
