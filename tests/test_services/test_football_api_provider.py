from backend.database import Competition, Tournament
from backend.services.providers.football_api import FootballApiProvider
from backend.services.rate_limiter import APIRateLimiter

UEL_FIXTURE = {
    "fixture": {
        "id": 880011,
        "date": "2026-09-24T19:00:00+00:00",
        "status": {"short": "NS", "long": "Not Started"},
    },
    "league": {"id": 3, "season": 2026, "round": "League Stage - 1"},
    "teams": {
        "home": {"id": 497, "name": "Roma"},
        "away": {"id": 212, "name": "FC Porto"},
    },
    "goals": {"home": None, "away": None},
}

def test_football_api_normalizes_league_phase_with_fa_stamp(db_session, monkeypatch):
    calls = []

    def _fetch(url, headers=None, **kwargs):
        calls.append((url, headers, kwargs.get("provider")))
        return {"response": [UEL_FIXTURE]}

    monkeypatch.setattr(
        "backend.services.providers.football_api.fetch_json_with_retry",
        _fetch,
    )
    provider = FootballApiProvider(api_key="test-key")
    raw = provider.fetch_fixtures("UEFA Europa League", 2026, league_id=3)
    assert len(raw) == 1
    url, headers, provider_name = calls[0]
    assert url == "https://v3.football.api-sports.io/fixtures?league=3&season=2026"
    assert headers == {"x-apisports-key": "test-key"}
    assert provider_name == "football_api"
    assert "squads" not in url
    assert "media.api-sports.io" not in url

    comp = Competition(name="UEFA Europa League", type="Cup", api_league_id=3)
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.commit()

    payload = provider.normalize_fixture_payload(db_session, raw[0], tourney.id, "Cup")
    assert payload["api_id"] == "fa_880011"
    assert payload["stage"] == "League Phase"
    assert payload["matchday_number"] == 1
    assert payload["home_team"].name == "Roma"
    assert payload["away_team"].name == "FC Porto"
    assert "media.api-sports.io" not in str(payload)


def test_football_api_rate_limit_leaves_headroom():
    limits = APIRateLimiter.LIMITS["football_api"]
    assert limits == {"per_min": 10, "per_day": 90}
    assert "api_football" not in APIRateLimiter.LIMITS
