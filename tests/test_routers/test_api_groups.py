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
