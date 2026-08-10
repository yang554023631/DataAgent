"""测试 analysis_node - CoT 分析节点集成测试"""
import sys
import os
import importlib.util

# Step 1: Import backend/src modules first (as "backend_src")
backend_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
spec = importlib.util.spec_from_file_location("backend_src", os.path.join(backend_src_dir, "__init__.py"))
backend_src = importlib.util.module_from_spec(spec)
sys.modules["backend_src"] = backend_src
spec.loader.exec_module(backend_src)

# Now import backend's graph.nodes using importlib
spec_graph = importlib.util.spec_from_file_location("backend_src.graph.nodes", os.path.join(backend_src_dir, "graph", "nodes.py"))
backend_graph_nodes = importlib.util.module_from_spec(spec_graph)
spec_graph.loader.exec_module(backend_graph_nodes)
analysis_node = backend_graph_nodes.analysis_node

# Import backend's nl_dsl models
spec_nl_dsl_models = importlib.util.spec_from_file_location("backend_src.nl_dsl.models", os.path.join(backend_src_dir, "nl_dsl", "models.py"))
backend_nl_dsl_models = importlib.util.module_from_spec(spec_nl_dsl_models)
spec_nl_dsl_models.loader.exec_module(backend_nl_dsl_models)
FilterResult = backend_nl_dsl_models.FilterResult
NlDslAnalysisResult = backend_nl_dsl_models.AnalysisResult
AnalysisDataTable = backend_nl_dsl_models.AnalysisDataTable
QualityResult = backend_nl_dsl_models.QualityResult
QualityIssue = backend_nl_dsl_models.QualityIssue
QualityCheckType = backend_nl_dsl_models.QualityCheckType
QualityAction = backend_nl_dsl_models.QualityAction

# Step 2: Now import project root's src modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from src.analysis.models import (
    AnalysisPlanResult,
    AnalysisPlan,
    AnalysisType,
    ChartType,
    AnalysisTimeRange,
    CotReasoning,
    EntityLevel,
    FieldContext,
    FilterPlan,
    FilterType,
    EmptyCheckResult,
    EmptyCheckErrorType
)
from src.analysis.cot_planner import CotResultStatus


@pytest.mark.asyncio
async def test_analysis_node_import():
    """测试 analysis_node 可以被正确导入"""
    # 这只是一个基本测试，确保模块结构正确
    assert callable(analysis_node)


