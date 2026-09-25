import inspect
from unittest.mock import patch
from urllib.error import HTTPError

from backend.database import Competition, Fixture, Tournament
from backend.services.providers.football_api import FootballApiProvider
from backend.services.providers.highlightly import HighlightlyProvider
from backend.services.rate_limiter import APIRateLimiter
from backend.services.updater import (
    sync_global_live_scores,
    sync_non_fd_date_overlay,
    update_live_scores,
    update_results_and_odds,
)

UEL_FA = {
    "fixture": {
        "id": 77001,
        "date": "2026-09-25T19:00:00+00:00",
        "status": {"short": "NS"},
    },
    "league": {"id": 3, "name": "UEFA Europa League", "round": "League Stage - 1"},
    "teams": {
        "home": {"id": 496, "name": "Juventus"},
        "away": {"id": 81, "name": "Marseille"},
    },
    "goals": {"home": None, "away": None},
}

UEL_HL = {
    "id": 1392473362,
    "date": "2026-09-25T19:00:00.000Z",
    "league": {"name": "UEFA Europa League"},
    "homeTeam": {"id": 496, "name": "Juventus"},
    "awayTeam": {"id": 81, "name": "Marseille"},
    "state": {"description": "Not started", "score": {"current": None}},
}


def _uel(db_session):
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
    db_session.commit()
    return comp, tourney


def test_daily_docstring_names_fd_plus_two_football_api_calls():
    text = update_results_and_odds.__doc__
    assert "1 Football-Data.org" in text
    assert "2 Football-API" in text
    assert "Highlightly" in text


def test_live_path_does_not_call_football_api_or_highlightly():
    source = inspect.getsource(update_live_scores) + inspect.getsource(sync_global_live_scores)
    assert "HighlightlyProvider" not in source
    assert "FootballApiProvider" not in source
    assert "fetch_fixtures_by_date" not in source
    assert "fetch_matches_by_date" not in source


def test_two_football_api_date_calls_skip_highlightly_on_200(db_session):
    _uel(db_session)

    with patch.object(
        FootballApiProvider,
        "fetch_fixtures_by_date",
        return_value=([UEL_FA], False),
    ) as fa_fetch, patch.object(
        HighlightlyProvider, "fetch_matches_by_date"
    ) as hl_fetch:
        created, updated = sync_non_fd_date_overlay(
            db_session, ["2026-09-24", "2026-09-25"]
        )

    assert fa_fetch.call_count == 2
    assert [call.args[0] for call in fa_fetch.call_args_list] == [
        "2026-09-24",
        "2026-09-25",
    ]
    hl_fetch.assert_not_called()
    assert created == 1
    assert updated == 1
    stamped = db_session.query(Fixture).filter(Fixture.api_id == "fa_77001").one()
    assert stamped.stage == "League Phase"


def test_highlightly_failover_when_football_api_returns_4xx(db_session):
    _uel(db_session)

    with patch.object(
        FootballApiProvider,
        "fetch_fixtures_by_date",
        return_value=([], True),
    ) as fa_fetch, patch.object(
        HighlightlyProvider,
        "fetch_matches_by_date",
        return_value=[UEL_HL],
    ) as hl_fetch:
        created, _updated = sync_non_fd_date_overlay(db_session, ["2026-09-25"])

    fa_fetch.assert_called_once()
    hl_fetch.assert_called_once_with("2026-09-25")
    assert created == 1
    fixture = db_session.query(Fixture).filter(Fixture.api_id == "hl_1392473362").one()
    assert fixture.home_team.name == "Juventus"


def test_football_api_date_http_403_is_a_failure(monkeypatch):
    def _boom(*args, **kwargs):
        raise HTTPError("https://v3.football.api-sports.io/fixtures?date=2026-09-25", 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr(
        "backend.services.providers.football_api.fetch_json_with_retry",
        _boom,
    )
    fixtures, failed = FootballApiProvider(api_key="test-key").fetch_fixtures_by_date("2026-09-25")
    assert fixtures == []
    assert failed is True


def test_highlightly_date_query_pages_and_optional_league_filter(monkeypatch):
    calls = []

    def _fetch(url, headers=None, **kwargs):
        calls.append((url, headers, kwargs.get("provider")))
        if "offset=0" in url:
            return {
                "data": [UEL_HL] * 100,
                "pagination": {"totalCount": 101, "offset": 0, "limit": 100},
            }
        return {"data": [], "pagination": {"totalCount": 101, "offset": 100, "limit": 100}}

    monkeypatch.setattr(
        "backend.services.providers.highlightly.fetch_json_with_retry",
        _fetch,
    )
    rows = HighlightlyProvider(api_key="hl-key").fetch_matches_by_date(
        "2026-09-25", league_name="UEFA Europa League"
    )
    assert len(rows) == 100
    assert "leagueName=UEFA+Europa+League" in calls[0][0]
    assert calls[0][1] == {"x-rapidapi-key": "hl-key"}
    assert calls[0][2] == "highlightly"
    assert "offset=100" in calls[1][0]
    assert APIRateLimiter.LIMITS["highlightly"] == {"per_min": 10, "per_day": 90}
