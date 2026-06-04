from backend.database import Fixture, Team

def test_get_fixtures_empty(client):
    response = client.get("/api/fixtures")
    assert response.status_code == 200
    data = response.json()
    assert "today" in data
    assert "tomorrow" in data
    assert "this_week" in data
    assert len(data["today"]) == 0

def test_get_fixtures_with_data(client, db_session):
    # Populate a team and a fixture matching "today" date (2026-06-11)
    team1 = Team(name="Germany", group_name="A", elo=1900)
    team2 = Team(name="Scotland", group_name="A", elo=1650)
    db_session.add_all([team1, team2])
    
    fixture = Fixture(
        home_team_name="Germany",
        away_team_name="Scotland",
        date="2026-06-11T20:00:00",
        stage="Group Stage",
        status="Scheduled"
    )
    db_session.add(fixture)
    db_session.commit()
    
    response = client.get("/api/fixtures")
    assert response.status_code == 200
    data = response.json()
    assert len(data["today"]) == 1
    assert data["today"][0]["home_team"]["name"] == "Germany"
    assert data["today"][0]["away_team"]["name"] == "Scotland"
