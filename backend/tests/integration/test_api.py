import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_create_session():
    response = client.post("/api/sessions", json={})
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "created_at" in data

def test_get_session_not_found():
    response = client.get("/api/sessions/nonexistent")
    assert response.status_code == 404

def test_send_message():
    # Create session first
    response = client.post("/api/sessions", json={})
    session_id = response.json()["session_id"]

    # Send message
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "看上周的曝光点击"}
    )
    # Just verify the endpoint returns something
    assert response.status_code == 200
    result = response.json()
    # Should have either completed or waiting for clarification
    assert "status" in result
