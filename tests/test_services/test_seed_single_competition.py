import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from backend.database import Competition, Tournament, Fixture, Team, TournamentTeam
from backend.services.seeder import (
    seed_single_competition,
    retire_european_draw_placeholders,
)
import backend.crud.fixture as crud_fixture


def test_seed_single_competition_european_cup(db_session, monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_ORG_KEY", raising=False)
    monkeypatch.delenv("FOOTBALL_DATA_API_KEY", raising=False)
    monkeypatch.delenv("FOOTBALL_DATA_KEY", raising=False)
    monkeypatch.setattr(
        "backend.services.providers.thesportsdb.fetch_json_with_retry",
        lambda url, *args, **kwargs: {"countries": [], "leagues": [], "events": None},
    )
    monkeypatch.setattr(
        "backend.services.seeder.fetch_and_seed_teams",
        lambda *args, **kwargs: None,
    )
    result = seed_single_competition(db_session, league_id=2)
    assert result["status"] == "success"
    assert result["league_id"] == 2
    assert result["competition"] == "UEFA Champions League"

    ucl_comp = db_session.query(Competition).filter(Competition.name == "UEFA Champions League").first()
    assert ucl_comp is not None
    assert ucl_comp.api_league_id == 2
    tourney = db_session.query(Tournament).filter(Tournament.competition_id == ucl_comp.id).one()
    assert db_session.query(Fixture).filter(Fixture.tournament_id == tourney.id).count() == 0

    uel_comp = db_session.query(Competition).filter(Competition.name == "UEFA Europa League").first()
    assert uel_comp is None


def test_retire_european_draw_placeholders_never_deletes(db_session):
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
    assert removed == 0
    assert len(remaining) == 2


@patch("backend.services.seeder.fetch_and_seed_teams")
@patch("backend.services.seeder.seed_competition")
def test_seed_single_competition_default_league(mock_seed_comp, mock_fetch_teams, db_session):
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


def _fd_ucl_match(match_id, utc_date, home_short, away_short, home_name=None, away_name=None, matchday=1):
    return {
        "id": match_id,
        "utcDate": utc_date,
        "status": "TIMED",
        "matchday": matchday,
        "stage": "LEAGUE_STAGE",
        "homeTeam": {
            "id": match_id * 10 + 1,
            "name": home_name or home_short,
            "shortName": home_short,
        },
        "awayTeam": {
            "id": match_id * 10 + 2,
            "name": away_name or away_short,
            "shortName": away_short,
        },
    }


@patch("backend.services.seeder.fetch_and_seed_teams")
@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
def test_ucl_overlay_stamps_inserts_hides_and_skips_api_football_key(
    mock_fetch_fixtures, mock_fetch_teams, db_session, monkeypatch, tmp_path
):
    monkeypatch.delenv("FOOTBALL_API_KEY", raising=False)
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    for name in ("FOOTBALL_DATA_ORG_KEY", "FOOTBALL_DATA_API_KEY", "FOOTBALL_DATA_KEY"):
        monkeypatch.delenv(name, raising=False)

    mock_fetch_fixtures.return_value = [
        _fd_ucl_match(
            9001,
            "2026-09-16T19:00:00Z",
            "Sporting CP",
            "Galatasaray",
            home_name="Sporting Clube de Portugal",
            away_name="Galatasaray SK",
        ),
        _fd_ucl_match(
            9002,
            "2026-09-09T19:00:00Z",
            "Liverpool",
            "Atletico Madrid",
            home_name="Liverpool FC",
            away_name="Club Atlético de Madrid",
        ),
        _fd_ucl_match(
            9003,
            "2026-09-16T19:00:00Z",
            "Sporting CP",
            "Lille",
            home_name="Sporting Clube de Portugal",
            away_name="Lille OSC",
        ),
    ]

    leftover_home = Team(name="BSC Young Boys", team_type="Club")
    leftover_away = Team(name="Aston Villa", team_type="Club")
    db_session.add_all([leftover_home, leftover_away])
    db_session.flush()

    now_utc = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    from backend.services import feed_builder

    class FrozenDatetime:
        @staticmethod
        def now(tz=None):
            return now_utc

    cache_path = tmp_path / "fixtures_feed_cache.json"
    monkeypatch.setattr(feed_builder, "datetime", FrozenDatetime)
    monkeypatch.setattr(feed_builder, "CACHE_FILE_PATH", str(cache_path))
    monkeypatch.setenv("FOOTBALL_DATA_ORG_KEY", "fd-test-key")
    result = seed_single_competition(db_session, league_id=2)
    assert result["status"] == "success"
    mock_fetch_fixtures.assert_called()
    assert mock_fetch_fixtures.call_args[0][0] == "UEFA Champions League"

    ucl = db_session.query(Competition).filter_by(name="UEFA Champions League").first()
    tourney = db_session.query(Tournament).filter_by(competition_id=ucl.id).first()
    by_api = {
        f.api_id: f
        for f in db_session.query(Fixture).filter_by(tournament_id=tourney.id)
    }
    assert set(by_api) == {"fd_9001", "fd_9002", "fd_9003"}
    sporting_row = by_api["fd_9001"]
    stored = sporting_row.date_utc
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored.isoformat().startswith("2026-09-16T19:00:00")
    assert sporting_row.stage == "League Phase"
    assert "Sporting" in sporting_row.home_team.name
    assert "Galatasaray" in sporting_row.away_team.name

    liverpool = by_api["fd_9002"]
    assert "Liverpool" in liverpool.home_team.name
    assert "Atlético" in liverpool.away_team.name
    liv_dt = liverpool.date_utc
    if liv_dt.tzinfo is None:
        liv_dt = liv_dt.replace(tzinfo=timezone.utc)
    assert liv_dt.date().isoformat() == "2026-09-09"
    assert "Lille" in by_api["fd_9003"].away_team.name

    pairings = {
        (f.home_team.name, f.away_team.name)
        for f in db_session.query(Fixture).filter_by(tournament_id=tourney.id)
        if f.home_team and f.away_team
    }
    assert ("Sporting CP", "LASK") not in pairings
    assert ("BSC Young Boys", "Aston Villa") not in pairings
    assert ("Young Boys", "Aston Villa") not in pairings
    assert db_session.query(Fixture).filter(
        Fixture.tournament_id == tourney.id, Fixture.stage == "Play-offs"
    ).count() == 0

    eligible = crud_fixture.get_eligible_fixtures(db_session, tournament_id=tourney.id, now_utc=now_utc)
    eligible_ids = {f.id for f in eligible}
    assert sporting_row.id in eligible_ids
    assert liverpool.id in eligible_ids

    feed_payload = feed_builder.build_fixtures_feed_cache(db_session)
    names = {
        (item["home_team"]["name"], item["away_team"]["name"])
        for item in feed_payload["fixtures"]
    }
    assert any("Sporting" in h and "Galatasaray" in a for h, a in names)
    assert ("Sporting CP", "LASK") not in names
    assert any("Liverpool" in h and "Atlético" in a for h, a in names)
    assert ("BSC Young Boys", "Aston Villa") not in names
    assert ("Young Boys", "Aston Villa") not in names


@patch("backend.services.seeder.fetch_and_seed_teams")
@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
def test_europa_overlay_stamps_from_thesportsdb_after_empty_football_data(
    mock_fd_fetch, mock_tsdb_http, mock_fetch_teams, db_session, monkeypatch
):
    monkeypatch.setenv("FOOTBALL_DATA_ORG_KEY", "fd-test-key")
    mock_fd_fetch.return_value = []
    mock_tsdb_http.side_effect = lambda url, *args, **kwargs: (
        {
            "countries": [
                {"idLeague": "4481", "strLeague": "UEFA Europa League", "strSport": "Soccer"}
            ]
        }
        if "search_all_leagues.php" in url or "all_leagues.php" in url
        else {
            "events": [
                {
                    "idEvent": "2272400",
                    "idLeague": "4481",
                    "strLeague": "UEFA Europa League",
                    "strHomeTeam": "AZ Alkmaar",
                    "strAwayTeam": "Elfsborg",
                    "idHomeTeam": "133800",
                    "idAwayTeam": "133801",
                    "intRound": "1",
                    "intHomeScore": None,
                    "intAwayScore": None,
                    "strTimestamp": "2026-09-25T18:45:00",
                    "dateEvent": "2026-09-25",
                    "strTime": "18:45:00",
                    "strPostponed": "no",
                    "strStatus": "Not Started",
                }
            ]
        }
        if "eventsseason.php" in url
        else {}
    )

    result = seed_single_competition(db_session, league_id=3)
    assert result["status"] == "success"
    mock_fd_fetch.assert_called()
    assert mock_fd_fetch.call_args[0][0] == "UEFA Europa League"

    uel = db_session.query(Competition).filter_by(name="UEFA Europa League").first()
    tourney = db_session.query(Tournament).filter_by(competition_id=uel.id).first()
    stamped = (
        db_session.query(Fixture)
        .filter(Fixture.tournament_id == tourney.id, Fixture.api_id == "tsdb_2272400")
        .one()
    )
    assert stamped.home_team.name == "AZ Alkmaar"
    assert stamped.away_team.name == "Elfsborg"
    from backend.crud.mapping import get_external_id_for_competition
    assert get_external_id_for_competition(db_session, uel.id, "thesportsdb") == "4481"

    playoff_count = (
        db_session.query(Fixture)
        .filter(Fixture.tournament_id == tourney.id, Fixture.stage == "Play-offs")
        .count()
    )
    assert playoff_count == 0
    leftover = (
        db_session.query(Fixture)
        .filter(Fixture.tournament_id == tourney.id, Fixture.api_id.is_(None))
        .count()
    )
    assert leftover == 0
    tsdb_urls = [call.args[0] for call in mock_tsdb_http.call_args_list]
    assert any("search_all_leagues.php" in url for url in tsdb_urls)
    assert any("eventsseason.php" in url and "id=4481" in url for url in tsdb_urls)


@patch("backend.services.seeder.fetch_and_seed_teams")
@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
def test_europa_empty_thesportsdb_does_not_invent_fixtures(
    mock_fd_fetch, mock_tsdb_http, mock_fetch_teams, db_session, monkeypatch
):
    monkeypatch.setenv("FOOTBALL_DATA_ORG_KEY", "fd-test-key")
    mock_fd_fetch.return_value = []
    mock_tsdb_http.side_effect = lambda url, *args, **kwargs: (
        {"countries": [{"idLeague": "4481", "strLeague": "UEFA Europa League"}]}
        if "search_all_leagues.php" in url or "all_leagues.php" in url
        else {"events": None}
        if "eventsseason.php" in url
        else {}
    )

    seed_single_competition(db_session, league_id=3)
    uel = db_session.query(Competition).filter_by(name="UEFA Europa League").first()
    tourney = db_session.query(Tournament).filter_by(competition_id=uel.id).first()
    stamped = (
        db_session.query(Fixture)
        .filter(Fixture.tournament_id == tourney.id, Fixture.api_id.isnot(None))
        .count()
    )
    assert stamped == 0
    assert db_session.query(Fixture).filter_by(tournament_id=tourney.id).count() == 0


@patch("backend.services.seeder.fetch_and_seed_teams")
@patch("backend.services.providers.thesportsdb.fetch_json_with_retry")
@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
def test_conference_overlay_stamps_from_thesportsdb_after_empty_football_data(
    mock_fd_fetch, mock_tsdb_http, mock_fetch_teams, db_session, monkeypatch
):
    monkeypatch.setenv("FOOTBALL_DATA_ORG_KEY", "fd-test-key")
    mock_fd_fetch.return_value = []
    mock_tsdb_http.side_effect = lambda url, *args, **kwargs: (
        {
            "countries": [
                {
                    "idLeague": "5071",
                    "strLeague": "UEFA Europa Conference League",
                    "strLeagueAlternate": "UEFA Conference League",
                    "strSport": "Soccer",
                }
            ]
        }
        if "search_all_leagues.php" in url or "all_leagues.php" in url
        else {
            "events": [
                {
                    "idEvent": "3000001",
                    "idLeague": "5071",
                    "strLeague": "UEFA Europa Conference League",
                    "strHomeTeam": "Fiorentina",
                    "strAwayTeam": "Real Betis",
                    "idHomeTeam": "133832",
                    "idAwayTeam": "133739",
                    "intRound": "1",
                    "intHomeScore": None,
                    "intAwayScore": None,
                    "strTimestamp": "2026-10-01T19:00:00",
                    "dateEvent": "2026-10-01",
                    "strTime": "19:00:00",
                    "strPostponed": "no",
                    "strStatus": "Not Started",
                }
            ]
        }
        if "eventsseason.php" in url
        else {}
    )

    result = seed_single_competition(db_session, league_id=848)
    assert result["status"] == "success"
    uecl = db_session.query(Competition).filter_by(name="UEFA Conference League").first()
    tourney = db_session.query(Tournament).filter_by(competition_id=uecl.id).first()
    stamped = (
        db_session.query(Fixture)
        .filter(Fixture.tournament_id == tourney.id, Fixture.api_id == "tsdb_3000001")
        .one()
    )
    assert stamped.home_team.name == "Fiorentina"
    from backend.crud.mapping import get_external_id_for_competition
    assert get_external_id_for_competition(db_session, uecl.id, "thesportsdb") == "5071"
    leftover = (
        db_session.query(Fixture)
        .filter(Fixture.tournament_id == tourney.id, Fixture.api_id.is_(None))
        .count()
    )
    assert leftover == 0
    tsdb_urls = [call.args[0] for call in mock_tsdb_http.call_args_list]
    assert any("eventsseason.php" in url and "id=5071" in url for url in tsdb_urls)
