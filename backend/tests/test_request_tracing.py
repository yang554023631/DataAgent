import re
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.middleware import RequestTracingMiddleware


@pytest.fixture
def app_with_middleware():
    app = FastAPI()
    app.add_middleware(RequestTracingMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/sessions/{session_id}/messages")
    async def send_message(session_id: str):
        return {"status": "completed"}

    return app


def test_request_id_in_response_header(app_with_middleware):
    """响应 header 中包含 X-Request-ID"""
    client = TestClient(app_with_middleware)
    response = client.get("/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


def test_request_id_is_unique(app_with_middleware):
    """两次请求的 request_id 不同"""
    client = TestClient(app_with_middleware)
    r1 = client.get("/health")
    r2 = client.get("/health")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


def test_request_id_is_valid_uuid(app_with_middleware):
    """request_id 是 UUID 格式"""
    client = TestClient(app_with_middleware)
    response = client.get("/health")
    rid = response.headers["x-request-id"]
    # UUID 格式校验 (8-4-4-4-12)
    uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    assert re.match(uuid_pattern, rid, re.IGNORECASE) is not None


def test_session_id_extracted_from_path(app_with_middleware):
    """session_id 从路径中提取（通过日志间接验证）"""
    # 这里我们通过检查中间件不报错来验证基本功能
    # 更详细的日志内容验证在 integration 测试中做
    client = TestClient(app_with_middleware)
    response = client.post(
        "/api/sessions/test-sess-123/messages",
        json={"content": "hello"}
    )
    assert response.status_code == 200
    assert "x-request-id" in response.headers


def test_health_check_has_request_id(app_with_middleware):
    """health check 也有 request_id"""
    client = TestClient(app_with_middleware)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["x-request-id"]