from datetime import datetime, timezone
import pytest
from backend.database import Team, Fixture, Competition, Tournament, TournamentTeam
from backend.services.standings import (
    calculate_standings,
    calculate_points_needed_to_guarantee_top_2,
    recalculate_tournament_team_standings,
    recalculate_team_streaks,
    recalculate_standings
)

def test_calculate_standings(db_session):
    comp = Competition(name="World Cup Standings Test", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()

    # Setup teams in Group A
    t1 = Team(name="Germany", elo=1900, form_score=80.0, win_streak=1)
    t2 = Team(name="Scotland", elo=1650, form_score=50.0, win_streak=0)
    db_session.add_all([t1, t2])
    db_session.flush()

    tt1 = TournamentTeam(tournament_id=tourney.id, team_id=t1.id, group_name="A")
    tt2 = TournamentTeam(tournament_id=tourney.id, team_id=t2.id, group_name="A")
    db_session.add_all([tt1, tt2])
    db_session.flush()
    
    # Finished fixture
    f1 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        status="Finished",
        home_score=3,
        away_score=1,
        date_utc=datetime.fromisoformat("2026-06-11T20:00:00")
    )
    db_session.add(f1)
    db_session.commit()
    
    # Run standings calculation
    standings = calculate_standings(db_session, "A")
    
    # Asserts
    assert len(standings) == 2
    assert standings[0]["name"] == "Germany"
    assert standings[0]["played"] == 1
    assert standings[0]["won"] == 1
    assert standings[0]["goals_for"] == 3
    assert standings[0]["goals_against"] == 1
    assert standings[0]["goal_difference"] == 2
    assert standings[0]["points"] == 3
    
    assert standings[1]["name"] == "Scotland"
    assert standings[1]["played"] == 1
    assert standings[1]["lost"] == 1
    assert standings[1]["goals_for"] == 1
    assert standings[1]["goals_against"] == 3
    assert standings[1]["goal_difference"] == -2
    assert standings[1]["points"] == 0


def test_calculate_points_needed_to_guarantee_top_2(db_session):
    comp = Competition(name="World Cup Guarantee Test", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()

    # Setup 4 teams in Group B
    t1 = Team(name="Argentina", elo=2000)
    t2 = Team(name="Mexico", elo=1750)
    t3 = Team(name="Poland", elo=1700)
    t4 = Team(name="Saudi Arabia", elo=1550)
    db_session.add_all([t1, t2, t3, t4])
    db_session.flush()

    db_session.add_all([
        TournamentTeam(tournament_id=tourney.id, team_id=t1.id, group_name="B"),
        TournamentTeam(tournament_id=tourney.id, team_id=t2.id, group_name="B"),
        TournamentTeam(tournament_id=tourney.id, team_id=t3.id, group_name="B"),
        TournamentTeam(tournament_id=tourney.id, team_id=t4.id, group_name="B"),
    ])
    db_session.flush()
    
    f_list = [
        Fixture(tournament_id=tourney.id, home_team_id=t1.id, away_team_id=t2.id, stage="Group Stage", status="Scheduled", date_utc=datetime.now(timezone.utc)),
        Fixture(tournament_id=tourney.id, home_team_id=t3.id, away_team_id=t4.id, stage="Group Stage", status="Scheduled", date_utc=datetime.now(timezone.utc)),
        Fixture(tournament_id=tourney.id, home_team_id=t1.id, away_team_id=t3.id, stage="Group Stage", status="Scheduled", date_utc=datetime.now(timezone.utc)),
        Fixture(tournament_id=tourney.id, home_team_id=t2.id, away_team_id=t4.id, stage="Group Stage", status="Scheduled", date_utc=datetime.now(timezone.utc)),
        Fixture(tournament_id=tourney.id, home_team_id=t1.id, away_team_id=t4.id, stage="Group Stage", status="Scheduled", date_utc=datetime.now(timezone.utc)),
        Fixture(tournament_id=tourney.id, home_team_id=t2.id, away_team_id=t3.id, stage="Group Stage", status="Scheduled", date_utc=datetime.now(timezone.utc)),
    ]
    db_session.add_all(f_list)
    db_session.commit()
    
    pts_needed = calculate_points_needed_to_guarantee_top_2(db_session, "Argentina", "B")
    assert pts_needed == 7


def test_recalculate_tournament_team_standings(db_session):
    # Setup Competition & Tournament
    comp = Competition(name="Custom Standings League Test", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()
    
    tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
    db_session.add(tourney)
    db_session.flush()
    
    # Setup Teams
    t1 = Team(name="Team A", elo=1500)
    t2 = Team(name="Team B", elo=1500)
    db_session.add_all([t1, t2])
    db_session.flush()
    
    # Setup TournamentTeam associations
    tt1 = TournamentTeam(tournament_id=tourney.id, team_id=t1.id, points=0)
    tt2 = TournamentTeam(tournament_id=tourney.id, team_id=t2.id, points=0)
    db_session.add_all([tt1, tt2])
    db_session.flush()
    
    # Add Finished Fixture
    f = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        date_utc=datetime.now(timezone.utc),
        stage="Regular Season",
        status="Finished",
        home_score=3,
        away_score=1
    )
    db_session.add(f)
    db_session.commit()
    
    # Recalculate standings cache and streaks
    recalculate_standings(db_session, tourney.id)
    
    # Refresh cache from DB
    db_session.refresh(tt1)
    db_session.refresh(tt2)
    
    assert tt1.points == 3
    assert tt1.wins == 1
    assert tt1.goals_for == 3
    assert tt1.goals_against == 1
    
    assert tt2.points == 0
    assert tt2.losses == 1
    assert tt2.goals_for == 1
    assert tt2.goals_against == 3

    # Assert streaks updated on Team records
    db_session.refresh(t1)
    db_session.refresh(t2)
    assert t1.win_streak == 1
    assert t2.loss_streak == 1
