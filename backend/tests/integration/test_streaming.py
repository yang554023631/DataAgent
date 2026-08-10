import pytest
import json
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_stream_message_endpoint_exists():
    """测试流式端点是否存在"""
    # Create session first
    response = client.post("/api/sessions", json={})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # Test stream endpoint returns text/event-stream
    response = client.post(
        f"/api/sessions/{session_id}/messages/stream",
        json={"content": "测试消息"}
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


def test_stream_message_session_not_found():
    """测试会话不存在时的处理"""
    response = client.post(
        "/api/sessions/nonexistent/messages/stream",
        json={"content": "测试消息"}
    )
    assert response.status_code == 404


def test_stream_message_events():
    """测试流式消息返回的事件格式"""
    # Create session first
    response = client.post("/api/sessions", json={})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # Send stream message
    response = client.post(
        f"/api/sessions/{session_id}/messages/stream",
        json={"content": "看上周的曝光点击"}
    )
    assert response.status_code == 200

    # Parse SSE events
    events = []
    content = response.content.decode("utf-8")
    lines = content.split("\n")
    for line in lines:
        if line.startswith("data: "):
            data = line[6:]
            try:
                events.append(json.loads(data))
            except json.JSONDecodeError:
                pass

    # Verify we got events
    assert len(events) > 0

    # Check that we have a complete event at the end
    assert any(event.get("type") == "complete" for event in events)

    # Check event types - should have step events and maybe others
    event_types = [event.get("type") for event in events]
    # At minimum should have complete event
    assert "complete" in event_types
