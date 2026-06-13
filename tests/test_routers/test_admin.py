from unittest.mock import patch

def test_admin_update_unauthorized_no_header(client):
    response = client.post("/api/admin/update")
    assert response.status_code == 401
    assert "detail" in response.json()

def test_admin_update_unauthorized_bad_token(client):
    response = client.post("/api/admin/update", headers={"X-Admin-Token": "bad-token-here"})
    assert response.status_code == 401

@patch("backend.routers.api_admin.update_results_and_odds")
def test_admin_update_success(mock_update, client):
    mock_update.return_value = {
        "status": "success",
        "fixtures_created": 1,
        "fixtures_updated_results": 2,
        "simulation": "Completed"
    }
    
    response = client.post("/api/admin/update", headers={"X-Admin-Token": "test-admin-token"})
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "success"
    assert data["fixtures_created"] == 1
    assert data["fixtures_updated_results"] == 2
    assert data["simulation"] == "Completed"
    mock_update.assert_called_once()

def test_admin_update_live_unauthorized_no_header(client):
    response = client.post("/api/admin/update-live")
    assert response.status_code == 401
    assert "detail" in response.json()

def test_admin_update_live_unauthorized_bad_token(client):
    response = client.post("/api/admin/update-live", headers={"X-Admin-Token": "bad-token-here"})
    assert response.status_code == 401

@patch("backend.routers.api_admin.update_live_scores")
def test_admin_update_live_success(mock_update_live, client):
    mock_update_live.return_value = {
        "status": "success",
        "fixtures_updated_live": 1,
        "fixtures_finished": 0,
        "simulation": "Skipped"
    }
    
    response = client.post("/api/admin/update-live", headers={"X-Admin-Token": "test-admin-token"})
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "success"
    assert data["fixtures_updated_live"] == 1
    assert data["fixtures_finished"] == 0
    assert data["simulation"] == "Skipped"
    mock_update_live.assert_called_once_with(mock_update_live.call_args[0][0], force=False)

