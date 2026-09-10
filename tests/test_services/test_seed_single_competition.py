import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from backend.database import Competition, Tournament, Fixture, FixtureOdds
from backend.services.seeder import seed_single_competition, seed_european_cups
import backend.crud.fixture as crud_fixture


def test_seed_single_competition_european_cup(db_session, monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_ORG_KEY", raising=False)
    monkeypatch.delenv("FOOTBALL_DATA_API_KEY", raising=False)
    monkeypatch.delenv("FOOTBALL_DATA_KEY", raising=False)
    result = seed_single_competition(db_session, league_id=2)
    assert result["status"] == "success"
    assert result["league_id"] == 2
    assert "details" in result

    ucl_comp = db_session.query(Competition).filter(Competition.name == "UEFA Champions League").first()
    assert ucl_comp is not None
    assert ucl_comp.api_league_id == 2

    uel_comp = db_session.query(Competition).filter(Competition.name == "UEFA Europa League").first()
    assert uel_comp is None


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
    mock_fetch_fixtures, mock_fetch_teams, db_session, monkeypatch
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
            "Lille",
            home_name="Sporting Clube de Portugal",
            away_name="Lille OSC",
        ),
        _fd_ucl_match(
            9002,
            "2026-09-09T19:00:00Z",
            "Liverpool",
            "Atletico Madrid",
            home_name="Liverpool FC",
            away_name="Club Atlético de Madrid",
        ),
    ]

    seed_european_cups(db_session, target_league_id=2)
    mock_fetch_fixtures.assert_not_called()

    ucl = db_session.query(Competition).filter_by(name="UEFA Champions League").first()
    tourney = db_session.query(Tournament).filter_by(competition_id=ucl.id).first()

    sporting_row = next(
        f
        for f in db_session.query(Fixture).filter_by(tournament_id=tourney.id)
        if f.home_team and f.away_team
        and f.home_team.name == "Sporting CP"
        and f.away_team.name == "Lille"
    )
    odds_before = {
        o.id: (o.odds_home, o.odds_draw, o.odds_away)
        for o in db_session.query(FixtureOdds).filter_by(fixture_id=sporting_row.id)
    }
    playoff_count_before = (
        db_session.query(Fixture)
        .filter(Fixture.tournament_id == tourney.id, Fixture.stage == "Play-offs")
        .count()
    )
    fixture_count_before = db_session.query(Fixture).filter_by(tournament_id=tourney.id).count()

    monkeypatch.setenv("FOOTBALL_DATA_ORG_KEY", "fd-test-key")
    result = seed_single_competition(db_session, league_id=2)
    assert result["status"] == "success"
    mock_fetch_fixtures.assert_called()
    assert mock_fetch_fixtures.call_args[0][0] == "UEFA Champions League"

    db_session.refresh(sporting_row)
    assert sporting_row.api_id == "fd_9001"
    stored = sporting_row.date_utc
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored.isoformat().startswith("2026-09-16T19:00:00")
    assert sporting_row.stage == "League Phase"
    odds_after = {
        o.id: (o.odds_home, o.odds_draw, o.odds_away)
        for o in db_session.query(FixtureOdds).filter_by(fixture_id=sporting_row.id)
    }
    for oid, triple in odds_before.items():
        assert odds_after[oid] == triple

    liverpool = (
        db_session.query(Fixture)
        .filter(Fixture.tournament_id == tourney.id, Fixture.api_id == "fd_9002")
        .one()
    )
    assert liverpool.home_team.name == "Liverpool"
    assert liverpool.away_team.name == "Atlético Madrid"
    liv_dt = liverpool.date_utc
    if liv_dt.tzinfo is None:
        liv_dt = liv_dt.replace(tzinfo=timezone.utc)
    assert liv_dt.date().isoformat() == "2026-09-09"

    yb_villa = next(
        f
        for f in db_session.query(Fixture).filter_by(tournament_id=tourney.id)
        if f.home_team and f.away_team
        and f.home_team.name == "BSC Young Boys"
        and f.away_team.name == "Aston Villa"
    )
    assert yb_villa.api_id is None
    assert yb_villa.status == "Scheduled"

    playoff_count_after = (
        db_session.query(Fixture)
        .filter(Fixture.tournament_id == tourney.id, Fixture.stage == "Play-offs")
        .count()
    )
    assert playoff_count_after == playoff_count_before
    assert db_session.query(Fixture).filter_by(tournament_id=tourney.id).count() == fixture_count_before + 1

    now_utc = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    eligible = crud_fixture.get_eligible_fixtures(db_session, tournament_id=tourney.id, now_utc=now_utc)
    eligible_ids = {f.id for f in eligible}
    assert sporting_row.id in eligible_ids
    assert yb_villa.id not in eligible_ids


@patch("backend.services.seeder.fetch_and_seed_teams")
@patch("backend.services.providers.football_data.FootballDataProvider.fetch_fixtures")
def test_europa_overlay_is_out_of_scope(mock_fetch_fixtures, mock_fetch_teams, db_session, monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_ORG_KEY", "fd-test-key")
    mock_fetch_fixtures.return_value = [{"id": 1}]

    seed_single_competition(db_session, league_id=3)
    mock_fetch_fixtures.assert_not_called()
    uel = db_session.query(Competition).filter_by(name="UEFA Europa League").first()
    tourney = db_session.query(Tournament).filter_by(competition_id=uel.id).first()
    stamped = (
        db_session.query(Fixture)
        .filter(Fixture.tournament_id == tourney.id, Fixture.api_id.isnot(None))
        .count()
    )
    assert stamped == 0
