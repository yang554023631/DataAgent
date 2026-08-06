import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.graph.builder import build_graph
from src.nl_dsl.models import NlDslResult


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


@pytest.mark.asyncio
async def test_graph_nl_dsl_path():
    """测试触发 nl_dsl 路由的查询流程（完整 Graph 流转验证）"""
    # 模拟 NL→DSL 成功结果
    mock_result = NlDslResult(
        display_type="list",
        columns=["计划ID", "计划名称", "消耗"],
        rows=[["1", "计划A", 1500], ["2", "计划B", 2000]],
        metadata={"success": True, "total_rows": 2}
    )

    # mock 所有外部依赖和节点（patch builder 模块中的引用）
    with patch('src.nl_dsl.dsl_generator.get_dsl_generator') as mock_get_generator, \
         patch('src.nl_dsl.self_reflection_executor.get_self_reflection_executor') as mock_get_executor, \
         patch('src.graph.builder.report_intent_node') as mock_report_intent, \
         patch('src.graph.builder.intent_classifier_node') as mock_classifier, \
         patch('src.graph.builder.reporter_node') as mock_reporter:

        mock_generator = AsyncMock()
        mock_generator.plan_query = AsyncMock(return_value=MagicMock(steps=[], final_output="step_1.output"))
        mock_get_generator.return_value = mock_generator

        mock_executor = AsyncMock()
        mock_executor.execute_plan = AsyncMock(return_value=mock_result)
        mock_get_executor.return_value = mock_executor

        # mock 上游节点返回 nl_dsl 路由
        mock_classifier.return_value = {"intent_category": "report"}
        mock_report_intent.return_value = {
            "query_route": "nl_dsl",
            "route_reason": "探索式列表查询",
            "analysis_type": "exploratory_query",
            "report_intent_result": {
                "time_range": {"start_date": "2026-08-01", "end_date": "2026-08-07"},
                "advertiser_ids": ["1"],
            },
            "advertiser_ids": ["1"],
            "needs_clarification": False,
        }
        # reporter 透传 final_report
        async def reporter_side_effect(state):
            return {"final_report": state.get("final_report"), "error": None}
        mock_reporter.side_effect = reporter_side_effect

        graph = build_graph()

        initial_state = create_test_state(
            "test-session-006",
            "列出近7天消耗大于1000的计划"
        )

        # 执行 graph，添加 config 以通过 checkpointer 验证
        result = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": "test-thread-006"}}
        )

        # 验证最终结果
        assert result["error"] is None
        assert result["final_report"] is not None
        assert result["final_report"]["title"] == "2026-08-01 ~ 2026-08-07 查询结果"
        assert len(result["final_report"]["data_table"]["rows"]) == 2
        assert result["final_report"]["data_table"]["columns"] == ["计划ID", "计划名称", "消耗"]
        # 验证使用了 nl_dsl 路径
        assert "nl_dsl_result" in result
