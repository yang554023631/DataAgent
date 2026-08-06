"""
测试 nl_dsl_node
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.graph.nodes import nl_dsl_node, _build_nl_dsl_final_report, _build_failure_guide_report
from src.nl_dsl.models import NlDslResult


@pytest.mark.asyncio
async def test_nl_dsl_node_success():
    """测试 nl_dsl_node 成功路径"""
    # 模拟 state
    state = {
        "user_input": "查看近7天消耗大于1000的计划列表",
        "report_intent_result": {
            "time_range": {"start_date": "2026-08-01", "end_date": "2026-08-07"},
            "metrics": ["cost", "impressions"],
            "chart_type": "list"
        },
        "advertiser_ids": ["123"],
        "query_route": "nl_dsl",
        "analysis_type": "exploratory_query"
    }

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

    # mock get_dsl_generator 和 get_self_reflection_executor（导入是在函数内部，所以 patch 它们的来源模块）
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

        # 执行节点
        updates = await nl_dsl_node(state)

        # 验证
        assert "final_report" in updates
        assert "nl_dsl_result" in updates
        assert updates["final_report"]["title"] is not None
        assert len(updates["final_report"]["highlights"]) > 0
        assert updates["nl_dsl_result"]["display_type"] == "list"


@pytest.mark.asyncio
async def test_nl_dsl_node_failure():
    """测试 nl_dsl_node 失败路径（返回失败引导报告）"""
    # 模拟 state
    state = {
        "user_input": "查看近7天消耗大于1000的计划列表",
        "report_intent_result": {
            "time_range": {"start_date": "2026-08-01", "end_date": "2026-08-07"},
            "metrics": ["cost"],
            "chart_type": "list"
        },
        "advertiser_ids": ["123"],
        "query_route": "nl_dsl"
    }

    # 模拟失败结果
    mock_result = NlDslResult(
        display_type="qa",
        columns=["错误信息"],
        rows=[["查询执行超时"]],
        metadata={"success": False, "final_error": "查询执行超时"}
    )

    # mock
    with patch('src.nl_dsl.dsl_generator.get_dsl_generator') as mock_get_generator, \
         patch('src.nl_dsl.self_reflection_executor.get_self_reflection_executor') as mock_get_executor:

        mock_generator = AsyncMock()
        mock_generator.plan_query = AsyncMock(return_value=MagicMock(steps=[], final_output="step_1.output"))
        mock_get_generator.return_value = mock_generator

        mock_executor = AsyncMock()
        mock_executor.execute_plan = AsyncMock(return_value=mock_result)
        mock_get_executor.return_value = mock_executor

        # 执行
        updates = await nl_dsl_node(state)

        # 验证
        assert "final_report" in updates
        assert "nl_dsl_result" not in updates  # 失败不保存结果
        assert "遇到问题" in updates["final_report"]["title"] or "查询遇到问题" in updates["final_report"]["title"]
        assert any("⚠️" in h.get("text", "") for h in updates["final_report"]["highlights"])
        assert any("💡" in h.get("text", "") for h in updates["final_report"]["highlights"])


@pytest.mark.asyncio
async def test_nl_dsl_node_exception():
    """测试 nl_dsl_node 异常处理"""
    state = {
        "user_input": "测试异常",
        "report_intent_result": {},
        "advertiser_ids": ["123"]
    }

    # mock 抛出异常（patch 来源模块）
    with patch('src.nl_dsl.dsl_generator.get_dsl_generator') as mock_get_generator:
        mock_get_generator.side_effect = Exception("DSL 生成器初始化失败")

        updates = await nl_dsl_node(state)

        assert "final_report" in updates
        assert "查询遇到问题" in updates["final_report"]["title"]
        assert any("DSL 生成器初始化失败" in h.get("text", "") for h in updates["final_report"]["highlights"])


def test_build_nl_dsl_final_report():
    """测试 _build_nl_dsl_final_report 辅助函数"""
    # 使用 dict 格式的 result
    result_dict = {
        "display_type": "list",
        "columns": ["计划ID", "消耗"],
        "rows": [["1", 1000], ["2", 2000]],
        "metadata": {"success": True, "total_rows": 2},
        "query_context": None
    }

    user_input = "查看消耗大于1000的计划"
    report_intent = {
        "time_range": {"start_date": "2026-08-01", "end_date": "2026-08-07"}
    }

    report = _build_nl_dsl_final_report(result_dict, user_input, report_intent)

    assert report["title"] == "2026-08-01 ~ 2026-08-07 查询结果"
    assert len(report["data_table"]["rows"]) == 2
    assert any("✅" in h.get("text", "") for h in report["highlights"])
    assert report["insights"] is None  # 必须有 insights 字段
    assert report["time_range"]["start"] == "2026-08-01"  # start/end 格式
    assert report["time_range"]["end"] == "2026-08-07"
    # 验证 highlights 类型
    for h in report["highlights"]:
        assert h["type"] in ["positive", "negative", "info"]


def test_build_nl_dsl_final_report_empty_result():
    """测试 _build_nl_dsl_final_report 空结果情况"""
    result_dict = {
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

    report = _build_nl_dsl_final_report(result_dict, "查看消耗大于1000的计划", {})

    assert any("⚠️" in h.get("text", "") for h in report["highlights"])
    assert report["insights"] is None
    # 验证 warning 改为 negative
    warning_highlights = [h for h in report["highlights"] if "⚠️" in h.get("text", "")]
    for h in warning_highlights:
        assert h["type"] == "negative"
    assert any("没有找到" in h.get("text", "") for h in report["highlights"])


def test_build_failure_guide_report():
    """测试 _build_failure_guide_report 辅助函数"""
    error_msg = "查询执行超时，尝试简化查询条件"
    user_input = "查看近7天消耗大于1000且点击率大于5%的计划，按天分组对比上月数据"

    report = _build_failure_guide_report(error_msg, user_input)

    assert "查询遇到问题" in report["title"]
    assert any("查询执行超时" in h.get("text", "") for h in report["highlights"])
    assert any("💡" in h.get("text", "") for h in report["highlights"])
    assert len(report["next_queries"]) > 0
    assert report["insights"] is None
    # 验证 highlights 类型
    for h in report["highlights"]:
        assert h["type"] in ["positive", "negative", "info"]


def test_build_failure_guide_report_with_nl_dsl_result():
    """测试 _build_failure_guide_report 接受 NlDslResult 对象"""
    result = NlDslResult(
        display_type="qa",
        columns=["错误"],
        rows=[["失败"]],
        metadata={"success": False, "final_error": "DSL 生成失败：语法错误"}
    )

    report = _build_failure_guide_report(result, "测试")

    assert any("DSL 生成失败" in h.get("text", "") for h in report["highlights"])


def test_build_failure_guide_report_with_exception():
    """测试 _build_failure_guide_report 接受异常对象"""
    class CustomException(Exception):
        pass

    exc = CustomException("连接数据库超时")

    report = _build_failure_guide_report(exc, "测试")

    assert any("CustomException" in h.get("text", "") or "连接数据库超时" in h.get("text", "")
               for h in report["highlights"])


@pytest.mark.asyncio
async def test_nl_dsl_node_query_context_type_check():
    """测试 nl_dsl_node 中 query_context 类型检查"""
    # 模拟 state
    state = {
        "user_input": "测试查询",
        "report_intent_result": {
            "time_range": {"start_date": "2026-08-01", "end_date": "2026-08-07"},
            "metrics": ["cost"],
            "chart_type": "list"
        },
        "advertiser_ids": ["123"],
        "query_route": "nl_dsl"
    }

    # 测试 1: query_context 是正常 dict
    mock_result1 = NlDslResult(
        display_type="list",
        columns=["计划ID"],
        rows=[["1"]],
        metadata={"success": True},
        query_context={"page": 1, "size": 10}
    )

    # 测试 2: query_context 是 None
    mock_result2 = NlDslResult(
        display_type="list",
        columns=["计划ID"],
        rows=[["1"]],
        metadata={"success": True},
        query_context=None
    )

    # mock
    with patch('src.nl_dsl.dsl_generator.get_dsl_generator') as mock_get_generator, \
         patch('src.nl_dsl.self_reflection_executor.get_self_reflection_executor') as mock_get_executor:

        mock_generator = AsyncMock()
        mock_generator.plan_query = AsyncMock(return_value=MagicMock(steps=[], final_output="step_1.output"))
        mock_get_generator.return_value = mock_generator

        # 测试 1: 正常 dict
        mock_executor = AsyncMock()
        mock_executor.execute_plan = AsyncMock(return_value=mock_result1)
        mock_get_executor.return_value = mock_executor
        updates1 = await nl_dsl_node(state)
        assert updates1["query_context"] == {"page": 1, "size": 10}

        # 测试 2: None
        mock_executor.execute_plan = AsyncMock(return_value=mock_result2)
        updates2 = await nl_dsl_node(state)
        assert updates2["query_context"] == {}
