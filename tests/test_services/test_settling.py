from datetime import datetime, timezone
from backend.database import Team, Fixture, Competition, Tournament
from backend.services.settling import settle_result, update_team_streaks

def _setup_tournament(db_session):
    comp = Competition(name="Test Competition", type="International")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
    db_session.add(tourney)
    db_session.flush()
    return tourney

def test_settle_result_home_win(db_session):
    tourney = _setup_tournament(db_session)

    t1 = Team(name="Team A", elo=1500, win_streak=0, draw_streak=0, loss_streak=0)
    t2 = Team(name="Team B", elo=1500, win_streak=0, draw_streak=0, loss_streak=0)
    db_session.add_all([t1, t2])
    db_session.flush()

    fixture = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        status="Scheduled",
        date_utc=datetime.now(timezone.utc)
    )
    fixture.home_team = t1
    fixture.away_team = t2
    db_session.add(fixture)
    db_session.flush()

    settle_result(fixture, 2, 1)

    assert fixture.status == "Finished"
    assert fixture.home_score == 2
    assert fixture.away_score == 1
    assert fixture.winner_id == t1.id
    assert t1.win_streak == 1
    assert t1.loss_streak == 0
    assert t2.loss_streak == 1
    assert t2.win_streak == 0

def test_settle_result_away_win(db_session):
    tourney = _setup_tournament(db_session)

    t1 = Team(name="Team C", elo=1500, win_streak=0, draw_streak=0, loss_streak=0)
    t2 = Team(name="Team D", elo=1500, win_streak=0, draw_streak=0, loss_streak=0)
    db_session.add_all([t1, t2])
    db_session.flush()

    fixture = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        status="Scheduled",
        date_utc=datetime.now(timezone.utc)
    )
    fixture.home_team = t1
    fixture.away_team = t2
    db_session.add(fixture)
    db_session.flush()

    settle_result(fixture, 0, 3)

    assert fixture.status == "Finished"
    assert fixture.home_score == 0
    assert fixture.away_score == 3
    assert fixture.winner_id == t2.id
    assert t2.win_streak == 1
    assert t1.loss_streak == 1

def test_settle_result_draw(db_session):
    tourney = _setup_tournament(db_session)

    t1 = Team(name="Team E", elo=1500, win_streak=1, draw_streak=0, loss_streak=0)
    t2 = Team(name="Team F", elo=1500, win_streak=2, draw_streak=0, loss_streak=0)
    db_session.add_all([t1, t2])
    db_session.flush()

    fixture = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        status="Scheduled",
        date_utc=datetime.now(timezone.utc)
    )
    fixture.home_team = t1
    fixture.away_team = t2
    db_session.add(fixture)
    db_session.flush()

    settle_result(fixture, 1, 1)

    assert fixture.status == "Finished"
    assert fixture.home_score == 1
    assert fixture.away_score == 1
    assert fixture.winner_id is None
    assert t1.draw_streak == 1
    assert t1.win_streak == 0
    assert t2.draw_streak == 1
    assert t2.win_streak == 0

def test_settle_result_none_scores(db_session):
    tourney = _setup_tournament(db_session)

    t1 = Team(name="Team G", elo=1500, win_streak=1, draw_streak=0, loss_streak=0)
    t2 = Team(name="Team H", elo=1500, win_streak=2, draw_streak=0, loss_streak=0)
    db_session.add_all([t1, t2])
    db_session.flush()

    fixture = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        home_team_placeholder="Winner Match 1",
        away_team_placeholder="Winner Match 2",
        stage="Round of 16",
        status="Scheduled",
        date_utc=datetime.now(timezone.utc)
    )
    fixture.home_team = t1
    fixture.away_team = t2
    db_session.add(fixture)
    db_session.flush()

    # Settle without scores (e.g. edge case or pending score feed)
    settle_result(fixture, None, None)

    assert fixture.status == "Finished"
    assert fixture.home_score is None
    assert fixture.away_score is None
    assert fixture.winner_id is None
    assert fixture.home_team_placeholder is None
    assert fixture.away_team_placeholder is None

