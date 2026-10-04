"""Shared factories cover a league, a cup, and stamped or unstamped fixtures."""
from tests.factories import FROZEN_NOW, cup, fixture, kickoff, league, team, tournament


def test_factories_build_league_cup_and_stamped_fixture(db_session):
    premier = league(db_session, "Factory League")
    fa_cup = cup(db_session, "Factory Cup")
    league_tourney = tournament(db_session, premier)
    cup_tourney = tournament(db_session, fa_cup, season="2026")
    home = team(db_session, "Factory Home")
    away = team(db_session, "Factory Away")
    stamped = fixture(
        db_session, league_tourney, home, away,
        status="Finished", stamp="fd_1", kickoff=kickoff(-1),
        home_score=2, away_score=1,
    )
    open_row = fixture(
        db_session, cup_tourney, away, home,
        status="Scheduled", stamp=None, kickoff=FROZEN_NOW,
    )
    assert premier.type == "League"
    assert fa_cup.type == "Cup"
    assert stamped.api_id == "fd_1"
    assert stamped.status == "Finished"
    assert open_row.api_id is None
    assert open_row.date_utc == FROZEN_NOW.replace(tzinfo=None)
