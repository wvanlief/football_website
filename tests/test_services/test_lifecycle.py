"""Tests for backend.services.lifecycle.finish_fixture.

Verifies that finish_fixture atomically performs all three post-match steps:
1. Settlement  — scores, status, winner, team streaks (via settle_result)
2. Watchability — watchability_score is non-None after the call (via update_fixture_score)
3. Standings   — TournamentTeam standings cache is updated (via recalculate_tournament_team_standings)
"""

from datetime import datetime, timezone

import pytest

from backend.database import (
    Competition,
    Fixture,
    FixtureOdds,
    Team,
    Tournament,
    TournamentTeam,
)
from backend.services.lifecycle import finish_fixture


# ---------------------------------------------------------------------------
# Fixtures (pytest)
# ---------------------------------------------------------------------------

def _make_competition(db, name="Test League", format_engine="league"):
    comp = Competition(name=name, type="League", format_engine=format_engine)
    db.add(comp)
    db.flush()
    return comp


def _make_tournament(db, comp):
    tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
    db.add(tourney)
    db.flush()
    return tourney


def _make_team(db, name, elo=1500):
    team = Team(name=name, elo=elo, form_score=50.0, win_streak=0, draw_streak=0, loss_streak=0)
    db.add(team)
    db.flush()
    return team


def _make_fixture(db, tourney, home_team, away_team, stage="Regular Season"):
    f = Fixture(
        tournament_id=tourney.id,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        stage=stage,
        status="Scheduled",
        date_utc=datetime.now(timezone.utc),
    )
    f.home_team = home_team
    f.away_team = away_team
    db.add(f)
    db.flush()
    # Minimal odds so watchability can be calculated without crashing
    odds = FixtureOdds(
        fixture_id=f.id,
        recorded_at=datetime.now(timezone.utc),
        odds_home=2.0,
        odds_draw=3.4,
        odds_away=3.5,
    )
    db.add(odds)
    db.flush()
    return f


def _register_teams(db, tourney, *teams, group_name="A"):
    for team in teams:
        tt = TournamentTeam(
            tournament_id=tourney.id,
            team_id=team.id,
            group_name=group_name,
        )
        db.add(tt)
    db.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFinishFixtureSettlement:
    """Step 1: scores, status, winner, team streaks."""

    def test_home_win_settled_correctly(self, db_session):
        comp = _make_competition(db_session)
        tourney = _make_tournament(db_session, comp)
        home = _make_team(db_session, "Alpha FC")
        away = _make_team(db_session, "Beta FC")
        _register_teams(db_session, tourney, home, away)
        fixture = _make_fixture(db_session, tourney, home, away)

        finish_fixture(fixture, 3, 1, db_session)

        assert fixture.status == "Finished"
        assert fixture.home_score == 3
        assert fixture.away_score == 1
        assert fixture.winner_id == home.id
        assert home.win_streak == 1
        assert home.loss_streak == 0
        assert away.loss_streak == 1
        assert away.win_streak == 0

    def test_away_win_settled_correctly(self, db_session):
        comp = _make_competition(db_session)
        tourney = _make_tournament(db_session, comp)
        home = _make_team(db_session, "Gamma FC")
        away = _make_team(db_session, "Delta FC")
        _register_teams(db_session, tourney, home, away)
        fixture = _make_fixture(db_session, tourney, home, away)

        finish_fixture(fixture, 0, 2, db_session)

        assert fixture.status == "Finished"
        assert fixture.winner_id == away.id
        assert away.win_streak == 1
        assert home.loss_streak == 1

    def test_draw_settled_correctly(self, db_session):
        comp = _make_competition(db_session)
        tourney = _make_tournament(db_session, comp)
        home = _make_team(db_session, "Epsilon FC")
        away = _make_team(db_session, "Zeta FC")
        _register_teams(db_session, tourney, home, away)
        fixture = _make_fixture(db_session, tourney, home, away)

        finish_fixture(fixture, 1, 1, db_session)

        assert fixture.status == "Finished"
        assert fixture.winner_id is None
        assert home.draw_streak == 1
        assert away.draw_streak == 1
        assert home.win_streak == 0
        assert away.win_streak == 0


class TestFinishFixtureWatchability:
    """Step 2: watchability score is populated after the call."""

    def test_watchability_score_set(self, db_session):
        comp = _make_competition(db_session)
        tourney = _make_tournament(db_session, comp)
        home = _make_team(db_session, "Eta FC", elo=1600)
        away = _make_team(db_session, "Theta FC", elo=1580)
        _register_teams(db_session, tourney, home, away)
        fixture = _make_fixture(db_session, tourney, home, away)

        # Default before settlement is 0.0 (column default)
        finish_fixture(fixture, 2, 0, db_session)

        # After settlement the score must be a genuine calculated value > 0
        assert fixture.watchability_score is not None
        assert fixture.watchability_score > 0.0
        assert fixture.watchability_score <= 100.0

    def test_watchability_set_even_on_draw(self, db_session):
        comp = _make_competition(db_session)
        tourney = _make_tournament(db_session, comp)
        home = _make_team(db_session, "Iota FC")
        away = _make_team(db_session, "Kappa FC")
        _register_teams(db_session, tourney, home, away)
        fixture = _make_fixture(db_session, tourney, home, away)

        finish_fixture(fixture, 0, 0, db_session)

        assert fixture.watchability_score is not None


