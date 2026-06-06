from datetime import datetime
from backend.database import Fixture, Competition, Tournament, Team, TournamentTeam

def test_get_fixtures_empty(client):
    response = client.get("/api/fixtures")
    assert response.status_code == 200
    data = response.json()
    assert "today" in data
    assert "tomorrow" in data
    assert "this_week" in data
    assert len(data["today"]) == 0

def test_get_fixtures_with_data(client, db_session):
    # Populate competition and tournament
    comp = Competition(name="World Cup", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()

    # Populate teams and their tournament settings
    team1 = Team(name="Germany", elo=1900)
    team2 = Team(name="Scotland", elo=1650)
    db_session.add_all([team1, team2])
    db_session.flush()

    tt1 = TournamentTeam(tournament_id=tourney.id, team_id=team1.id, group_name="A")
    tt2 = TournamentTeam(tournament_id=tourney.id, team_id=team2.id, group_name="A")
    db_session.add_all([tt1, tt2])
    db_session.flush()
    
    fixture = Fixture(
        tournament_id=tourney.id,
        home_team_id=team1.id,
        away_team_id=team2.id,
        date_utc=datetime.fromisoformat("2026-06-11T20:00:00"),
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
