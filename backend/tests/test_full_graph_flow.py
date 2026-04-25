import pytest
from src.graph.builder import build_graph


def create_test_state(session_id: str, user_input: str, advertiser_ids: list = None) -> dict:
    """创建测试状态，默认包含广告主以避免触发选择流程"""
    return {
        "session_id": session_id,
        "user_id": "test-user",
        "user_input": user_input,
        "conversation_history": [],
        "advertiser_ids": ["1"] if advertiser_ids is None else advertiser_ids,
        "show_advertiser_list": False,
        "query_intent": None,
        "query_request": None,
        "query_result": None,
        "analysis_result": None,
        "final_report": None,
        "ambiguity": None,
        "user_feedback": None,
        "clarification_count": 0,
        "query_warnings": [],
        "drill_down_level": 0,
        "needs_drill_down": False,
        "error": None,
        "execution_time_ms": None,
    }


@pytest.mark.asyncio
async def test_complete_graph_flow():
    """测试完整的 6-node 流程"""
    graph = build_graph()

    initial_state = create_test_state("test-session-001", "看上周的曝光点击")
    result = await graph.ainvoke(initial_state)

    # 验证最终结果
    assert result["error"] is None
    assert result["final_report"] is not None
    assert "title" in result["final_report"]
    assert "metrics" in result["final_report"]
    assert "highlights" in result["final_report"]
    assert "data_table" in result["final_report"]


@pytest.mark.asyncio
async def test_graph_with_dimension_query():
    """测试带维度的查询流程"""
    graph = build_graph()

    initial_state = create_test_state("test-session-002", "按渠道看 CTR")
    result = await graph.ainvoke(initial_state)

    # 验证最终结果
    assert result["error"] is None
    assert result["final_report"] is not None
    # 验证维度被正确解析
    assert result["query_intent"] is not None
    assert "group_by" in result["query_intent"]


@pytest.mark.asyncio
async def test_graph_multiple_metrics():
    """测试多指标查询流程"""
    graph = build_graph()

    initial_state = create_test_state(
        "test-session-003",
        "看上周的曝光、点击、花费和 CTR"
    )
    result = await graph.ainvoke(initial_state)

    # 验证最终结果
    assert result["error"] is None
    assert result["final_report"] is not None
    assert len(result["final_report"]["metrics"]) > 0


@pytest.mark.asyncio
async def test_graph_advertiser_list_query():
    """测试查询广告主列表"""
    graph = build_graph()

    initial_state = create_test_state(
        "test-session-004",
        "有哪些广告主",
        advertiser_ids=[]  # 没有选择任何广告主
    )
    result = await graph.ainvoke(initial_state)

    # 应该直接返回广告主列表
    assert result["error"] is None
    assert result["final_report"] is not None
    assert result["final_report"]["title"] == "可用的广告主列表"
    assert len(result["final_report"]["data_table"]["rows"]) > 0


@pytest.mark.asyncio
async def test_graph_no_advertiser_triggers_selection():
    """测试没有广告主时触发选择提示"""
    graph = build_graph()

    initial_state = create_test_state(
        "test-session-005",
        "看上周的曝光点击",
        advertiser_ids=[]  # 没有选择任何广告主
    )
    result = await graph.ainvoke(initial_state)

    # 应该提示选择广告主
    assert result["error"] is None
    assert result["final_report"] is not None
    assert result["final_report"]["title"] == "请选择要查看的广告主"
    assert len(result["final_report"]["data_table"]["rows"]) > 0
