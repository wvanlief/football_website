"""Report-only hygiene checks. The job must not mutate rows."""
from datetime import datetime
from pathlib import Path

from sqlalchemy import func

from backend.database import Competition, Fixture, FixtureOdds, Team, Tournament
from backend.services.hygiene import build_hygiene_report, run_hygiene_report


def _comp(db, name, kind="League"):
    row = Competition(name=name, type=kind, format_engine="league")
    db.add(row)
    db.flush()
    return row


def _tourney(db, comp, season, status="Active"):
    row = Tournament(competition_id=comp.id, season_name=season, status=status)
    db.add(row)
    db.flush()
    return row


def _team(db, name):
    row = Team(name=name, country_code="XX")
    db.add(row)
    db.flush()
    return row


def _fixture(db, tournament, home, away, day, status="Scheduled", api_id=None):
    row = Fixture(
        tournament_id=tournament.id,
        home_team_id=home.id,
        away_team_id=away.id,
        date_utc=datetime.fromisoformat(day + "T15:00:00"),
        stage="League Phase",
        status=status,
        api_id=api_id,
    )
    db.add(row)
    db.flush()
    return row


def _ids(db):
    return [row[0] for row in db.query(Fixture.id).order_by(Fixture.id).all()]


def test_split_season_pair_is_reported_and_rows_stay(db_session):
    comp = _comp(db_session, "Belgian Pro League")
    legacy = _tourney(db_session, comp, "2026")
    current = _tourney(db_session, comp, "2026/27")
    home, away = _team(db_session, "Club Brugge"), _team(db_session, "Anderlecht")
    other = _team(db_session, "Genk")
    _fixture(db_session, legacy, home, away, "2026-08-01")
    _fixture(db_session, current, home, away, "2026-08-01")
    _fixture(db_session, current, home, other, "2026-08-08")
    before = _ids(db_session)

    report = build_hygiene_report(db_session)

    assert _ids(db_session) == before
    assert not db_session.dirty
    assert not db_session.deleted
    splits = report["split_seasons"]
    assert len(splits) == 1
    assert splits[0]["competition"] == "Belgian Pro League"
    assert {row["season_name"] for row in splits[0]["tournaments"]} == {"2026", "2026/27"}
    assert splits[0]["shared_pairings"][0]["date"] == "2026-08-01"
    source = (Path(__file__).resolve().parents[2] / "backend" / "services" / "hygiene.py").read_text(encoding="utf-8")
    assert "2026" not in source
    assert "--execute" not in source


def test_duplicate_pairing_names_authoritative_row(db_session):
    comp = _comp(db_session, "Premier League")
    tourney = _tourney(db_session, comp, "2026/27")
    home, away = _team(db_session, "Arsenal"), _team(db_session, "Chelsea")
    scheduled = _fixture(db_session, tourney, home, away, "2026-09-12", status="Scheduled")
    finished = _fixture(db_session, tourney, home, away, "2026-09-12", status="Finished", api_id="fd_1")
    db_session.add(FixtureOdds(
        fixture_id=finished.id,
        recorded_at=datetime(2026, 9, 1),
        odds_home=1.8,
        odds_draw=3.4,
        odds_away=4.2,
    ))
    db_session.flush()
    before = _ids(db_session)

    report = build_hygiene_report(db_session)

    assert _ids(db_session) == before
    dupes = report["duplicate_fixtures"]
    assert len(dupes) == 1
    assert dupes[0]["authoritative_fixture_id"] == finished.id
    assert "Finished" in dupes[0]["authoritative_because"]
    assert "has odds" in dupes[0]["authoritative_because"]
    assert {row["id"] for row in dupes[0]["rows"]} == {scheduled.id, finished.id}


def test_world_cup_dated_row_on_a_domestic_cup(db_session):
    world_cup = _comp(db_session, "FIFA World Cup", kind="International")
    fa_cup = _comp(db_session, "FA Cup", kind="Cup")
    wc_tourney = _tourney(db_session, world_cup, "2026")
    cup_tourney = _tourney(db_session, fa_cup, "2026")
    mexico, canada = _team(db_session, "Mexico"), _team(db_session, "Canada")
    arsenal, chelsea = _team(db_session, "Arsenal WC"), _team(db_session, "Chelsea WC")
    _fixture(db_session, wc_tourney, mexico, canada, "2026-06-11")
    _fixture(db_session, wc_tourney, canada, mexico, "2026-07-19")
    inside = _fixture(db_session, cup_tourney, arsenal, chelsea, "2026-06-15")
    outside = _fixture(db_session, cup_tourney, chelsea, arsenal, "2026-05-01")
    before_count = db_session.query(func.count(Fixture.id)).scalar()

    report = build_hygiene_report(db_session)

    assert db_session.query(func.count(Fixture.id)).scalar() == before_count
    section = report["world_cup_dates_on_other_tournaments"]
    assert section["window_start"] == "2026-06-11"
    assert section["window_end"] == "2026-07-19"
    assert [row["fixture_id"] for row in section["rows"]] == [inside.id]
    assert outside.id not in [row["fixture_id"] for row in section["rows"]]


def test_empty_database_report_is_clean(db_session):
    report = build_hygiene_report(db_session)
    assert report["split_seasons"] == []
    assert report["duplicate_fixtures"] == []
    assert report["world_cup_dates_on_other_tournaments"]["rows"] == []
    assert report["european_cup_leftovers"]["total"] == 0
    note = report["european_cup_leftovers"]["note"]
    assert "#145" in note
    assert "delete" not in note.lower()


def test_european_leftover_count_excludes_stamped_twins(db_session):
    comp = _comp(db_session, "UEFA Champions League", kind="Cup")
    tourney = _tourney(db_session, comp, "2026/27")
    home, away = _team(db_session, "Barcelona"), _team(db_session, "Aston Villa")
    other_home, other_away = _team(db_session, "Liverpool"), _team(db_session, "Atletico")
    _fixture(db_session, tourney, home, away, "2026-11-03", api_id=None)
    _fixture(db_session, tourney, other_home, other_away, "2026-09-09", api_id=None)
    _fixture(db_session, tourney, other_home, other_away, "2026-09-09", api_id="fd_575331", status="Finished")

    report = build_hygiene_report(db_session)

    leftovers = report["european_cup_leftovers"]
    assert leftovers["counts"]["UEFA Champions League"] == 1
    assert leftovers["total"] == 1
    assert "delete" not in leftovers["note"].lower()


def test_run_writes_report_file_only(db_session, tmp_path):
    before = _ids(db_session)
    path = tmp_path / "hygiene_report.json"
    report = run_hygiene_report(db_session, report_path=path)
    assert path.is_file()
    assert report["split_seasons"] == []
    assert _ids(db_session) == before


def test_hygiene_report_does_not_mutate_local_replica(replica_db):
    before_count = replica_db.query(func.count(Fixture.id)).scalar()
    before_ids = _ids(replica_db)
    report = build_hygiene_report(replica_db)
    assert replica_db.query(func.count(Fixture.id)).scalar() == before_count
    assert _ids(replica_db) == before_ids
    assert not replica_db.new
    assert not replica_db.dirty
    assert not replica_db.deleted
    assert "split_seasons" in report
