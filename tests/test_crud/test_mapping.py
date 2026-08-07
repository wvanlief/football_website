from backend.database import Team, Competition
from backend.crud.mapping import (
    get_team_by_external_id,
    link_team_external_id,
    get_competition_by_external_id,
    link_competition_external_id
)

def test_team_external_mapping_crud(db_session):
    team = Team(name="Arsenal Test", country_code="ENG", elo=1900)
    db_session.add(team)
    db_session.flush()

    # Link Football-Data ID
    link_team_external_id(db_session, team.id, "football_data", 57)
    db_session.commit()

    # Lookup by external ID
    found_team = get_team_by_external_id(db_session, "football_data", 57)
    assert found_team is not None
    assert found_team.id == team.id
    assert found_team.name == "Arsenal Test"

    # Non-existent external ID
    assert get_team_by_external_id(db_session, "football_data", 999999) is None

def test_competition_external_mapping_crud(db_session):
    comp = Competition(name="Premier League Test", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    # Link Football-Data code/ID
    link_competition_external_id(db_session, comp.id, "football_data", "PL")
    db_session.commit()

    # Lookup by external ID
    found_comp = get_competition_by_external_id(db_session, "football_data", "PL")
    assert found_comp is not None
    assert found_comp.id == comp.id
    assert found_comp.name == "Premier League Test"
