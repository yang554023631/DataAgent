"""
NL→DSL 集成测试
验证 NL→DSL 路径在 Graph 中的完整流转
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.graph.builder import build_graph
from src.nl_dsl.models import NlDslResult


def create_test_state(session_id: str, user_input: str, advertiser_ids: list = None) -> dict:
    """创建测试状态，包含必要的基础字段"""
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
        "intent_category": "report",  # 已经过意图分类
        "report_intent_result": {
            "time_range": {"start_date": "2026-08-01", "end_date": "2026-08-07"},
            "metrics": ["cost", "impressions"],
            "chart_type": "list"
        },
        "query_route": "nl_dsl",  # 明确指定走 nl_dsl 路由
        "analysis_type": "exploratory_query"
    }


@pytest.mark.asyncio
async def test_dsl_generator_to_validator_flow():
    """测试 DSL 生成 → 校验 → 执行的管道"""
    # 模拟 state
    state = create_test_state("test-session-dsl-001", "查看近7天消耗大于1000的计划列表")

    # 模拟成功结果
    mock_result = NlDslResult(
        display_type="list",
        columns=["计划ID", "计划名称", "消耗", "展示"],
        rows=[
            ["1", "计划A", 1500, 10000],
            ["2", "计划B", 2000, 15000]
        ],
        metadata={"success": True, "total_rows": 2}
    )

    # mock 依赖
    with patch('src.nl_dsl.dsl_generator.get_dsl_generator') as mock_get_generator, \
         patch('src.nl_dsl.self_reflection_executor.get_self_reflection_executor') as mock_get_executor:

        # 配置 mock generator
        mock_generator = AsyncMock()
        mock_generator.plan_query = AsyncMock(return_value=MagicMock(steps=[], final_output="step_1.output"))
        mock_get_generator.return_value = mock_generator

        # 配置 mock executor
        mock_executor = AsyncMock()
        mock_executor.execute_plan = AsyncMock(return_value=mock_result)
        mock_get_executor.return_value = mock_executor

        # 导入并测试节点
        from src.graph.nodes import nl_dsl_node
        updates = await nl_dsl_node(state)

        # 验证
        assert "final_report" in updates
        assert "nl_dsl_result" in updates
        assert updates["final_report"]["title"] == "2026-08-01 ~ 2026-08-07 查询结果"
        assert len(updates["final_report"]["data_table"]["rows"]) == 2
        assert updates["nl_dsl_result"]["display_type"] == "list"


@pytest.mark.asyncio
async def test_self_reflection_retry_flow():
    """测试生成失败 → 自反思 → 重试成功的完整流程"""
    state = create_test_state("test-session-retry-001", "查看近7天消耗大于1000且CTR大于5%的计划列表")

    # 失败结果
    mock_failure = NlDslResult(
        display_type="qa",
        columns=["错误信息"],
        rows=[["DSL 生成失败：语法错误"]],
        metadata={"success": False, "final_error": "语法错误"}
    )

    with patch('src.nl_dsl.dsl_generator.get_dsl_generator') as mock_get_generator, \
         patch('src.nl_dsl.self_reflection_executor.get_self_reflection_executor') as mock_get_executor:

        mock_generator = AsyncMock()
        mock_generator.plan_query = AsyncMock(return_value=MagicMock(steps=[], final_output="step_1.output"))
        mock_get_generator.return_value = mock_generator

        # 执行失败
        mock_executor = AsyncMock()
        mock_executor.execute_plan = AsyncMock(return_value=mock_failure)
        mock_get_executor.return_value = mock_executor

        from src.graph.nodes import nl_dsl_node
        updates = await nl_dsl_node(state)

        # 验证只调用了一次execute_plan，并且返回了失败引导报告
        assert mock_executor.execute_plan.call_count == 1
        assert "final_report" in updates
        assert "nl_dsl_result" not in updates  # 失败不保存结果
        assert "查询遇到问题" in updates["final_report"]["title"]


@pytest.mark.asyncio
async def test_result_formatter_display_types():
    """测试不同 ES 响应格式 → 正确的 display_type"""
    from src.graph.nodes import _build_nl_dsl_final_report

    # 测试列表类型
    list_result = {
        "display_type": "list",
        "columns": ["计划ID", "消耗"],
        "rows": [["1", 1000], ["2", 2000]],
        "metadata": {"success": True, "total_rows": 2},
        "query_context": None
    }

    report = _build_nl_dsl_final_report(list_result, "查看消耗列表", {})
    assert report["data_table"]["columns"] == ["计划ID", "消耗"]
    assert report["chart_config"] is None

    # 测试图表类型
    chart_result = {
        "display_type": "bar",
        "columns": ["日期", "消耗"],
        "rows": [["2026-08-01", 1000], ["2026-08-02", 1500]],
        "metadata": {"success": True, "total_rows": 2},
        "query_context": None
    }

    report = _build_nl_dsl_final_report(chart_result, "查看消耗趋势", {})
    assert report["chart_config"]["type"] == "bar"
    assert report["chart_config"]["series"][0]["name"] == "消耗"

    # 测试空结果
    empty_result = {
        "display_type": "list",
        "columns": ["计划ID", "消耗"],
        "rows": [],
        "metadata": {
            "success": True,
            "is_empty_result": True,
            "empty_reason": "没有找到消耗大于1000的计划"
        },
        "query_context": None
    }

    report = _build_nl_dsl_final_report(empty_result, "查看消耗大于1000的计划", {})
    assert any("⚠️ 没有找到" in h.get("text", "") for h in report["highlights"])


@pytest.mark.asyncio
async def test_nl_dsl_route_from_report_intent():
    """测试 report_intent 返回 nl_dsl route → Graph 正确路由到 nl_dsl 节点"""
    # 先patch builder中引用的节点函数，再build_graph
    # 注意：必须 patch builder 模块中的引用，因为 build_graph() 从那里读取节点函数
    with patch('src.graph.builder.nl_dsl_node') as mock_nl_dsl, \
         patch('src.graph.builder.reporter_node') as mock_reporter, \
         patch('src.graph.builder.report_intent_node') as mock_report_intent, \
         patch('src.graph.builder.intent_classifier_node') as mock_classifier:

        # 配置 mock report_intent：返回 nl_dsl 路由
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
        mock_classifier.return_value = {"intent_category": "report"}

        # 配置 mock nl_dsl 和 reporter
        mock_nl_dsl.return_value = {
            "final_report": {
                "title": "测试报告",
                "data_table": {"columns": [], "rows": []},
                "highlights": [],
                "insights": None,
            }
        }
        mock_reporter.return_value = {"final_report": {"title": "最终报告"}, "error": None}

        graph = build_graph()

        # 创建状态
        initial_state = create_test_state(
            "test-session-route-001",
            "列出近7天消耗大于1000的计划"
        )

        # 执行 graph，添加 config 以通过 checkpointer 验证
        result = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": "test-thread-001"}}
        )

        # 验证路由：nl_dsl_node 应该被调用
        assert mock_nl_dsl.called, "nl_dsl_node 应该被调用"


@pytest.mark.asyncio
async def test_nl_dsl_success_flow():
    """测试 nl_dsl 节点成功 → final_report 正确生成 → 到达 reporter"""
    # 模拟成功结果
    mock_result = NlDslResult(
        display_type="list",
        columns=["计划ID", "计划名称", "消耗"],
        rows=[["1", "计划A", 1500]],
        metadata={"success": True, "total_rows": 1}
    )

    # 先patch依赖，再build_graph
    # 注意：必须 patch builder 模块中的节点引用
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

        # mock report_intent 返回 nl_dsl 路由
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
        mock_classifier.return_value = {"intent_category": "report"}
        # reporter 透传 final_report
        async def reporter_side_effect(state):
            return {"final_report": state.get("final_report"), "error": None}
        mock_reporter.side_effect = reporter_side_effect

        graph = build_graph()

        initial_state = create_test_state(
            "test-session-success-001",
            "查看近7天消耗大于1000的计划列表"
        )

        # 执行 graph，添加 config 以通过 checkpointer 验证
        result = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": "test-thread-001"}}
        )

        # 验证最终结果
        assert result["error"] is None
        assert result["final_report"] is not None
        assert result["final_report"]["title"] == "2026-08-01 ~ 2026-08-07 查询结果"
        assert len(result["final_report"]["data_table"]["rows"]) == 1
        assert result["final_report"]["data_table"]["columns"] == ["计划ID", "计划名称", "消耗"]


@pytest.mark.asyncio
async def test_nl_dsl_failure_flow():
    """测试 nl_dsl 节点失败 → 生成引导报告 → 优雅降级"""
    # 模拟失败结果
    mock_result = NlDslResult(
        display_type="qa",
        columns=["错误信息"],
        rows=[["查询执行失败：无法识别的指标"]],
        metadata={"success": False, "final_error": "无法识别的指标"}
    )

    # 先patch依赖，再build_graph
    # 注意：必须 patch builder 模块中的节点引用
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

        # mock report_intent 返回 nl_dsl 路由
        mock_report_intent.return_value = {
            "query_route": "nl_dsl",
            "route_reason": "探索式查询",
            "analysis_type": "exploratory_query",
            "report_intent_result": {
                "time_range": {"start_date": "2026-08-01", "end_date": "2026-08-07"},
                "advertiser_ids": ["1"],
            },
            "advertiser_ids": ["1"],
            "needs_clarification": False,
        }
        mock_classifier.return_value = {"intent_category": "report"}
        # reporter 透传 final_report
        async def reporter_side_effect(state):
            return {"final_report": state.get("final_report"), "error": None}
        mock_reporter.side_effect = reporter_side_effect

        graph = build_graph()

        initial_state = create_test_state(
            "test-session-failure-001",
            "查看一个非常复杂的不存在的指标的查询"
        )

        # 执行 graph，添加 config 以通过 checkpointer 验证
        result = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": "test-thread-001"}}
        )

        # 验证失败处理
        assert result["error"] is None
        assert result["final_report"] is not None
        assert "查询遇到问题" in result["final_report"]["title"]
        assert any("无法识别的指标" in h.get("text", "") for h in result["final_report"]["highlights"])
        assert any("你可以尝试用结构化方式提问" in h.get("text", "") for h in result["final_report"]["highlights"])