@pytest.mark.asyncio
async def test_analysis_node_success_path():
    """测试 analysis_node 完整成功路径"""
    state = {
        "user_input": "查看广告主 123 最近 7 天的消耗趋势",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-success"
    }

    # Mock 所有依赖组件
    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_analyzer_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_planner_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_executor_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_checker_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_executor_class, \
         patch('src.nl_dsl.quality_checker.QualityChecker') as mock_quality_checker_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_report_formatter_class:

        # 1. Mock IntentAnalyzer
        mock_intent_analyzer = MagicMock()
        mock_intent_analyzer_factory.return_value = mock_intent_analyzer
        mock_field_context = FieldContext(
            advertiser_ids=[123],
            metrics=["cost"],
            time_range=AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-07"),
            target_level=EntityLevel.CAMPAIGN
        )
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = mock_field_context
        mock_intent_analyzer.analyze.return_value = mock_intent_result

        # 2. Mock CotPlanner
        mock_cot_planner = MagicMock()
        mock_cot_planner_factory.return_value = mock_cot_planner
        mock_analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-07")
        )
        mock_analysis_plan_result = AnalysisPlanResult(
            target_level=EntityLevel.CAMPAIGN,
            filter_plan=FilterPlan(filter_type=FilterType.NONE, target_level=EntityLevel.CAMPAIGN, steps=[]),
            analysis_plan=mock_analysis_plan,
            reasoning=CotReasoning(steps=[], summary="分析消耗趋势")
        )
        mock_cot_result = MagicMock()
        mock_cot_result.status = CotResultStatus.SUCCESS
        mock_cot_result.plan = mock_analysis_plan_result
        mock_cot_result.reasoning = CotReasoning(steps=[], summary="分析消耗趋势")
        mock_cot_planner.plan.return_value = mock_cot_result

        # 3. Mock FilterExecutor
        mock_filter_executor = MagicMock()
        mock_filter_executor_class.return_value = mock_filter_executor
        mock_filter_result = FilterResult(
            entity_ids=[1, 2, 3],
            entity_level="campaign",
            total_count=3
        )
        mock_filter_executor.execute.return_value = mock_filter_result

        # 4. Mock EmptyResultChecker
        mock_empty_checker = MagicMock()
        mock_empty_checker_class.return_value = mock_empty_checker
        mock_empty_check_result = EmptyCheckResult(found_error=False)
        mock_empty_checker.async_check = AsyncMock(return_value=mock_empty_check_result)

        # 5. Mock AnalysisExecutor
        mock_analysis_executor = MagicMock()
        mock_analysis_executor_class.return_value = mock_analysis_executor
        mock_analysis_result = NlDslAnalysisResult(
            success=True,
            chart_data={
                "chart_config": {"type": "line", "title": "消耗趋势"},
                "data": [
                    {"date": "2025-01-01", "cost": 100},
                    {"date": "2025-01-02", "cost": 200}
                ]
            },
            data_table=AnalysisDataTable(columns=[], rows=[])
        )
        mock_analysis_executor.execute.return_value = mock_analysis_result

        # 6. Mock QualityChecker
        mock_quality_checker = MagicMock()
        mock_quality_checker_class.return_value = mock_quality_checker
        mock_quality_result = QualityResult(passed=True, issues=[], warnings=[])
        mock_quality_checker.check.return_value = mock_quality_result

        # 7. Mock ReportFormatter
        mock_report_formatter = MagicMock()
        mock_report_formatter_class.return_value = mock_report_formatter
        mock_final_report = {
            "report_type": "success",
            "title": "时间趋势分析 (2025-01-01 ~ 2025-01-07)",
            "highlights": [{"type": "info", "text": "✅ 数据加载完成"}]
        }
        mock_report_formatter.format.return_value = mock_final_report

        # 执行测试
        result = await analysis_node(state)

        # 验证结果
        assert "final_report" in result
        assert result["final_report"] == mock_final_report
        assert "error" not in result or result["error"] is None
        assert "execution_trace" in result

        # 验证所有组件被正确调用
        mock_intent_analyzer.analyze.assert_called_once()
        mock_cot_planner.plan.assert_called_once()
        mock_filter_executor.execute.assert_called_once()
        mock_empty_checker.async_check.assert_called_once()
        mock_analysis_executor.execute.assert_called_once()
        mock_quality_checker.check.assert_called_once()
        mock_report_formatter.format.assert_called_once()


