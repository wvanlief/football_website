"""Table-driven season-overlay identity. Matching never deletes or moves teams."""
from datetime import timedelta

import pytest

from backend.database import Fixture
from backend.services.ingestion.fixture_identity import find_existing_fixture, stamp_fixture
from tests.factories import FROZEN_NOW, cup, fixture, team, tournament


def _row(db, tourney, home, away, *, stamp=None, kickoff=None, stage="League Phase"):
    return fixture(
        db, tourney, home, away, stamp=stamp, kickoff=kickoff or FROZEN_NOW, stage=stage
    )


@pytest.mark.parametrize(
    "case",
    [
        "provider_id",
        "unique_pairing",
        "stage",
        "kickoff_window",
        "same_provider_other_leg",
        "cross_provider_single_row",
        "none",
    ],
)
def test_find_existing_fixture_table(db_session, case):
    comp = cup(db_session, name=f"Identity {case}")
    tourney = tournament(db_session, comp)
    home = team(db_session, f"Home {case}")
    away = team(db_session, f"Away {case}")
    other_home = team(db_session, f"Other home {case}")
    other_away = team(db_session, f"Other away {case}")
    near = FROZEN_NOW
    far = FROZEN_NOW + timedelta(days=20)

    expected_id = None
    incoming_api = "fd_9"
    incoming_home, incoming_away = home, away
    incoming_when = near
    incoming_stage = "League Phase"

    if case == "provider_id":
        target = _row(db_session, tourney, home, away, stamp="fd_9", kickoff=far)
        _row(db_session, tourney, other_home, other_away, stamp="fd_1", kickoff=near)
        incoming_home, incoming_away = other_home, other_away
        expected_id = target.id
    elif case == "unique_pairing":
        target = _row(db_session, tourney, home, away, stamp="tsdb_1", kickoff=far)
        incoming_api = "fd_9"
        incoming_when = near
        expected_id = target.id
    elif case == "stage":
        target = _row(db_session, tourney, home, away, kickoff=near, stage="League Phase")
        _row(db_session, tourney, home, away, kickoff=near + timedelta(hours=1), stage="Quarter-final")
        incoming_stage = "League Phase"
        expected_id = target.id
    elif case == "kickoff_window":
        target = _row(db_session, tourney, home, away, kickoff=near, stage="League Phase")
        _row(db_session, tourney, home, away, kickoff=far, stage="League Phase")
        incoming_when = near + timedelta(hours=2)
        expected_id = target.id
    elif case == "same_provider_other_leg":
        _row(db_session, tourney, home, away, stamp="fd_1", kickoff=far, stage="League Phase")
        target = _row(db_session, tourney, home, away, stamp=None, kickoff=near, stage="League Phase")
        incoming_api = "fd_2"
        incoming_when = near + timedelta(hours=1)
        expected_id = target.id
    elif case == "cross_provider_single_row":
        target = _row(db_session, tourney, home, away, stamp="fd_1", kickoff=far)
        incoming_api = "of_9"
        expected_id = target.id
    else:
        _row(db_session, tourney, other_home, other_away, stamp="fd_1")
        incoming_api = "fd_missing"

    db_session.commit()
    before = db_session.query(Fixture).filter(Fixture.tournament_id == tourney.id).count()
    found = find_existing_fixture(
        db_session,
        tourney,
        incoming_api,
        incoming_home,
        incoming_away,
        incoming_when,
        incoming_stage,
    )
    after = db_session.query(Fixture).filter(Fixture.tournament_id == tourney.id).count()
    assert after == before
    if expected_id is None:
        assert found is None
    else:
        assert found.id == expected_id
        home_id, away_id = found.home_team_id, found.away_team_id
        stamp_fixture(found, incoming_api)
        assert found.api_id == incoming_api
        assert found.home_team_id == home_id
        assert found.away_team_id == away_id
