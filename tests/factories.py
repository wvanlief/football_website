"""Shared builders for league, cup, and fixture rows.

Date-window tests pass ``FROZEN_NOW`` into eligibility, feed building, and
grouping so the window does not move at midnight or across a DST change.
"""
from datetime import datetime, timedelta, timezone

from backend.database import Competition, Fixture, Team, Tournament, TournamentTeam

FROZEN_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


def league(db, name="Premier League", **kwargs):
    row = Competition(
        name=name,
        type=kwargs.pop("type", "League"),
        format_engine=kwargs.pop("format_engine", "league"),
        **kwargs,
    )
    db.add(row)
    db.flush()
    return row


def cup(db, name="FA Cup", **kwargs):
    row = Competition(
        name=name,
        type=kwargs.pop("type", "Cup"),
        format_engine=kwargs.pop("format_engine", "cup"),
        **kwargs,
    )
    db.add(row)
    db.flush()
    return row


def tournament(db, competition, season="2026/27", status="Active"):
    row = Tournament(competition_id=competition.id, season_name=season, status=status)
    db.add(row)
    db.flush()
    return row


def team(db, name, elo=1500):
    row = Team(name=name, elo=elo, country_code="XX")
    db.add(row)
    db.flush()
    return row


def membership(db, tournament_row, team_row, group_name=None):
    row = TournamentTeam(
        tournament_id=tournament_row.id,
        team_id=team_row.id,
        group_name=group_name,
    )
    db.add(row)
    db.flush()
    return row


def fixture(
    db,
    tournament_row,
    home,
    away,
    *,
    status="Scheduled",
    stamp=None,
    kickoff=None,
    stage="League Phase",
    home_score=None,
    away_score=None,
    watchability_score=None,
):
    """Build one fixture. ``stamp`` is the provider id stored on ``api_id``."""
    when = FROZEN_NOW + timedelta(days=1) if kickoff is None else kickoff
    if when.tzinfo is not None:
        when = when.astimezone(timezone.utc).replace(tzinfo=None)
    row = Fixture(
        tournament_id=tournament_row.id,
        home_team_id=home.id,
        away_team_id=away.id,
        date_utc=when,
        stage=stage,
        status=status,
        api_id=stamp,
        home_score=home_score,
        away_score=away_score,
        watchability_score=watchability_score if watchability_score is not None else 0.0,
    )
    db.add(row)
    db.flush()
    return row


def kickoff(days=0, *, hour=15, minute=0, base=None):
    """UTC kickoff relative to the frozen clock."""
    start = base or FROZEN_NOW
    shifted = (start + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    if shifted.tzinfo is None:
        return shifted.replace(tzinfo=timezone.utc)
    return shifted