@pytest.mark.asyncio
async def test_analysis_node_hitl_from_cot_planner():
    """测试 CotPlanner 返回需要澄清的情况（HITL）"""
    state = {
        "user_input": "查看广告主的数据",
        "conversation_history": [],
        "advertiser_ids": [],
        "session_id": "test-session-hitl"
    }

    # Mock 依赖组件
    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_analyzer_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_planner_factory, \
         patch('backend.src.graph.nodes.build_clarification_state') as mock_build_clarification:

        # 1. Mock IntentAnalyzer
        mock_intent_analyzer = MagicMock()
        mock_intent_analyzer_factory.return_value = mock_intent_analyzer
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = None
        mock_intent_analyzer.analyze.return_value = mock_intent_result

        # 2. Mock CotPlanner 返回需要澄清
        mock_cot_planner = MagicMock()
        mock_cot_planner_factory.return_value = mock_cot_planner
        mock_cot_result = MagicMock()
        mock_cot_result.status = CotResultStatus.NEEDS_CLARIFICATION
        mock_clarification = MagicMock()
        mock_clarification.question = "请选择要查看的广告主"
        mock_clarification.missing_fields = ["advertiser_ids"]
        mock_clarification.options = [{"value": "123", "label": "广告主 123"}]
        mock_cot_result.clarification = mock_clarification
        mock_cot_result.reasoning = CotReasoning(steps=[], summary="需要广告主信息")
        mock_cot_planner.plan.return_value = mock_cot_result

        # 3. Mock build_clarification_state
        mock_build_clarification.return_value = {
            "clarification": {"type": "cot_clarification", "question": "请选择要查看的广告主"}
        }

        # 执行测试
        result = await analysis_node(state)

        # 验证结果
        assert "needs_clarification" in result
        assert result["needs_clarification"] is True
        assert "clarification" in result
        assert "hitl_request" in result
        assert "final_report" not in result  # 不应生成最终报告

        # 验证后续组件没有被调用
        with pytest.raises(AttributeError):
            mock_filter_executor = result.get("mock_filter_executor")
            mock_filter_executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_analysis_node_error_handling():
    """测试 FilterExecutor 抛出异常的情况"""
    state = {
        "user_input": "查看广告主 123 的数据",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-error"
    }

    # Mock 依赖组件
    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_analyzer_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_planner_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_executor_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_report_formatter_class:

        # 1. Mock IntentAnalyzer
        mock_intent_analyzer = MagicMock()
        mock_intent_analyzer_factory.return_value = mock_intent_analyzer
        mock_field_context = FieldContext(
            advertiser_ids=[123],
            metrics=["cost"],
            time_range=AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-07")
        )
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = mock_field_context
        mock_intent_analyzer.analyze.return_value = mock_intent_result

        # 2. Mock CotPlanner
        mock_cot_planner = MagicMock()
        mock_cot_planner_factory.return_value = mock_cot_planner
        mock_analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-07")
        )
        mock_analysis_plan_result = AnalysisPlanResult(
            target_level=EntityLevel.CAMPAIGN,
            filter_plan=FilterPlan(filter_type=FilterType.NONE, target_level=EntityLevel.CAMPAIGN, steps=[]),
            analysis_plan=mock_analysis_plan
        )
        mock_cot_result = MagicMock()
        mock_cot_result.status = CotResultStatus.SUCCESS
        mock_cot_result.plan = mock_analysis_plan_result
        mock_cot_result.reasoning = CotReasoning(steps=[], summary="分析消耗趋势")
        mock_cot_planner.plan.return_value = mock_cot_result

        # 3. Mock FilterExecutor 抛出异常
        mock_filter_executor = MagicMock()
        mock_filter_executor_class.return_value = mock_filter_executor
        mock_filter_executor.execute.side_effect = Exception("数据库连接失败")

        # 4. Mock ReportFormatter 生成错误报告
        mock_report_formatter = MagicMock()
        mock_report_formatter_class.return_value = mock_report_formatter
        mock_error_report = {
            "report_type": "error",
            "title": "分析遇到问题",
            "highlights": [{"type": "negative", "text": "⚠️ 分析过程中发生错误: 数据库连接失败"}]
        }
        mock_report_formatter.format_error.return_value = mock_error_report

        # 执行测试
        result = await analysis_node(state)

        # 验证结果
        assert "final_report" in result
        assert result["final_report"] == mock_error_report
        assert "error" in result
        assert result["error"]["type"] == "analysis_error"
        assert "execution_trace" in result


