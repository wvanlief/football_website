def test_get_weights(client):
    response = client.get("/api/weights")
    assert response.status_code == 200
    data = response.json()
    assert "elo" in data
    assert "odds" in data

def test_update_weights_validates_and_recalculates(client):
    payload = {
        "elo": 0.40,
        "odds": 0.40,
        "form": 0.10,
        "narrative": 0.10
    }
    response = client.post("/api/weights", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["weights"]["elo"] == 0.40

def test_update_weights_invalid_values(client):
    # odds > 1.0 is invalid based on Field(..., ge=0.0, le=1.0)
    payload = {
        "elo": 0.50,
        "odds": 1.50,
        "form": 0.10,
        "narrative": 0.10
    }
    response = client.post("/api/weights", json=payload)
    assert response.status_code == 422 # Unprocessable Entity validation error