class TestFinishFixtureStandings:
    """Step 3: TournamentTeam standings cache reflects the result."""

    def test_standings_updated_after_home_win(self, db_session):
        comp = _make_competition(db_session)
        tourney = _make_tournament(db_session, comp)
        home = _make_team(db_session, "Lambda FC")
        away = _make_team(db_session, "Mu FC")
        _register_teams(db_session, tourney, home, away)
        fixture = _make_fixture(db_session, tourney, home, away)

        finish_fixture(fixture, 2, 1, db_session)

        home_tt = db_session.query(TournamentTeam).filter_by(
            tournament_id=tourney.id, team_id=home.id
        ).one()
        away_tt = db_session.query(TournamentTeam).filter_by(
            tournament_id=tourney.id, team_id=away.id
        ).one()

        assert home_tt.points == 3
        assert home_tt.wins == 1
        assert away_tt.points == 0
        assert away_tt.losses == 1

    def test_standings_updated_after_draw(self, db_session):
        comp = _make_competition(db_session)
        tourney = _make_tournament(db_session, comp)
        home = _make_team(db_session, "Nu FC")
        away = _make_team(db_session, "Xi FC")
        _register_teams(db_session, tourney, home, away)
        fixture = _make_fixture(db_session, tourney, home, away)

        finish_fixture(fixture, 1, 1, db_session)

        home_tt = db_session.query(TournamentTeam).filter_by(
            tournament_id=tourney.id, team_id=home.id
        ).one()
        away_tt = db_session.query(TournamentTeam).filter_by(
            tournament_id=tourney.id, team_id=away.id
        ).one()

        assert home_tt.points == 1
        assert home_tt.draws == 1
        assert away_tt.points == 1
        assert away_tt.draws == 1

    def test_update_standings_false_skips_cache(self, db_session):
        """Batch ingestion path: standings cache not updated per-fixture."""
        comp = _make_competition(db_session)
        tourney = _make_tournament(db_session, comp)
        home = _make_team(db_session, "Omicron FC")
        away = _make_team(db_session, "Pi FC")
        _register_teams(db_session, tourney, home, away)
        fixture = _make_fixture(db_session, tourney, home, away)

        finish_fixture(fixture, 3, 0, db_session, update_standings=False)

        home_tt = db_session.query(TournamentTeam).filter_by(
            tournament_id=tourney.id, team_id=home.id
        ).one()
        # Points cache should still be 0 — caller recalculates after the batch
        assert home_tt.points == 0
        # But settlement and watchability still happened
        assert fixture.status == "Finished"
        assert fixture.watchability_score is not None


class TestFinishFixtureAtomicity:
    """All three steps happen in a single call — no partial state."""

    def test_all_three_steps_in_one_call(self, db_session):
        comp = _make_competition(db_session)
        tourney = _make_tournament(db_session, comp)
        home = _make_team(db_session, "Rho FC", elo=1650)
        away = _make_team(db_session, "Sigma FC", elo=1620)
        _register_teams(db_session, tourney, home, away)
        fixture = _make_fixture(db_session, tourney, home, away)

        finish_fixture(fixture, 2, 2, db_session)

        # Settlement
        assert fixture.status == "Finished"
        assert fixture.home_score == 2
        assert fixture.away_score == 2
        assert home.draw_streak == 1
        assert away.draw_streak == 1

        # Watchability
        assert fixture.watchability_score is not None

        # Standings
        home_tt = db_session.query(TournamentTeam).filter_by(
            tournament_id=tourney.id, team_id=home.id
        ).one()
        assert home_tt.points == 1

    def test_rollback_discards_all_three_steps(self, db_session):
        """If the session is rolled back after finish_fixture, none of the changes persist."""
        comp = _make_competition(db_session)
        tourney = _make_tournament(db_session, comp)
        home = _make_team(db_session, "Tau FC", elo=1700)
        away = _make_team(db_session, "Upsilon FC", elo=1680)
        _register_teams(db_session, tourney, home, away)
        fixture = _make_fixture(db_session, tourney, home, away)
        db_session.commit()

        # Capture initial state
        initial_status = fixture.status
        initial_home_score = fixture.home_score
        initial_away_score = fixture.away_score
        initial_home_win_streak = home.win_streak
        initial_away_loss_streak = away.loss_streak
        initial_watchability = fixture.watchability_score

        home_tt = db_session.query(TournamentTeam).filter_by(
            tournament_id=tourney.id, team_id=home.id
        ).one()
        initial_home_points = home_tt.points

        # Call finish_fixture then rollback
        finish_fixture(fixture, 3, 1, db_session)
        db_session.rollback()

        # Re-fetch from DB to confirm nothing persisted
        db_session.expire_all()
        fixture_refetch = db_session.query(Fixture).filter_by(id=fixture.id).one()
        home_refetch = db_session.query(Team).filter_by(id=home.id).one()
        away_refetch = db_session.query(Team).filter_by(id=away.id).one()
        home_tt_refetch = db_session.query(TournamentTeam).filter_by(
            tournament_id=tourney.id, team_id=home.id
        ).one()

        # Settlement changes should NOT persist
        assert fixture_refetch.status == initial_status
        assert fixture_refetch.home_score == initial_home_score
        assert fixture_refetch.away_score == initial_away_score
        assert home_refetch.win_streak == initial_home_win_streak
        assert away_refetch.loss_streak == initial_away_loss_streak

        # Watchability changes should NOT persist
        assert fixture_refetch.watchability_score == initial_watchability

        # Standings cache changes should NOT persist
        assert home_tt_refetch.points == initial_home_points