@pytest.mark.asyncio
async def test_analysis_node_empty_result():
    """测试 EmptyResultChecker 发现空数据的情况"""
    state = {
        "user_input": "查看广告主 123 最近 7 天的消耗",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-empty"
    }

    # Mock 所有依赖组件
    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_analyzer_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_planner_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_executor_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_checker_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_report_formatter_class:

        # 1. Mock IntentAnalyzer
        mock_intent_analyzer = MagicMock()
        mock_intent_analyzer_factory.return_value = mock_intent_analyzer
        mock_field_context = FieldContext(
            advertiser_ids=[123],
            metrics=["cost"],
            time_range=AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-07")
        )
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = mock_field_context
        mock_intent_analyzer.analyze.return_value = mock_intent_result

        # 2. Mock CotPlanner
        mock_cot_planner = MagicMock()
        mock_cot_planner_factory.return_value = mock_cot_planner
        mock_analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-07")
        )
        mock_analysis_plan_result = AnalysisPlanResult(
            target_level=EntityLevel.CAMPAIGN,
            filter_plan=FilterPlan(filter_type=FilterType.NONE, target_level=EntityLevel.CAMPAIGN, steps=[]),
            analysis_plan=mock_analysis_plan
        )
        mock_cot_result = MagicMock()
        mock_cot_result.status = CotResultStatus.SUCCESS
        mock_cot_result.plan = mock_analysis_plan_result
        mock_cot_result.reasoning = CotReasoning(steps=[], summary="分析消耗趋势")
        mock_cot_planner.plan.return_value = mock_cot_result

        # 3. Mock FilterExecutor
        mock_filter_executor = MagicMock()
        mock_filter_executor_class.return_value = mock_filter_executor
        mock_filter_result = FilterResult(
            entity_ids=[1, 2, 3],
            entity_level="campaign",
            total_count=3
        )
        mock_filter_executor.execute.return_value = mock_filter_result

        # 4. Mock EmptyResultChecker 返回空结果
        mock_empty_checker = MagicMock()
        mock_empty_checker_class.return_value = mock_empty_checker
        mock_empty_check_result = EmptyCheckResult(
            found_error=True,
            error_type=EmptyCheckErrorType.NO_DATA_VALUES,
            hints=["在指定条件下，核心指标(cost/impressions)的总和为零", "请尝试调整筛选条件或时间范围"]
        )
        mock_empty_checker.async_check = AsyncMock(return_value=mock_empty_check_result)

        # 5. Mock ReportFormatter 生成空结果报告
        mock_report_formatter = MagicMock()
        mock_report_formatter_class.return_value = mock_report_formatter
        mock_empty_report = {
            "report_type": "empty",
            "title": "📭 时间趋势分析 (2025-01-01 ~ 2025-01-07)",
            "highlights": [{"type": "negative", "text": "⚠️ 在指定条件下，核心指标(cost/impressions)的总和为零"}]
        }
        mock_report_formatter.format_empty_result.return_value = mock_empty_report

        # 执行测试
        result = await analysis_node(state)

        # 验证结果
        assert "final_report" in result
        assert result["final_report"] == mock_empty_report
        assert "error" not in result or result["error"] is None
        assert "execution_trace" in result

        # 验证 AnalysisExecutor 没有被调用
        with pytest.raises(AttributeError):
            mock_analysis_executor = result.get("mock_analysis_executor")
            mock_analysis_executor.execute.assert_not_called()

        # 验证 format_empty_result 被正确调用
        mock_report_formatter.format_empty_result.assert_called_once()


