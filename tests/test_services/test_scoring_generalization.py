import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.database import Team, Tournament, Competition, TournamentTeam, Fixture, FixtureOdds
from backend.scoring import calculate_watchability

def test_weight_presets(db_session: Session):
    # Create mock league and group_knockout competitions
    comp_league = Competition(
        name="Test League",
        type="League",
        format_engine="league",
        relegation_spots=3
    )
    comp_tournament = Competition(
        name="Test Cup",
        type="International",
        format_engine="group_knockout"
    )
    db_session.add(comp_league)
    db_session.add(comp_tournament)
    db_session.flush()

    tourney_l = Tournament(competition_id=comp_league.id, season_name="2026", status="Active")
    tourney_t = Tournament(competition_id=comp_tournament.id, season_name="2026", status="Active")
    db_session.add(tourney_l)
    db_session.add(tourney_t)
    db_session.flush()

    t_home = Team(name="Team A", elo=1600, form_score=60.0)
    t_away = Team(name="Team B", elo=1550, form_score=65.0)
    db_session.add(t_home)
    db_session.add(t_away)
    db_session.flush()

    # Create fixtures
    fixture_l = Fixture(
        tournament_id=tourney_l.id,
        home_team_id=t_home.id,
        away_team_id=t_away.id,
        date_utc=datetime.now(timezone.utc),
        stage="Regular Season",
        matchday_number=10,
        status="Scheduled"
    )
    fixture_t = Fixture(
        tournament_id=tourney_t.id,
        home_team_id=t_home.id,
        away_team_id=t_away.id,
        date_utc=datetime.now(timezone.utc),
        stage="Group Stage",
        status="Scheduled"
    )
    db_session.add(fixture_l)
    db_session.add(fixture_t)
    db_session.flush()

    # Add default odds
    odds_l = FixtureOdds(fixture_id=fixture_l.id, recorded_at=datetime.now(timezone.utc), odds_home=2.0, odds_draw=3.0, odds_away=2.0)
    odds_t = FixtureOdds(fixture_id=fixture_t.id, recorded_at=datetime.now(timezone.utc), odds_home=2.0, odds_draw=3.0, odds_away=2.0)
    db_session.add(odds_l)
    db_session.add(odds_t)
    db_session.flush()

    # Standings for league (needed for standings calculation to avoid empty list index errors)
    tt_home = TournamentTeam(tournament_id=tourney_l.id, team_id=t_home.id, group_name=None, points=20)
    tt_away = TournamentTeam(tournament_id=tourney_l.id, team_id=t_away.id, group_name=None, points=18)
    db_session.add(tt_home)
    db_session.add(tt_away)
    db_session.flush()

    res_l = calculate_watchability(fixture_l, t_home, t_away, db_session)
    res_t = calculate_watchability(fixture_t, t_home, t_away, db_session)

    assert res_l["watchability_score"] > 0
    assert res_t["watchability_score"] > 0
    assert any("Gameweek 10" in r for r in res_l["reasons"])

def test_derby_boost(db_session: Session):
    # Verify that a derby matchup triggers derby boost and correct narrative reason
    comp = Competition(name="Premier League Test", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
    db_session.add(tourney)
    db_session.flush()

    t_ars = Team(name="Arsenal", elo=1800, form_score=70.0)
    t_tot = Team(name="Tottenham", elo=1750, form_score=70.0)
    db_session.add(t_ars)
    db_session.add(t_tot)
    db_session.flush()

    fixture = Fixture(
        tournament_id=tourney.id,
        home_team_id=t_ars.id,
        away_team_id=t_tot.id,
        date_utc=datetime.now(timezone.utc),
        stage="Regular Season",
        matchday_number=12,
        status="Scheduled"
    )
    db_session.add(fixture)
    db_session.flush()

    odds = FixtureOdds(fixture_id=fixture.id, recorded_at=datetime.now(timezone.utc), odds_home=2.0, odds_draw=3.0, odds_away=2.0)
    db_session.add(odds)
    
    tt_ars = TournamentTeam(tournament_id=tourney.id, team_id=t_ars.id, group_name=None, points=30)
    tt_tot = TournamentTeam(tournament_id=tourney.id, team_id=t_tot.id, group_name=None, points=28)
    db_session.add(tt_ars)
    db_session.add(tt_tot)
    db_session.flush()

    res = calculate_watchability(fixture, t_ars, t_tot, db_session)
    assert any("North London Derby" in r for r in res["reasons"])
