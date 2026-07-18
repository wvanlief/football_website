from backend.database import Competition, Tournament

def test_list_competitions_empty(client):
    response = client.get("/api/competitions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_list_competitions_with_data(client, db_session):
    comp = Competition(name="Premier League", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()

    tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
    db_session.add(tourney)
    db_session.commit()

    response = client.get("/api/competitions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    
    # Check Premier League is in the list
    pl = [c for c in data if c["name"] == "Premier League"]
    assert len(pl) == 1
    assert pl[0]["type"] == "League"
    assert pl[0]["format_engine"] == "league"
    assert len(pl[0]["tournaments"]) == 1
    assert pl[0]["tournaments"][0]["season_name"] == "2026"
    assert pl[0]["tournaments"][0]["status"] == "Active"
