"""流式响应集成测试"""
import sys
import os
import types
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# ============================================================================
# 设置合并的 src 包
# ============================================================================

_integration_dir = os.path.dirname(os.path.abspath(__file__))
_tests_dir = os.path.dirname(_integration_dir)
_backend_dir = os.path.dirname(_tests_dir)
_project_root = os.path.dirname(_backend_dir)

_backend_src = os.path.join(_backend_dir, 'src')
_root_src = os.path.join(_project_root, 'src')

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

_src_mod = types.ModuleType('src')
_src_mod.__path__ = [_root_src, _backend_src]
sys.modules['src'] = _src_mod

_nl_dsl_mod = types.ModuleType('src.nl_dsl')
_nl_dsl_mod.__path__ = [
    os.path.join(_root_src, 'nl_dsl'),
    os.path.join(_backend_src, 'nl_dsl'),
]
sys.modules['src.nl_dsl'] = _nl_dsl_mod

_graph_mod = types.ModuleType('src.graph')
_graph_mod.__path__ = [os.path.join(_backend_src, 'graph')]
sys.modules['src.graph'] = _graph_mod

_analysis_mod = types.ModuleType('src.analysis')
_analysis_mod.__path__ = [os.path.join(_root_src, 'analysis')]
sys.modules['src.analysis'] = _analysis_mod

_intent_mod = types.ModuleType('src.intent')
_intent_mod.__path__ = [os.path.join(_backend_src, 'intent')]
sys.modules['src.intent'] = _intent_mod

_tools_mod = types.ModuleType('src.tools')
_tools_mod.__path__ = [os.path.join(_backend_src, 'tools')]
sys.modules['src.tools'] = _tools_mod

_services_mod = types.ModuleType('src.services')
_services_mod.__path__ = [os.path.join(_backend_src, 'services')]
sys.modules['src.services'] = _services_mod

_rag_mod = types.ModuleType('src.rag')
_rag_mod.__path__ = [os.path.join(_backend_src, 'rag')]
sys.modules['src.rag'] = _rag_mod

_agents_mod = types.ModuleType('src.agents')
_agents_mod.__path__ = [os.path.join(_backend_src, 'agents')]
sys.modules['src.agents'] = _agents_mod

_config_mod = types.ModuleType('src.config')
_config_mod.__path__ = [os.path.join(_backend_src, 'config')]
sys.modules['src.config'] = _config_mod

# ============================================================================
# 导入
# ============================================================================

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


# ============================================================================
# 已有测试（保留）
# ============================================================================

def test_stream_message_endpoint_exists():
    """测试流式端点是否存在"""
    response = client.post("/api/sessions", json={})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

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
    response = client.post("/api/sessions", json={})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    response = client.post(
        f"/api/sessions/{session_id}/messages/stream",
        json={"content": "看上周的曝光点击"}
    )
    assert response.status_code == 200

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

    assert len(events) > 0
    assert any(event.get("type") == "complete" for event in events)

    event_types = [event.get("type") for event in events]
    assert "complete" in event_types


# ============================================================================
# 辅助函数
# ============================================================================

def _parse_sse_events(content: str) -> list:
    """从 SSE 响应内容中解析事件列表"""
    events = []
    lines = content.split("\n")
    for line in lines:
        if line.startswith("data: "):
            data = line[6:]
            try:
                events.append(json.loads(data))
            except json.JSONDecodeError:
                pass
    return events


async def _collect_stream_events(generator):
    """从异步生成器中收集 SSE 事件"""
    events = []
    async for event_data in generator:
        if event_data.startswith("data: "):
            try:
                events.append(json.loads(event_data[6:]))
            except json.JSONDecodeError:
                pass
    return events


# ============================================================================
# C. Streaming tests（流式场景测试）
# ============================================================================

