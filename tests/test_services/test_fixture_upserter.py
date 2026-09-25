from datetime import datetime, timezone
from backend.database import Competition, Tournament, Fixture, FixtureOdds, TournamentTeam, Team
from backend.services.ingestion.fixture_upserter import FixtureUpserter


def test_upsert_creates_new_fixture(db_session):
    """Upserting a brand-new fixture payload creates a Fixture and default FixtureOdds."""
    comp = Competition(name="Premier League Test", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.commit()

    upserter = FixtureUpserter()
    now_utc = datetime.now(timezone.utc)

    payload = {
        "api_id": "api_1001",
        "home_team_name": "Arsenal",
        "away_team_name": "Chelsea",
        "date_utc": now_utc,
        "stage": "Regular Season",
        "status": "Scheduled"
    }

    fixture, is_created = upserter.upsert_fixture(db_session, tourney, payload)
    db_session.commit()

    assert is_created is True
    assert fixture.api_id == "api_1001"
    assert fixture.home_team.name == "Arsenal"
    assert fixture.away_team.name == "Chelsea"

    odds = db_session.query(FixtureOdds).filter_by(fixture_id=fixture.id).all()
    assert len(odds) == 1

    tt_list = db_session.query(TournamentTeam).filter_by(tournament_id=tourney.id).all()
    assert len(tt_list) == 2


def test_upsert_updates_existing_fixture(db_session):
    """Upserting an existing fixture updates attributes without creating a duplicate Fixture."""
    comp = Competition(name="La Liga Test", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.commit()

    upserter = FixtureUpserter()
    now_utc = datetime.now(timezone.utc)

    payload = {
        "api_id": "api_2001",
        "home_team_name": "Real Madrid",
        "away_team_name": "Barcelona",
        "date_utc": now_utc,
        "stage": "Regular Season",
        "status": "Scheduled"
    }

    f1, is_created1 = upserter.upsert_fixture(db_session, tourney, payload)
    db_session.commit()
    assert is_created1 is True

    updated_payload = {
        "api_id": "api_2001",
        "home_team_name": "Real Madrid",
        "away_team_name": "Barcelona",
        "date_utc": now_utc,
        "stage": "Regular Season",
        "status": "Finished",
        "home_score": 3,
        "away_score": 1
    }

    f2, is_created2 = upserter.upsert_fixture(db_session, tourney, updated_payload)
    db_session.commit()

    assert is_created2 is False
    assert f1.id == f2.id
    assert f2.status == "Finished"
    assert f2.home_score == 3
    assert f2.away_score == 1
    assert f2.winner_id == f2.home_team_id


def test_odds_date_deduplication(db_session):
    """Re-running fixture upserts on the same day skips duplicate FixtureOdds creation."""
    comp = Competition(name="Serie A Test", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.commit()

    upserter = FixtureUpserter()
    now_utc = datetime.now(timezone.utc)

    payload = {
        "api_id": "api_3001",
        "home_team_name": "Juventus",
        "away_team_name": "Inter Milan",
        "date_utc": now_utc,
        "stage": "Regular Season",
        "status": "Scheduled"
    }

    fixture, _ = upserter.upsert_fixture(db_session, tourney, payload)
    db_session.commit()

    upserter.upsert_fixture(db_session, tourney, payload)
    db_session.commit()

    odds_entries = db_session.query(FixtureOdds).filter_by(fixture_id=fixture.id).all()
    assert len(odds_entries) == 1


def test_upsert_stamps_unique_pairing_without_changing_teams(db_session):
    """A unique home/away row is stamped even when the kickoff is outside the ±12h window."""
    comp = Competition(name="UCL Overlay Match", type="Cup", format_engine="league_phase_knockout")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    home = Team(name="Liverpool", team_type="Club")
    away = Team(name="Atlético Madrid", team_type="Club")
    db_session.add_all([home, away])
    db_session.flush()

    original = Fixture(
        tournament_id=tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        date_utc=datetime(2026, 9, 17, 18, 45, tzinfo=timezone.utc),
        stage="League Phase",
        status="Scheduled",
        watchability_score=88.0,
    )
    db_session.add(original)
    db_session.commit()

    upserter = FixtureUpserter()
    fixture, created = upserter.upsert_fixture(
        db_session,
        tourney,
        {
            "api_id": "fd_9002",
            "home_team": home,
            "away_team": away,
            "date_utc": datetime(2026, 9, 9, 19, 0, tzinfo=timezone.utc),
            "stage": "League Phase",
            "matchday_number": 1,
            "status": "Scheduled",
        },
        competition=comp,
    )
    db_session.commit()

    assert created is False
    assert fixture.id == original.id
    assert fixture.api_id == "fd_9002"
    assert fixture.home_team_id == home.id
    assert fixture.away_team_id == away.id
    stored = fixture.date_utc
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored == datetime(2026, 9, 9, 19, 0, tzinfo=timezone.utc)
    assert fixture.watchability_score == 88.0
    assert fixture.matchday_number == 1
    assert db_session.query(Fixture).filter_by(tournament_id=tourney.id).count() == 1


def test_upsert_does_not_change_home_or_away_on_existing_row(db_session):
    comp = Competition(name="UCL Overlay Teams Locked", type="Cup", format_engine="league_phase_knockout")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    home = Team(name="Liverpool", team_type="Club")
    away = Team(name="Atlético Madrid", team_type="Club")
    other = Team(name="Real Madrid", team_type="Club")
    db_session.add_all([home, away, other])
    db_session.flush()

    original = Fixture(
        tournament_id=tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        date_utc=datetime(2026, 9, 9, 19, 0, tzinfo=timezone.utc),
        stage="League Phase",
        status="Scheduled",
        api_id="fd_9002",
        home_score=2,
        away_score=1,
        watchability_score=91.0,
    )
    db_session.add(original)
    db_session.flush()
    odds = FixtureOdds(
        fixture_id=original.id,
        recorded_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        odds_home=1.9,
        odds_draw=3.5,
        odds_away=4.0,
    )
    db_session.add(odds)
    db_session.commit()

    upserter = FixtureUpserter()
    fixture, created = upserter.upsert_fixture(
        db_session,
        tourney,
        {
            "api_id": "fd_9002",
            "home_team": other,
            "away_team": home,
            "date_utc": datetime(2026, 9, 9, 19, 0, tzinfo=timezone.utc),
            "stage": "League Phase",
            "matchday_number": 1,
            "status": "Scheduled",
        },
        competition=comp,
    )
    db_session.commit()

    assert created is False
    assert fixture.home_team_id == home.id
    assert fixture.away_team_id == away.id
    assert fixture.home_score == 2
    assert fixture.away_score == 1
    assert fixture.watchability_score == 91.0
    kept_odds = db_session.query(FixtureOdds).filter_by(id=odds.id).one()
    assert (kept_odds.odds_home, kept_odds.odds_draw, kept_odds.odds_away) == (1.9, 3.5, 4.0)


def test_unique_pairing_updates_when_kickoff_and_stage_drift(db_session):
    """A single home/away row is updated even when kickoff moved by days and stage differs."""
    comp = Competition(name="UEL Unique Pairing", type="Cup", format_engine="league_phase_knockout")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    home = Team(name="Roma", team_type="Club")
    away = Team(name="Sporting CP", team_type="Club")
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

    fixture, created = FixtureUpserter().upsert_fixture(
        db_session,
        tourney,
        {
            "api_id": "fd_88001",
            "home_team": home,
            "away_team": away,
            "date_utc": datetime(2026, 9, 24, 19, 0, tzinfo=timezone.utc),
            "stage": "League Phase",
            "status": "Scheduled",
        },
        competition=comp,
    )
    db_session.commit()

    assert created is False
    assert fixture.id == original.id
    assert fixture.api_id == "fd_88001"
    assert fixture.stage == "League Phase"
    stored = fixture.date_utc
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored == datetime(2026, 9, 24, 19, 0, tzinfo=timezone.utc)
    assert db_session.query(Fixture).filter_by(tournament_id=tourney.id).count() == 1


def test_multiple_legs_outside_window_insert_a_second_row(db_session):
    """Two existing legs of the same pairing stay distinct; a far kickoff inserts."""
    comp = Competition(name="UEL Two Legs", type="Cup", format_engine="league_phase_knockout")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    home = Team(name="Ajax", team_type="Club")
    away = Team(name="Benfica", team_type="Club")
    db_session.add_all([home, away])
    db_session.flush()
    db_session.add_all([
        Fixture(
            tournament_id=tourney.id,
            home_team_id=home.id,
            away_team_id=away.id,
            date_utc=datetime(2026, 9, 17, 19, 0, tzinfo=timezone.utc),
            stage="League Phase",
            status="Scheduled",
            api_id="fd_1",
        ),
        Fixture(
            tournament_id=tourney.id,
            home_team_id=home.id,
            away_team_id=away.id,
            date_utc=datetime(2026, 10, 1, 19, 0, tzinfo=timezone.utc),
            stage="League Phase",
            status="Scheduled",
            api_id="fd_2",
        ),
    ])
    db_session.commit()

    _, created = FixtureUpserter().upsert_fixture(
        db_session,
        tourney,
        {
            "api_id": "fd_3",
            "home_team": home,
            "away_team": away,
            "date_utc": datetime(2026, 11, 5, 20, 0, tzinfo=timezone.utc),
            "stage": "League Phase",
            "status": "Scheduled",
        },
        competition=comp,
    )
    db_session.commit()

    assert created is True
    assert db_session.query(Fixture).filter_by(tournament_id=tourney.id).count() == 3
