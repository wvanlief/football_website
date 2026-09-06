import pytest
from datetime import datetime
from backend.database import Competition, Tournament, Team, TournamentTeam, Fixture

def test_api_group_endpoints(client, db_session):
    # Seed the DB so endpoints have data
    comp = Competition(name="World Cup Router", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()
    
    # 4 teams in group A
    teams = []
    for j in range(4):
        t = Team(name=f"RouterTeam_A_{j}", elo=1600 + j*10)
        db_session.add(t)
        db_session.flush()
        teams.append(t)
        tt = TournamentTeam(tournament_id=tourney.id, team_id=t.id, group_name="A")
        db_session.add(tt)
        db_session.flush()
        
    db_session.commit()
    
    # Test GET Group Details
    response = client.get("/api/group/A")
    assert response.status_code == 200
    data = response.json()
    assert data["group_letter"] == "A"
    assert len(data["standings"]) == 4
    assert "qualification_probability" in data["standings"][0]
    assert "status" in data["standings"][0]
    assert "points_needed_top_2" in data["standings"][0]
    
    # Test GET Thirds Standings
    response = client.get("/api/group/thirds")
    assert response.status_code == 200
    thirds_data = response.json()
    # Since only group A is seeded, only RouterTeam_A_2 (3rd rank) should be returned as the third-placed team
    assert len(thirds_data) == 1
    assert thirds_data[0]["group"] == "A"
    assert thirds_data[0]["name"] == "RouterTeam_A_1"


def test_api_group_standings_league_phase_filters_qualifiers(client, db_session):
    comp = Competition(
        name="UEFA Europa League Group API",
        type="Cup",
        format_engine="league_phase_knockout",
    )
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    home = Team(name="API Home", elo=1800)
    away = Team(name="API Away", elo=1700)
    qualifier = Team(name="API Qualifier", elo=1500)
    db_session.add_all([home, away, qualifier])
    db_session.flush()
    for team in (home, away, qualifier):
        db_session.add(TournamentTeam(tournament_id=tourney.id, team_id=team.id))

    db_session.add(Fixture(
        tournament_id=tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        stage="League Phase",
        status="Scheduled",
        date_utc=datetime(2026, 9, 17),
    ))
    db_session.add(Fixture(
        tournament_id=tourney.id,
        home_team_id=qualifier.id,
        away_team_id=home.id,
        stage="2nd Qualifying Round",
        status="Finished",
        home_score=0,
        away_score=1,
        date_utc=datetime(2026, 8, 5),
    ))
    db_session.commit()

    response = client.get(f"/api/group/STANDINGS?tournament_id={tourney.id}")
    assert response.status_code == 200
    data = response.json()
    standing_names = {row["name"] for row in data["standings"]}
    assert standing_names == {"API Home", "API Away"}
    assert all(f["stage"] == "League Phase" for f in data["fixtures"])
    assert len(data["fixtures"]) == 1