@pytest.mark.asyncio
async def test_stream_hitl_event_emitted():
    """测试 HITL 场景下流式响应正确发出 hitl 事件

    当 analysis_node 返回 needs_clarification=True 时，
    stream_message 应该发出 hitl 类型事件，
    包含 question 和 options，并且流以 complete 事件正常结束（不提前关闭）。
    """
    from src.services.session_service import SessionService

    service = SessionService()
    session = service.create_session()
    session_id = session["session_id"]

    mock_result = {
        "needs_clarification": True,
        "clarification": {
            "type": "cot_clarification",
            "question": "请选择要查看的广告主",
            "options": [
                {"value": "123", "label": "广告主 123"},
                {"value": "456", "label": "广告主 456"},
            ],
            "allow_custom_input": True,
            "missing_fields": ["advertiser_ids"],
        },
        "hitl_request": {
            "question": "请选择要查看的广告主",
            "missing_fields": ["advertiser_ids"],
            "options": [
                {"value": "123", "label": "广告主 123"},
                {"value": "456", "label": "广告主 456"},
            ],
        },
        "execution_trace": [
            {"step": "intent_analyzer", "status": "started"},
            {"step": "intent_analyzer", "status": "success", "duration_ms": 10},
            {"step": "cot_planner", "status": "started"},
            {"step": "cot_planner", "status": "hitl_required", "duration_ms": 50},
        ],
        "cot_reasoning": {"steps": [], "summary": "需要澄清"},
    }

    with patch('src.services.session_service.graph_app') as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        events = await _collect_stream_events(
            service.stream_message(session_id, "查看广告主的数据")
        )

    event_types = [e["type"] for e in events]

    # 应该有 step_start 和 step_complete 事件
    assert "step_start" in event_types
    assert "step_complete" in event_types

    # 应该有 hitl 事件（关键验证点）
    assert "hitl" in event_types, "HITL 场景应该发出 hitl 事件"

    # 验证 hitl 事件的内容
    hitl_events = [e for e in events if e["type"] == "hitl"]
    assert len(hitl_events) >= 1
    hitl = hitl_events[0]
    assert "question" in hitl
    assert "请选择" in hitl["question"]
    assert "options" in hitl
    assert len(hitl["options"]) == 2
    assert hitl["options"][0]["value"] == "123"

    # 应该有 complete 事件（流正常结束，不会因为 HITL 提前关闭）
    assert "complete" in event_types, "流式响应应该以 complete 事件结束"

    # 验证事件顺序：step 事件 → hitl → complete
    hitl_idx = event_types.index("hitl")
    complete_idx = event_types.index("complete")
    assert hitl_idx < complete_idx, "hitl 事件应该在 complete 之前"

    # 验证有 CoT reasoning 事件
    assert "cot_reasoning" in event_types


@pytest.mark.asyncio
async def test_stream_error_event_emitted():
    """测试错误场景下流式响应正确发出 error 和 complete 事件

    当图执行抛出异常时，stream_message 应该：
    1. 发出 error 类型事件，包含错误消息
    2. 发出 complete 事件（确保流正常关闭）
    3. 不应该有 final_report 事件
    """
    from src.services.session_service import SessionService

    service = SessionService()
    session = service.create_session()
    session_id = session["session_id"]

    error_message = "Elasticsearch connection refused"

    with patch('src.services.session_service.graph_app') as mock_graph:
        mock_graph.ainvoke = AsyncMock(side_effect=Exception(error_message))
        events = await _collect_stream_events(
            service.stream_message(session_id, "查看消耗数据")
        )

    event_types = [e["type"] for e in events]

    # 验证 error 事件存在
    assert "error" in event_types, "错误场景应该发出 error 事件"

    # 验证 error 事件包含错误消息
    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert error_message in error_events[0]["message"]

    # 验证 complete 事件存在（流正常关闭）
    assert "complete" in event_types, "错误场景也应该以 complete 事件结束"

    # 验证顺序：error → complete
    error_idx = event_types.index("error")
    complete_idx = event_types.index("complete")
    assert error_idx < complete_idx, "error 应该在 complete 之前"

    # 不应该有 final_report 事件
    assert "final_report" not in event_types


@pytest.mark.asyncio
async def test_stream_empty_result_report_emitted():
    """测试空结果场景下流式响应正确发出空报告

    当 EmptyResultChecker 发现空数据时，analysis_node 返回 empty 类型的 final_report，
    流式响应应该正确发出 final_report 事件（report_type=empty）。
    """
    from src.services.session_service import SessionService

    service = SessionService()
    session = service.create_session()
    session_id = session["session_id"]

    empty_report = {
        "report_type": "empty",
        "title": "📭 时间趋势分析",
        "highlights": [
            {"type": "negative", "text": "⚠️ 在指定条件下，核心指标的总和为零"}
        ],
        "data_table": {"columns": [], "rows": []},
        "suggestions": ["调整筛选条件", "扩大时间范围"],
    }

    mock_result = {
        "needs_clarification": False,
        "final_report": empty_report,
        "execution_trace": [
            {"step": "intent_analyzer", "status": "started"},
            {"step": "intent_analyzer", "status": "success", "duration_ms": 10},
            {"step": "cot_planner", "status": "started"},
            {"step": "cot_planner", "status": "success", "duration_ms": 50},
            {"step": "filter_executor", "status": "started"},
            {"step": "filter_executor", "status": "success", "duration_ms": 30},
            {"step": "empty_result_checker", "status": "started"},
            {"step": "empty_result_checker", "status": "empty_data", "duration_ms": 20},
            {"step": "complete", "status": "empty", "total_duration_ms": 120},
        ],
        "cot_reasoning": {"steps": [], "summary": "空结果"},
    }

    with patch('src.services.session_service.graph_app') as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        events = await _collect_stream_events(
            service.stream_message(session_id, "查看不存在的广告数据")
        )

    event_types = [e["type"] for e in events]

    # 验证 final_report 事件存在
    assert "final_report" in event_types, "空结果场景应该发出 final_report 事件"

    # 验证 final_report 内容是 empty 类型
    report_events = [e for e in events if e["type"] == "final_report"]
    assert len(report_events) == 1
    report_data = report_events[0]["data"]
    assert report_data["report_type"] == "empty"
    assert "📭" in report_data["title"]
    assert len(report_data["highlights"]) > 0
    assert report_data["highlights"][0]["type"] == "negative"

    # 验证 complete 事件存在
    assert "complete" in event_types

    # 验证空结果检查步骤在 trace 中被标记为 empty_data
    step_complete_events = [e for e in events if e.get("type") == "step_complete"]
    step_names = [e.get("step") for e in step_complete_events]
    assert "empty_result_checker" in step_names

    # 验证没有 hitl 事件
    assert "hitl" not in event_types

    # 验证顺序：step 事件 → final_report → complete
    report_idx = event_types.index("final_report")
    complete_idx = event_types.index("complete")
    assert report_idx < complete_idx