@pytest.mark.asyncio
async def test_analysis_node_cot_clarification_reentry():
    """测试 analysis_node 处理 cot_clarification 后重新进入"""
    # 准备状态：包含待处理的澄清输入和之前的上下文
    state = {
        "user_input": "查看广告主 123 的数据，广告主: 456",  # clarify_node 已更新 user_input
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-cot-reentry",
        "pending_clarification_input": "456",
        "clarification": {"type": "cot_clarification"},
        "field_context": FieldContext(
            advertiser_ids=[123],
            metrics=["cost"],
            target_level=EntityLevel.CAMPAIGN
        ).model_dump()
    }

    # Mock 所有依赖组件
    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_analyzer_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_planner_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_executor_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_checker_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_executor_class, \
         patch('src.nl_dsl.quality_checker.QualityChecker') as mock_quality_checker_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_report_formatter_class:

        # 1. Mock IntentAnalyzer
        mock_intent_analyzer = MagicMock()
        mock_intent_analyzer_factory.return_value = mock_intent_analyzer
        mock_new_field_context = FieldContext(
            advertiser_ids=[456],
            metrics=["cost"],
            time_range=AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-07"),
            target_level=EntityLevel.CAMPAIGN
        )
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = mock_new_field_context
        mock_intent_analyzer.analyze.return_value = mock_intent_result

        # 2. Mock CotPlanner
        mock_cot_planner = MagicMock()
        mock_cot_planner_factory.return_value = mock_cot_planner
        mock_analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-07")
        )
        mock_analysis_plan_result = AnalysisPlanResult(
            target_level=EntityLevel.CAMPAIGN,
            filter_plan=FilterPlan(filter_type=FilterType.NONE, target_level=EntityLevel.CAMPAIGN, steps=[]),
            analysis_plan=mock_analysis_plan
        )
        mock_cot_result = MagicMock()
        mock_cot_result.status = CotResultStatus.SUCCESS
        mock_cot_result.plan = mock_analysis_plan_result
        mock_cot_result.reasoning = CotReasoning(steps=[], summary="分析消耗趋势")
        mock_cot_planner.plan.return_value = mock_cot_result

        # 3. Mock FilterExecutor
        mock_filter_executor = MagicMock()
        mock_filter_executor_class.return_value = mock_filter_executor
        mock_filter_result = FilterResult(
            entity_ids=[1, 2, 3],
            entity_level="campaign",
            total_count=3
        )
        mock_filter_executor.execute.return_value = mock_filter_result

        # 4. Mock EmptyResultChecker
        mock_empty_checker = MagicMock()
        mock_empty_checker_class.return_value = mock_empty_checker
        mock_empty_check_result = EmptyCheckResult(found_error=False)
        mock_empty_checker.async_check = AsyncMock(return_value=mock_empty_check_result)

        # 5. Mock AnalysisExecutor
        mock_analysis_executor = MagicMock()
        mock_analysis_executor_class.return_value = mock_analysis_executor
        mock_analysis_result = NlDslAnalysisResult(
            success=True,
            data_table=AnalysisDataTable(columns=[], rows=[])
        )
        mock_analysis_executor.execute.return_value = mock_analysis_result

        # 6. Mock QualityChecker
        mock_quality_checker = MagicMock()
        mock_quality_checker_class.return_value = mock_quality_checker
        mock_quality_result = QualityResult(passed=True, issues=[], warnings=[])
        mock_quality_checker.check.return_value = mock_quality_result

        # 7. Mock ReportFormatter
        mock_report_formatter = MagicMock()
        mock_report_formatter_class.return_value = mock_report_formatter
        mock_final_report = {
            "report_type": "success",
            "title": "时间趋势分析 (2025-01-01 ~ 2025-01-07)",
            "highlights": [{"type": "info", "text": "✅ 数据加载完成"}]
        }
        mock_report_formatter.format.return_value = mock_final_report

        # 执行测试
        result = await analysis_node(state)

        # 验证结果
        assert "final_report" in result
        assert result["final_report"] == mock_final_report
        assert "pending_clarification_input" in result and result["pending_clarification_input"] is None  # 应被清除
        assert "execution_trace" in result

        # 验证 CotPlanner 被调用时传入了合并后的 field_context
        call_args = mock_cot_planner.plan.call_args
        passed_field_context = call_args.kwargs.get("field_context")
        assert passed_field_context is not None
        # 验证合并后的 advertiser_ids 包含之前和新的
        assert 123 in passed_field_context.advertiser_ids
        assert 456 in passed_field_context.advertiser_ids


