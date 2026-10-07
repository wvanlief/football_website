"""Live score poll: Highlightly first, one API-Football fallback, score-only cache patch."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.database import Competition, Fixture, Team, Tournament
from backend.services.providers.football_api import FootballApiProvider
from backend.services.providers.highlightly import HighlightlyProvider, _status_and_scores
from backend.services.queries import _FIXTURES_CACHE, _RECOMMENDED_CACHE
from backend.services.updater import update_live_scores
from backend.services import queries, updater


def test_live_queries_exclude_stale_rows_at_nine_hour_boundary(db_session, monkeypatch):
    now = datetime(2026, 10, 4, 0, 10, tzinfo=timezone.utc)
    start, end = queries.match_window_bounds(now)
    monkeypatch.setattr(queries, "match_window_bounds", lambda: (start, end))
    _comp, tourney = _competition(db_session, "Premier League")
    home, away = _pair(db_session, "Arsenal", "Chelsea")
    dates = [start - timedelta(hours=9, seconds=1), start - timedelta(hours=9),
             start - timedelta(hours=1), now]
    fixtures = []
    for index, kickoff in enumerate(dates):
        fixture, _ = _fixture(db_session, tourney, home, away, api_id=f"fd_{index}", status="Live")
        fixture.date_utc = kickoff
        fixtures.append(fixture)
    db_session.commit()
    expected = {fixture.id for fixture in fixtures[1:]}
    assert {f.id for f in queries.fixtures_in_match_window(db_session)} == expected
    assert {row["id"] for row in queries.list_match_window_scores(db_session)} == expected


@pytest.mark.parametrize("miss", [None, "empty", "error"])
def test_live_poll_queries_distinct_kickoff_dates_and_preserves_fallback(db_session, monkeypatch, miss):
    now = datetime(2026, 10, 4, 0, 10, tzinfo=timezone.utc)
    monkeypatch.setattr(queries, "match_window_bounds", lambda: queries_bounds)
    queries_bounds = (now - timedelta(hours=3), now + timedelta(minutes=15))
    _comp, tourney = _competition(db_session, "Premier League", api_league_id=39)
    fixtures = []
    for index, minutes in enumerate([60, 45, 5]):
        home, away = _pair(db_session, f"Home {index}", f"Away {index}")
        fixture, _ = _fixture(db_session, tourney, home, away, api_id=f"fd_{index}")
        fixture.date_utc = now - timedelta(minutes=minutes)
        fixtures.append(fixture)
    db_session.commit()
    calls, fallback_calls = [], []

    def fetch(self, date, league_name=None):
        calls.append((date, league_name))
        if date == "2026-10-03" and miss:
            if miss == "error":
                raise RuntimeError("provider unavailable")
            return []
        return [_hl(f.id, f.date_utc, league_name, f.home_team.name, f.away_team.name,
                    "Second half", "2-1") for f in fixtures if f.date_utc.date().isoformat() == date]

    def fallback(self):
        fallback_calls.append(True)
        return [_fa(f.id, f.date_utc, 39, "Premier League", f.home_team.name, f.away_team.name,
                    "2H", 2, 1) for f in fixtures[:2]], False

    monkeypatch.setattr(HighlightlyProvider, "fetch_matches_by_date", fetch)
    monkeypatch.setattr(FootballApiProvider, "fetch_live_fixtures", fallback)
    assert updater.sync_global_live_scores(db_session) == (3, 0)
    assert calls == [("2026-10-03", "Premier League"), ("2026-10-04", "Premier League")]
    assert len(fallback_calls) == int(miss is not None)
    assert all((f.status, f.home_score, f.away_score) == ("Live", 2, 1) for f in fixtures)


def _forbid(message):
    def _call(*_args, **_kwargs):
        raise AssertionError(message)

    return _call


@pytest.fixture(autouse=True)
def isolated_feed_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "fixtures_feed_cache.json"
    monkeypatch.setattr("backend.services.feed_builder.CACHE_FILE_PATH", str(cache_path))
    monkeypatch.setattr("backend.services.feed_builder.build_fixtures_feed_cache", _forbid("rebuild"))
    monkeypatch.setattr("backend.services.updater.sync_football_data_matches", _forbid("football-data"))
    monkeypatch.setattr(
        "backend.services.updater.recalculate_tournament_team_standings",
        _forbid("standings"),
    )
    monkeypatch.setattr("backend.services.updater.propagate_knockout_fixtures", _forbid("knockout"))
    monkeypatch.setattr("backend.services.lifecycle.finish_fixture", _forbid("finish_fixture"))
    monkeypatch.setattr(
        "backend.services.format_adapters.CompetitionSyncAdapter.sync_live_scores",
        _forbid("adapter live"),
    )
    return cache_path


def _keys(monkeypatch):
    monkeypatch.setenv("HIGHLIGHTLY_API_KEY", "hl-test")
    monkeypatch.setenv("FOOTBALLAPI_API_KEY", "fa-test")


def _install_fetch(monkeypatch, handler):
    monkeypatch.setattr("backend.services.providers.highlightly.fetch_json_with_retry", handler)
    monkeypatch.setattr("backend.services.providers.football_api.fetch_json_with_retry", handler)


def _competition(db, name, api_league_id=None):
    comp = Competition(
        name=name,
        type="League",
        format_engine="league",
        api_league_id=api_league_id,
    )
    db.add(comp)
    db.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db.add(tourney)
    db.flush()
    return comp, tourney


def _pair(db, home_name, away_name):
    home = Team(name=home_name, elo=1800)
    away = Team(name=away_name, elo=1700)
    db.add_all([home, away])
    db.flush()
    return home, away


def _fixture(db, tourney, home, away, *, api_id="fd_4242", minutes_ago=30, status="Scheduled"):
    kickoff = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    fixture = Fixture(
        tournament_id=tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        api_id=api_id,
        stage="Regular Season",
        status=status,
        date_utc=kickoff,
        winner_id=None,
        watchability_score=91.5,
    )
    db.add(fixture)
    db.commit()
    db.refresh(fixture)
    return fixture, kickoff


def _hl(match_id, kickoff, league, home, away, description, score):
    return {
        "id": match_id,
        "date": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "league": {"name": league},
        "homeTeam": {"id": 1, "name": home},
        "awayTeam": {"id": 2, "name": away},
        "state": {"description": description, "score": {"current": score}},
    }


def _fa(match_id, kickoff, league_id, league_name, home, away, short, home_goals, away_goals):
    return {
        "fixture": {
            "id": match_id,
            "date": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": {"short": short},
        },
        "league": {"id": league_id, "name": league_name},
        "teams": {
            "home": {"id": 10, "name": home},
            "away": {"id": 11, "name": away},
        },
        "goals": {"home": home_goals, "away": away_goals},
    }


def test_in_play_states_including_extra_time_are_live():
    assert _status_and_scores({
        "state": {"description": "Second half", "score": {"current": "2-1"}},
    }) == ("Live", 2, 1)
    assert _status_and_scores({
        "state": {"description": "Extra time", "score": {"current": "1-1"}},
    }) == ("Live", 1, 1)
    assert _status_and_scores({
        "state": {"description": "Penalties", "score": {"current": "1-1"}},
    }) == ("Live", 1, 1)
    assert _status_and_scores({
        "state": {"description": "Break", "score": {"current": "1-1"}},
    }) == ("Live", 1, 1)
    assert _status_and_scores({
        "state": {"description": "After extra time", "score": {"current": "2-1"}},
    }) == ("Finished", 2, 1)
    assert _status_and_scores({
        "state": {"description": "After penalties", "score": {"current": "2-1"}},
    }) == ("Finished", 2, 1)


@pytest.mark.parametrize("failure", [None, "serialize", "replace"])
def test_score_patch_is_atomic_and_cleans_up(isolated_feed_cache, monkeypatch, failure):
    from backend.services import feed_builder

    original = json.dumps({"fixtures": [{"id": 1, "status": "Scheduled", "score": None}]})
    isolated_feed_cache.write_text(original, encoding="utf-8")
    real_dump = json.dump
    real_replace = feed_builder.os.replace

    def dump(payload, handle, **kwargs):
        assert isolated_feed_cache.read_text(encoding="utf-8") == original
        assert handle.name != str(isolated_feed_cache)
        if failure == "serialize":
            handle.write('{"partial":')
            raise OSError("write failed")
        real_dump(payload, handle, **kwargs)

    def replace(source, destination):
        from pathlib import Path

        assert Path(source).parent == isolated_feed_cache.parent
        assert json.loads(Path(source).read_text())["fixtures"][0]["score"] == "0 - 0"
        assert isolated_feed_cache.read_text(encoding="utf-8") == original
        if failure == "replace":
            raise OSError("replace failed")
        real_replace(source, destination)

    monkeypatch.setattr(feed_builder.json, "dump", dump)
    monkeypatch.setattr(feed_builder.os, "replace", replace)
    patch = [{"id": 1, "status": "Live", "score": "0 - 0"}]
    if failure:
        with pytest.raises(OSError):
            feed_builder.patch_feed_cache_scores(patch)
        assert isolated_feed_cache.read_text(encoding="utf-8") == original
    else:
        assert feed_builder.patch_feed_cache_scores(patch)
        assert json.loads(isolated_feed_cache.read_text())["fixtures"] == patch
        assert not feed_builder.patch_feed_cache_scores(patch)
    assert list(isolated_feed_cache.parent.iterdir()) == [isolated_feed_cache]


@pytest.mark.parametrize("miss", [None, "empty", "error"])
def test_highlightly_polls_distinct_fixture_dates_and_falls_back_for_misses(
    db_session, monkeypatch, miss
):
    from backend.services import updater

    _comp, tourney = _competition(db_session, "Premier League", api_league_id=39)
    fixtures = []
    # Both sides of UTC midnight, with two matches on the earlier date.
    for index, kickoff in enumerate([
        datetime(2026, 10, 3, 23, 30),
        datetime(2026, 10, 4, 0, 15),
        datetime(2026, 10, 3, 23, 45),
    ]):
        home, away = _pair(db_session, f"Home {index}", f"Away {index}")
        fixture, _ = _fixture(db_session, tourney, home, away, api_id=f"fd_{index}")
        fixture.date_utc = kickoff
        fixtures.append(fixture)
    db_session.commit()
    monkeypatch.setattr(updater, "fixtures_in_match_window", lambda db: fixtures)
    calls = []

    def fetch(self, date, league_name):
        calls.append((date, league_name))
        if date == "2026-10-03" and miss:
            if miss == "error":
                raise RuntimeError("provider unavailable")
            return []
        return [
            _hl(f.id, f.date_utc, league_name, f.home_team.name, f.away_team.name, "First half", "2-1")
            for f in fixtures if f.date_utc.date().isoformat() == date
        ]

    fallback_calls = []

    def fallback(self):
        fallback_calls.append(True)
        return ([
            _fa(f.id, f.date_utc, 39, "Premier League", f.home_team.name, f.away_team.name, "1H", 1, 0)
            for f in fixtures
        ], False)

    monkeypatch.setattr(HighlightlyProvider, "fetch_matches_by_date", fetch)
    monkeypatch.setattr(FootballApiProvider, "fetch_live_fixtures", fallback)
    assert updater.sync_global_live_scores(db_session) == (3, 0)
    assert calls == [("2026-10-03", "Premier League"), ("2026-10-04", "Premier League")]
    assert len(fallback_calls) == int(miss is not None)
    for f in fixtures:
        expected = (1, 0) if miss and f.date_utc.day == 3 else (2, 1)
        assert (f.home_score, f.away_score) == expected


def test_highlightly_second_half_updates_fd_fixture_and_patches_score_only(
    db_session, monkeypatch, isolated_feed_cache
):
    _keys(monkeypatch)
    _comp, tourney = _competition(db_session, "Premier League", api_league_id=39)
    arsenal, chelsea = _pair(db_session, "Arsenal", "Chelsea")
    fixture, kickoff = _fixture(db_session, tourney, arsenal, chelsea, api_id="fd_4242")
    kickoff_before = fixture.date_utc
    team_count = db_session.query(Team).count()
    fixture_count = db_session.query(Fixture).count()

    other = {
        "id": fixture.id + 1000,
        "status": "Scheduled",
        "score": None,
        "watchability": {"overall": 40},
        "reasons": ["leave me"],
    }
    target = {
        "id": fixture.id,
        "status": "Scheduled",
        "score": None,
        "watchability": {"overall": 88, "tier": "Must Watch"},
        "reasons": ["derby"],
        "odds": {"home": 1.5, "draw": 3.2, "away": 4.1},
        "home_team": {"name": "Arsenal"},
    }
    isolated_feed_cache.write_text(json.dumps({
        "updated_at": "frozen",
        "total_fixtures": 2,
        "fixtures": [target, other],
    }), encoding="utf-8")
    _FIXTURES_CACHE["stale"] = (0, {"old": True})
    _RECOMMENDED_CACHE["stale"] = (0, [])

    calls = []

    def fetch(url, headers=None, **kwargs):
        calls.append(url)
        if "highlightly.net" in url:
            assert kwargs.get("use_cache") is False
            assert kwargs.get("provider") == "highlightly"
            return {
                "data": [
                    _hl(9001, kickoff, "Premier League", "Arsenal", "Chelsea", "Second half", "2-1"),
                    _hl(9002, kickoff, "Major League Soccer", "Inter Miami", "LA Galaxy", "Second half", "1-0"),
                ],
                "pagination": {"totalCount": 2},
            }
        raise AssertionError(url)

    _install_fetch(monkeypatch, fetch)
    result = update_live_scores(db_session, force=False)

    assert result["status"] == "success"
    assert result["fixtures_updated_live"] == 1
    assert result["fixtures_finished"] == 0
    assert len(calls) == 1
    assert "leagueName=Premier+League" in calls[0]
    assert "live=all" not in calls[0]
    assert "football-data.org" not in calls[0]

    db_session.refresh(fixture)
    assert fixture.status == "Live"
    assert fixture.home_score == 2
    assert fixture.away_score == 1
    assert fixture.api_id == "fd_4242"
    assert fixture.winner_id is None
    assert fixture.watchability_score == 91.5
    assert fixture.date_utc == kickoff_before
    assert db_session.query(Team).count() == team_count
    assert db_session.query(Fixture).count() == fixture_count
    assert db_session.query(Team).filter(Team.name == "Inter Miami").count() == 0

    cached = json.loads(isolated_feed_cache.read_text(encoding="utf-8"))
    assert cached["updated_at"] == "frozen"
    assert cached["total_fixtures"] == 2
    by_id = {item["id"]: item for item in cached["fixtures"]}
    assert by_id[fixture.id]["status"] == "Live"
    assert by_id[fixture.id]["score"] == "2 - 1"
    assert by_id[fixture.id]["watchability"] == {"overall": 88, "tier": "Must Watch"}
    assert by_id[fixture.id]["reasons"] == ["derby"]
    assert by_id[fixture.id]["odds"] == {"home": 1.5, "draw": 3.2, "away": 4.1}
    assert by_id[fixture.id]["home_team"] == {"name": "Arsenal"}
    assert by_id[other["id"]] == other
    assert _FIXTURES_CACHE == {}
    assert _RECOMMENDED_CACHE == {}


def test_concluded_highlightly_state_stores_finished_without_settling(
    db_session, monkeypatch, isolated_feed_cache
):
    _keys(monkeypatch)
    _comp, tourney = _competition(db_session, "Premier League", api_league_id=39)
    arsenal, chelsea = _pair(db_session, "Arsenal", "Chelsea")
    fixture, kickoff = _fixture(db_session, tourney, arsenal, chelsea, api_id="fd_4242", status="Live")
    fixture.home_score = 2
    fixture.away_score = 1
    db_session.commit()

    def fetch(url, headers=None, **kwargs):
        if "highlightly.net" in url:
            return {
                "data": [_hl(9001, kickoff, "Premier League", "Arsenal", "Chelsea", "Finished", "3-1")],
                "pagination": {"totalCount": 1},
            }
        raise AssertionError(url)

    _install_fetch(monkeypatch, fetch)
    result = update_live_scores(db_session, force=False)

    assert result["fixtures_updated_live"] == 0
    assert result["fixtures_finished"] == 1
    db_session.refresh(fixture)
    assert fixture.status == "Finished"
    assert fixture.home_score == 3
    assert fixture.away_score == 1
    assert fixture.winner_id is None
    assert fixture.watchability_score == 91.5
    assert fixture.api_id == "fd_4242"


def test_blank_api_id_takes_highlightly_stamp(db_session, monkeypatch):
    _keys(monkeypatch)
    _comp, tourney = _competition(db_session, "Premier League", api_league_id=39)
    arsenal, chelsea = _pair(db_session, "Arsenal", "Chelsea")
    fixture, kickoff = _fixture(db_session, tourney, arsenal, chelsea, api_id=None)

    def fetch(url, headers=None, **kwargs):
        if "highlightly.net" in url:
            return {
                "data": [_hl(9001, kickoff, "Premier League", "Arsenal", "Chelsea", "Second half", "1-0")],
                "pagination": {"totalCount": 1},
            }
        raise AssertionError(url)

    _install_fetch(monkeypatch, fetch)
    update_live_scores(db_session, force=False)
    db_session.refresh(fixture)
    assert fixture.api_id == "hl_9001"
    assert fixture.status == "Live"
    assert fixture.home_score == 1


def test_api_football_fallback_covers_highlightly_miss_and_ignores_unknown_league(
    db_session, monkeypatch
):
    _keys(monkeypatch)
    _pl, pl_tourney = _competition(db_session, "Premier League", api_league_id=39)
    _liga, liga_tourney = _competition(db_session, "La Liga", api_league_id=140)
    arsenal, chelsea = _pair(db_session, "Arsenal", "Chelsea")
    madrid, barca = _pair(db_session, "Real Madrid", "Barcelona")
    pl_fixture, pl_kickoff = _fixture(db_session, pl_tourney, arsenal, chelsea, api_id="fd_111")
    liga_fixture, liga_kickoff = _fixture(db_session, liga_tourney, madrid, barca, api_id=None)
    team_count = db_session.query(Team).count()
    fixture_count = db_session.query(Fixture).count()
    calls = []

    def fetch(url, headers=None, **kwargs):
        calls.append(url)
        if "highlightly.net" in url and "Premier+League" in url:
            return {
                "data": [_hl(1, pl_kickoff, "Premier League", "Arsenal", "Chelsea", "Second half", "2-1")],
                "pagination": {"totalCount": 1},
            }
        if "highlightly.net" in url and "La+Liga" in url:
            raise RuntimeError("highlightly down")
        if "live=all" in url:
            assert kwargs.get("use_cache") is False
            assert kwargs.get("provider") == "football_api"
            return {
                "response": [
                    _fa(50, pl_kickoff, 39, "Premier League", "Arsenal", "Chelsea", "1H", 0, 0),
                    _fa(60, liga_kickoff, 140, "La Liga", "Real Madrid", "Barcelona", "2H", 1, 0),
                    _fa(70, liga_kickoff, 99999, "Andorran First Division", "FC Andorra", "UE Santa Coloma", "1H", 3, 0),
                ]
            }
        raise AssertionError(url)

    _install_fetch(monkeypatch, fetch)
    result = update_live_scores(db_session, force=False)

    assert result["fixtures_updated_live"] == 2
    assert [url for url in calls if "live=all" in url] == [
        "https://v3.football.api-sports.io/fixtures?live=all"
    ]
    assert sum("highlightly.net" in url for url in calls) == 2
    assert not any("football-data.org" in url for url in calls)

    db_session.refresh(pl_fixture)
    db_session.refresh(liga_fixture)
    assert pl_fixture.status == "Live"
    assert pl_fixture.home_score == 2
    assert pl_fixture.away_score == 1
    assert pl_fixture.api_id == "fd_111"
    assert liga_fixture.status == "Live"
    assert liga_fixture.home_score == 1
    assert liga_fixture.away_score == 0
    assert liga_fixture.api_id == "fa_60"
    assert db_session.query(Team).count() == team_count
    assert db_session.query(Fixture).count() == fixture_count
    assert db_session.query(Team).filter(Team.name == "FC Andorra").count() == 0


def test_live_poll_includes_mapped_leagues_and_conference_alias(db_session, monkeypatch):
    _keys(monkeypatch)
    _pl, pl_tourney = _competition(db_session, "Premier League", api_league_id=39)
    _conf, conf_tourney = _competition(db_session, "UEFA Conference League", api_league_id=848)
    arsenal, chelsea = _pair(db_session, "Arsenal", "Chelsea")
    fiorentina, betis = _pair(db_session, "Fiorentina", "Real Betis")
    pl_fixture, pl_kickoff = _fixture(db_session, pl_tourney, arsenal, chelsea, api_id="fd_39")
    conf_fixture, conf_kickoff = _fixture(db_session, conf_tourney, fiorentina, betis, api_id="fd_848")
    calls = []

    def fetch(url, headers=None, **kwargs):
        calls.append(url)
        if "Premier+League" in url:
            return {
                "data": [_hl(1, pl_kickoff, "Premier League", "Arsenal", "Chelsea", "First half", "1-0")],
                "pagination": {"totalCount": 1},
            }
        if "UEFA+Europa+Conference+League" in url:
            return {
                "data": [_hl(
                    2, conf_kickoff, "UEFA Europa Conference League",
                    "Fiorentina", "Real Betis", "Second half", "0-1",
                )],
                "pagination": {"totalCount": 1},
            }
        raise AssertionError(url)

    _install_fetch(monkeypatch, fetch)
    result = update_live_scores(db_session, force=False)

    assert result["fixtures_updated_live"] == 2
    assert len(calls) == 2
    assert any("leagueName=Premier+League" in url for url in calls)
    assert any("leagueName=UEFA+Europa+Conference+League" in url for url in calls)
    db_session.refresh(pl_fixture)
    db_session.refresh(conf_fixture)
    assert (pl_fixture.status, pl_fixture.home_score, pl_fixture.away_score) == ("Live", 1, 0)
    assert (conf_fixture.status, conf_fixture.home_score, conf_fixture.away_score) == ("Live", 0, 1)
    assert pl_fixture.api_id == "fd_39"
    assert conf_fixture.api_id == "fd_848"


def test_quiet_window_makes_no_provider_call(db_session, monkeypatch):
    _comp, tourney = _competition(db_session, "Premier League", api_league_id=39)
    arsenal, chelsea = _pair(db_session, "Arsenal", "Chelsea")
    _fixture(db_session, tourney, arsenal, chelsea, minutes_ago=-60 * 24 * 5)
    monkeypatch.setattr(HighlightlyProvider, "fetch_matches_by_date", _forbid("highlightly"))
    monkeypatch.setattr(FootballApiProvider, "fetch_live_fixtures", _forbid("football-api"))

    result = update_live_scores(db_session, force=False)
    assert result["status"] == "skipped"
    assert "No active match window" in result["message"]


def test_both_rate_limiters_skip_without_football_data(db_session, monkeypatch):
    _keys(monkeypatch)
    _comp, tourney = _competition(db_session, "Premier League", api_league_id=39)
    arsenal, chelsea = _pair(db_session, "Arsenal", "Chelsea")
    fixture, _kickoff = _fixture(db_session, tourney, arsenal, chelsea)
    monkeypatch.setattr("backend.services.rate_limiter.rate_limiter.try_call", lambda _provider: False)
    monkeypatch.setattr("urllib.request.urlopen", _forbid("network"))

    result = update_live_scores(db_session, force=False)
    assert result["status"] == "success"
    assert result["fixtures_updated_live"] == 0
    assert result["fixtures_finished"] == 0
    db_session.refresh(fixture)
    assert fixture.status == "Scheduled"
    assert fixture.home_score is None
    assert fixture.api_id == "fd_4242"


def test_scores_endpoint_returns_match_window_rows(client, db_session):
    _comp, tourney = _competition(db_session, "Premier League", api_league_id=39)
    arsenal, chelsea = _pair(db_session, "Arsenal", "Chelsea")
    home_b, away_b = _pair(db_session, "Liverpool", "Everton")
    home_c, away_c = _pair(db_session, "Spurs", "Wolves")
    in_window, _kickoff = _fixture(db_session, tourney, arsenal, chelsea, api_id="fd_1", status="Live")
    in_window.home_score = 1
    in_window.away_score = 0
    finished, _done = _fixture(
        db_session, tourney, home_b, away_b, api_id="fd_2", minutes_ago=50, status="Finished",
    )
    finished.home_score = 2
    finished.away_score = 0
    late_live, _late = _fixture(
        db_session, tourney, home_c, away_c, api_id="fd_3", minutes_ago=240, status="Live",
    )
    late_live.home_score = 0
    late_live.away_score = 0
    future = Fixture(
        tournament_id=tourney.id,
        home_team_id=arsenal.id,
        away_team_id=chelsea.id,
        api_id="fd_future",
        stage="Regular Season",
        status="Scheduled",
        date_utc=datetime.now(timezone.utc) + timedelta(days=5),
    )
    db_session.add(future)
    db_session.commit()

    response = client.get("/api/fixtures/scores")
    assert response.status_code == 200
    rows = response.json()
    assert rows == sorted(rows, key=lambda row: row["id"])
    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {in_window.id, finished.id, late_live.id}
    assert by_id[in_window.id] == {"id": in_window.id, "status": "Live", "score": "1 - 0"}
    assert by_id[finished.id] == {"id": finished.id, "status": "Finished", "score": "2 - 0"}
    assert by_id[late_live.id] == {"id": late_live.id, "status": "Live", "score": "0 - 0"}
    assert future.id not in by_id
