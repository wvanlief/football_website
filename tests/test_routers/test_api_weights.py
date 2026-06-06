def test_get_weights(client):
    response = client.get("/api/weights")
    assert response.status_code == 200
    data = response.json()
    assert "elo" in data
    assert "odds" in data

def test_update_weights_not_allowed(client):
    payload = {
        "elo": 0.40,
        "odds": 0.40,
        "form": 0.10,
        "narrative": 0.10
    }
    response = client.post("/api/weights", json=payload)
    assert response.status_code == 405  # Method Not Allowed