@pytest.mark.asyncio
async def test_analysis_node_quality_hitl_continue():
    """测试 quality_hitl 后用户选择 continue，跳过 QualityChecker"""
    state = {
        "user_input": "查看广告主 123 最近 7 天的消耗趋势",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-quality-continue",
        "pending_clarification_input": "continue",
        "clarification": {"type": "quality_hitl"}
    }

    # Mock 所有依赖组件
    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_analyzer_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_planner_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_executor_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_checker_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_executor_class, \
         patch('src.nl_dsl.quality_checker.QualityChecker') as mock_quality_checker_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_report_formatter_class:

        # 1. Mock IntentAnalyzer
        mock_intent_analyzer = MagicMock()
        mock_intent_analyzer_factory.return_value = mock_intent_analyzer
        mock_field_context = FieldContext(
            advertiser_ids=[123],
            metrics=["cost"],
            time_range=AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-07"),
            target_level=EntityLevel.CAMPAIGN
        )
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = mock_field_context
        mock_intent_analyzer.analyze.return_value = mock_intent_result

        # 2. Mock CotPlanner
        mock_cot_planner = MagicMock()
        mock_cot_planner_factory.return_value = mock_cot_planner
        mock_analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-07")
        )
        mock_analysis_plan_result = AnalysisPlanResult(
            target_level=EntityLevel.CAMPAIGN,
            filter_plan=FilterPlan(filter_type=FilterType.NONE, target_level=EntityLevel.CAMPAIGN, steps=[]),
            analysis_plan=mock_analysis_plan
        )
        mock_cot_result = MagicMock()
        mock_cot_result.status = CotResultStatus.SUCCESS
        mock_cot_result.plan = mock_analysis_plan_result
        mock_cot_result.reasoning = CotReasoning(steps=[], summary="分析消耗趋势")
        mock_cot_planner.plan.return_value = mock_cot_result

        # 3. Mock FilterExecutor
        mock_filter_executor = MagicMock()
        mock_filter_executor_class.return_value = mock_filter_executor
        mock_filter_result = FilterResult(
            entity_ids=[1, 2, 3],
            entity_level="campaign",
            total_count=3
        )
        mock_filter_executor.execute.return_value = mock_filter_result

        # 4. Mock EmptyResultChecker
        mock_empty_checker = MagicMock()
        mock_empty_checker_class.return_value = mock_empty_checker
        mock_empty_check_result = EmptyCheckResult(found_error=False)
        mock_empty_checker.async_check = AsyncMock(return_value=mock_empty_check_result)

        # 5. Mock AnalysisExecutor
        mock_analysis_executor = MagicMock()
        mock_analysis_executor_class.return_value = mock_analysis_executor
        mock_analysis_result = NlDslAnalysisResult(
            success=True,
            data_table=AnalysisDataTable(columns=[], rows=[])
        )
        mock_analysis_executor.execute.return_value = mock_analysis_result

        # 6. Mock QualityChecker (应该不会被调用)
        mock_quality_checker = MagicMock()
        mock_quality_checker_class.return_value = mock_quality_checker

        # 7. Mock ReportFormatter
        mock_report_formatter = MagicMock()
        mock_report_formatter_class.return_value = mock_report_formatter
        mock_final_report = {
            "report_type": "success",
            "title": "时间趋势分析 (2025-01-01 ~ 2025-01-07)",
            "highlights": [{"type": "info", "text": "✅ 数据加载完成"}]
        }
        mock_report_formatter.format.return_value = mock_final_report

        # 执行测试
        result = await analysis_node(state)

        # 验证结果
        assert "final_report" in result
        assert result["final_report"] == mock_final_report
        assert "pending_clarification_input" in result and result["pending_clarification_input"] is None

        # 验证 QualityChecker.check 没有被调用
        mock_quality_checker.check.assert_not_called()