@pytest.mark.asyncio
async def test_stream_success_flow_event_order():
    """测试成功场景下流式事件的完整顺序

    验证成功路径下事件类型和顺序正确：
    step_start → step_complete（多个）→ cot_reasoning → final_report → complete
    """
    from src.services.session_service import SessionService

    service = SessionService()
    session = service.create_session()
    session_id = session["session_id"]

    success_report = {
        "report_type": "success",
        "title": "时间趋势分析",
        "highlights": [{"type": "info", "text": "✅ 分析完成"}],
        "metrics": ["cost"],
    }

    mock_result = {
        "needs_clarification": False,
        "final_report": success_report,
        "execution_trace": [
            {"step": "intent_analyzer", "status": "started"},
            {"step": "intent_analyzer", "status": "success", "duration_ms": 10},
            {"step": "cot_planner", "status": "started"},
            {"step": "cot_planner", "status": "success", "duration_ms": 50},
            {"step": "filter_executor", "status": "started"},
            {"step": "filter_executor", "status": "success", "duration_ms": 20},
            {"step": "empty_result_checker", "status": "started"},
            {"step": "empty_result_checker", "status": "success", "duration_ms": 5},
            {"step": "analysis_executor", "status": "started"},
            {"step": "analysis_executor", "status": "success", "duration_ms": 30},
            {"step": "quality_checker", "status": "started"},
            {"step": "quality_checker", "status": "success", "duration_ms": 5},
            {"step": "report_formatter", "status": "started"},
            {"step": "report_formatter", "status": "success", "duration_ms": 10},
            {"step": "complete", "status": "success", "total_duration_ms": 150},
        ],
        "cot_reasoning": {"steps": [], "summary": "分析完成"},
    }

    with patch('src.services.session_service.graph_app') as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        events = await _collect_stream_events(
            service.stream_message(session_id, "查看消耗趋势")
        )

    event_types = [e["type"] for e in events]

    # 验证所有关键事件类型
    assert "step_start" in event_types
    assert "step_complete" in event_types
    assert "cot_reasoning" in event_types
    assert "final_report" in event_types
    assert "complete" in event_types

    # 验证没有 hitl 和 error
    assert "hitl" not in event_types
    assert "error" not in event_types

    # 验证事件数量合理
    step_start_count = event_types.count("step_start")
    step_complete_count = event_types.count("step_complete")
    assert step_start_count >= 6  # 至少 6 个步骤开始
    assert step_complete_count >= 6  # 至少 6 个步骤完成

    # 验证顺序：cot_reasoning 在 final_report 之前，final_report 在 complete 之前
    cot_idx = event_types.index("cot_reasoning")
    report_idx = event_types.index("final_report")
    complete_idx = event_types.index("complete")
    assert cot_idx < report_idx < complete_idx

    # 验证 final_report 内容
    report_events = [e for e in events if e["type"] == "final_report"]
    assert report_events[0]["data"]["report_type"] == "success"


@pytest.mark.asyncio
async def test_stream_session_not_found_returns_error():
    """测试会话不存在时流式响应返回 error + complete 事件"""
    from src.services.session_service import SessionService

    service = SessionService()
    # 不创建会话，直接请求不存在的 session

    events = await _collect_stream_events(
        service.stream_message("nonexistent-session", "test")
    )

    event_types = [e["type"] for e in events]

    # 应该有 error 和 complete
    assert "error" in event_types
    assert "complete" in event_types

    # error 消息应该包含 session not found
    error_events = [e for e in events if e["type"] == "error"]
    assert "not found" in error_events[0]["message"].lower() or "Session" in error_events[0]["message"]

    # 顺序：error → complete
    assert event_types.index("error") < event_types.index("complete")