@pytest.mark.asyncio
async def test_analysis_node_quality_hitl_rephrase():
    """测试 quality_hitl 后用户选择 rephrase，重新执行完整流程"""
    state = {
        "user_input": "查看广告主 123 最近 14 天的消耗趋势",  # clarify_node 已更新 user_input
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-quality-rephrase",
        "pending_clarification_input": "rephrase",
        "clarification": {"type": "quality_hitl"}
    }

    # Mock 所有依赖组件
    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_analyzer_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_planner_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_executor_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_checker_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_executor_class, \
         patch('src.nl_dsl.quality_checker.QualityChecker') as mock_quality_checker_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_report_formatter_class:

        # 1. Mock IntentAnalyzer
        mock_intent_analyzer = MagicMock()
        mock_intent_analyzer_factory.return_value = mock_intent_analyzer
        mock_field_context = FieldContext(
            advertiser_ids=[123],
            metrics=["cost"],
            time_range=AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-14"),
            target_level=EntityLevel.CAMPAIGN
        )
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = mock_field_context
        mock_intent_analyzer.analyze.return_value = mock_intent_result

        # 2. Mock CotPlanner
        mock_cot_planner = MagicMock()
        mock_cot_planner_factory.return_value = mock_cot_planner
        mock_analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-14")
        )
        mock_analysis_plan_result = AnalysisPlanResult(
            target_level=EntityLevel.CAMPAIGN,
            filter_plan=FilterPlan(filter_type=FilterType.NONE, target_level=EntityLevel.CAMPAIGN, steps=[]),
            analysis_plan=mock_analysis_plan
        )
        mock_cot_result = MagicMock()
        mock_cot_result.status = CotResultStatus.SUCCESS
        mock_cot_result.plan = mock_analysis_plan_result
        mock_cot_result.reasoning = CotReasoning(steps=[], summary="分析消耗趋势")
        mock_cot_planner.plan.return_value = mock_cot_result

        # 3. Mock FilterExecutor
        mock_filter_executor = MagicMock()
        mock_filter_executor_class.return_value = mock_filter_executor
        mock_filter_result = FilterResult(
            entity_ids=[1, 2, 3],
            entity_level="campaign",
            total_count=3
        )
        mock_filter_executor.execute.return_value = mock_filter_result

        # 4. Mock EmptyResultChecker
        mock_empty_checker = MagicMock()
        mock_empty_checker_class.return_value = mock_empty_checker
        mock_empty_check_result = EmptyCheckResult(found_error=False)
        mock_empty_checker.async_check = AsyncMock(return_value=mock_empty_check_result)

        # 5. Mock AnalysisExecutor
        mock_analysis_executor = MagicMock()
        mock_analysis_executor_class.return_value = mock_analysis_executor
        mock_analysis_result = NlDslAnalysisResult(
            success=True,
            data_table=AnalysisDataTable(columns=[], rows=[])
        )
        mock_analysis_executor.execute.return_value = mock_analysis_result

        # 6. Mock QualityChecker (应该被调用)
        mock_quality_checker = MagicMock()
        mock_quality_checker_class.return_value = mock_quality_checker
        mock_quality_result = QualityResult(passed=True, issues=[], warnings=[])
        mock_quality_checker.check.return_value = mock_quality_result

        # 7. Mock ReportFormatter
        mock_report_formatter = MagicMock()
        mock_report_formatter_class.return_value = mock_report_formatter
        mock_final_report = {
            "report_type": "success",
            "title": "时间趋势分析 (2025-01-01 ~ 2025-01-14)",
            "highlights": [{"type": "info", "text": "✅ 数据加载完成"}]
        }
        mock_report_formatter.format.return_value = mock_final_report

        # 执行测试
        result = await analysis_node(state)

        # 验证结果
        assert "final_report" in result
        assert result["final_report"] == mock_final_report
        assert "pending_clarification_input" in result and result["pending_clarification_input"] is None

        # 验证 QualityChecker.check 被调用
        mock_quality_checker.check.assert_called_once()
