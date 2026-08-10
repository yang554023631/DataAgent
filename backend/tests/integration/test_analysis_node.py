"""测试 analysis_node - CoT 分析节点集成测试"""
import sys
import os
import types

# ============================================================================
# 设置合并的 src 包
#
# 项目有两个 src 目录：
#   /Users/simon/AL/DataAgent/src/          (项目根目录，包含 analysis/, nl_dsl/)
#   /Users/simon/AL/DataAgent/backend/src/  (后端目录，包含 graph/, intent/ 等)
#
# 两个目录都有 nl_dsl/ 子包，但内容不同：
#   根目录 src/nl_dsl/  —— filter_executor, analysis_executor, quality_checker, empty_checker, models
#   后端 backend/src/nl_dsl/ —— dsl_generator, dsl_validator, field_mapping 等
#
# 我们需要把两者合并成一个 src 命名空间，使得 analysis_node 内部的所有 import 都能正常工作。
# ============================================================================

# 计算路径
_integration_dir = os.path.dirname(os.path.abspath(__file__))
_tests_dir = os.path.dirname(_integration_dir)
_backend_dir = os.path.dirname(_tests_dir)
_project_root = os.path.dirname(_backend_dir)

_backend_src = os.path.join(_backend_dir, 'src')
_root_src = os.path.join(_project_root, 'src')

# 确保项目根目录在 sys.path 中（用于 conftest 等）
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# 创建合并的 src 模块
_src_mod = types.ModuleType('src')
_src_mod.__path__ = [_root_src, _backend_src]
sys.modules['src'] = _src_mod

# 合并 nl_dsl 子包（两个目录都有 nl_dsl，需合并 __path__）
_nl_dsl_mod = types.ModuleType('src.nl_dsl')
_nl_dsl_mod.__path__ = [
    os.path.join(_root_src, 'nl_dsl'),
    os.path.join(_backend_src, 'nl_dsl'),
]
sys.modules['src.nl_dsl'] = _nl_dsl_mod

# 合并 graph 子包
_graph_mod = types.ModuleType('src.graph')
_graph_mod.__path__ = [os.path.join(_backend_src, 'graph')]
sys.modules['src.graph'] = _graph_mod

# 合并 analysis 子包
_analysis_mod = types.ModuleType('src.analysis')
_analysis_mod.__path__ = [os.path.join(_root_src, 'analysis')]
sys.modules['src.analysis'] = _analysis_mod

# 合并 intent 子包（build_clarification_state 等）
_intent_mod = types.ModuleType('src.intent')
_intent_mod.__path__ = [os.path.join(_backend_src, 'intent')]
sys.modules['src.intent'] = _intent_mod

# 合并 tools 子包（es_client 等）
_tools_mod = types.ModuleType('src.tools')
_tools_mod.__path__ = [os.path.join(_backend_src, 'tools')]
sys.modules['src.tools'] = _tools_mod

# 合并 services 子包
_services_mod = types.ModuleType('src.services')
_services_mod.__path__ = [os.path.join(_backend_src, 'services')]
sys.modules['src.services'] = _services_mod

# 合并 rag 子包
_rag_mod = types.ModuleType('src.rag')
_rag_mod.__path__ = [os.path.join(_backend_src, 'rag')]
sys.modules['src.rag'] = _rag_mod

# 合并 agents 子包
_agents_mod = types.ModuleType('src.agents')
_agents_mod.__path__ = [os.path.join(_backend_src, 'agents')]
sys.modules['src.agents'] = _agents_mod

# 合并 config 子包
_config_mod = types.ModuleType('src.config')
_config_mod.__path__ = [os.path.join(_backend_src, 'config')]
sys.modules['src.config'] = _config_mod

# ============================================================================
# 现在导入 analysis_node 和相关模型
# ============================================================================

from src.graph.nodes import analysis_node

# 导入 analysis 相关模型
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
    EmptyCheckErrorType,
)

# 导入 nl_dsl 相关模型
from src.nl_dsl.models import (
    FilterResult,
    AnalysisResult as NlDslAnalysisResult,
    AnalysisDataTable,
    QualityResult,
    QualityIssue,
    QualityCheckType,
    QualityAction,
)

from src.analysis.cot_planner import CotResultStatus

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


# ============================================================================
# 辅助函数
# ============================================================================

def _make_field_context(advertiser_ids=None, metrics=None, time_range=None, target_level=None):
    """构造 FieldContext 的便捷函数"""
    return FieldContext(
        advertiser_ids=advertiser_ids or [123],
        metrics=metrics or ["cost"],
        time_range=time_range or AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-07"),
        target_level=target_level or EntityLevel.CAMPAIGN,
    )


def _make_analysis_plan(analysis_type=None, metrics=None, time_range=None, chart_type=None):
    """构造 AnalysisPlan 的便捷函数"""
    return AnalysisPlan(
        analysis_type=analysis_type or AnalysisType.TIME_TREND,
        chart_type=chart_type or ChartType.LINE,
        metrics=metrics or ["cost"],
        time_range=time_range or AnalysisTimeRange(start_date="2025-01-01", end_date="2025-01-07"),
    )


def _make_plan_result(analysis_plan=None, filter_plan=None, target_level=None):
    """构造 AnalysisPlanResult 的便捷函数"""
    ap = analysis_plan or _make_analysis_plan()
    fp = filter_plan or FilterPlan(
        filter_type=FilterType.NONE,
        target_level=EntityLevel.CAMPAIGN.value,
        steps=[]
    )
    return AnalysisPlanResult(
        target_level=target_level or EntityLevel.CAMPAIGN,
        filter_plan=fp,
        analysis_plan=ap,
        reasoning=CotReasoning(steps=[], summary="分析消耗趋势")
    )


def _make_cot_success(plan_result=None):
    """构造成功的 CotPlanner 返回值"""
    mock_cot = MagicMock()
    mock_cot.status = CotResultStatus.SUCCESS
    mock_cot.plan = plan_result or _make_plan_result()
    mock_cot.reasoning = CotReasoning(steps=[], summary="分析消耗趋势")
    return mock_cot


def _make_filter_result(entity_ids=None, entity_level="campaign", total_count=None):
    """构造 FilterResult 的便捷函数"""
    eids = entity_ids if entity_ids is not None else [1, 2, 3]
    return FilterResult(
        entity_ids=eids,
        entity_level=entity_level,
        total_count=total_count if total_count is not None else len(eids),
    )


def _make_analysis_result(success=True, chart_data=None, data_table=None):
    """构造 NlDslAnalysisResult 的便捷函数"""
    if chart_data is None and success:
        chart_data = {
            "chart_config": {"type": "line", "title": "消耗趋势"},
            "data": [
                {"date": "2025-01-01", "cost": 100},
                {"date": "2025-01-02", "cost": 200}
            ]
        }
    if data_table is None:
        data_table = AnalysisDataTable(columns=[], rows=[])
    return NlDslAnalysisResult(
        success=success,
        chart_data=chart_data,
        data_table=data_table,
    )


# ============================================================================
# 基础导入测试
# ============================================================================

@pytest.mark.asyncio
async def test_analysis_node_import():
    """测试 analysis_node 可以被正确导入"""
    assert callable(analysis_node)


# ============================================================================
# 已有测试（保留并修复）
# ============================================================================

@pytest.mark.asyncio
async def test_analysis_node_success_path():
    """测试 analysis_node 完整成功路径"""
    state = {
        "user_input": "查看广告主 123 最近 7 天的消耗趋势",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-success"
    }

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
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context()
        mock_intent_analyzer.analyze.return_value = mock_intent_result

        # 2. Mock CotPlanner
        mock_cot_planner = MagicMock()
        mock_cot_planner_factory.return_value = mock_cot_planner
        mock_cot_planner.plan.return_value = _make_cot_success()

        # 3. Mock FilterExecutor
        mock_filter_executor = MagicMock()
        mock_filter_executor_class.return_value = mock_filter_executor
        mock_filter_executor.execute.return_value = _make_filter_result()

        # 4. Mock EmptyResultChecker
        mock_empty_checker = MagicMock()
        mock_empty_checker_class.return_value = mock_empty_checker
        mock_empty_checker.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # 5. Mock AnalysisExecutor
        mock_analysis_executor = MagicMock()
        mock_analysis_executor_class.return_value = mock_analysis_executor
        mock_analysis_executor.execute.return_value = _make_analysis_result()

        # 6. Mock QualityChecker
        mock_quality_checker = MagicMock()
        mock_quality_checker_class.return_value = mock_quality_checker
        mock_quality_checker.check.return_value = QualityResult(passed=True, issues=[], warnings=[])

        # 7. Mock ReportFormatter
        mock_report_formatter = MagicMock()
        mock_report_formatter_class.return_value = mock_report_formatter
        mock_final_report = {
            "report_type": "success",
            "title": "时间趋势分析 (2025-01-01 ~ 2025-01-07)",
            "highlights": [{"type": "info", "text": "✅ 数据加载完成"}]
        }
        mock_report_formatter.format.return_value = mock_final_report

        result = await analysis_node(state)

        assert "final_report" in result
        assert result["final_report"] == mock_final_report
        assert "error" not in result or result["error"] is None
        assert "execution_trace" in result

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

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_analyzer_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_planner_factory, \
         patch('src.graph.nodes.build_clarification_state') as mock_build_clarification:

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

        result = await analysis_node(state)

        assert "needs_clarification" in result
        assert result["needs_clarification"] is True
        assert "clarification" in result
        assert "hitl_request" in result
        assert "final_report" not in result


@pytest.mark.asyncio
async def test_analysis_node_error_handling():
    """测试 FilterExecutor 抛出异常的情况"""
    state = {
        "user_input": "查看广告主 123 的数据",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-error"
    }

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_analyzer_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_planner_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_executor_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_report_formatter_class:

        # 1. Mock IntentAnalyzer
        mock_intent_analyzer = MagicMock()
        mock_intent_analyzer_factory.return_value = mock_intent_analyzer
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context()
        mock_intent_analyzer.analyze.return_value = mock_intent_result

        # 2. Mock CotPlanner
        mock_cot_planner = MagicMock()
        mock_cot_planner_factory.return_value = mock_cot_planner
        mock_cot_planner.plan.return_value = _make_cot_success()

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

        result = await analysis_node(state)

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

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_analyzer_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_planner_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_executor_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_checker_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_report_formatter_class:

        # 1. Mock IntentAnalyzer
        mock_intent_analyzer = MagicMock()
        mock_intent_analyzer_factory.return_value = mock_intent_analyzer
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context()
        mock_intent_analyzer.analyze.return_value = mock_intent_result

        # 2. Mock CotPlanner
        mock_cot_planner = MagicMock()
        mock_cot_planner_factory.return_value = mock_cot_planner
        mock_cot_planner.plan.return_value = _make_cot_success()

        # 3. Mock FilterExecutor
        mock_filter_executor = MagicMock()
        mock_filter_executor_class.return_value = mock_filter_executor
        mock_filter_executor.execute.return_value = _make_filter_result()

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

        result = await analysis_node(state)

        assert "final_report" in result
        assert result["final_report"] == mock_empty_report
        assert "error" not in result or result["error"] is None
        assert "execution_trace" in result
        mock_report_formatter.format_empty_result.assert_called_once()


@pytest.mark.asyncio
async def test_analysis_node_cot_clarification_reentry():
    """测试 analysis_node 处理 cot_clarification 后重新进入"""
    state = {
        "user_input": "查看广告主 123 的数据，广告主: 456",
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
        mock_cot_planner.plan.return_value = _make_cot_success()

        # 3. Mock FilterExecutor
        mock_filter_executor = MagicMock()
        mock_filter_executor_class.return_value = mock_filter_executor
        mock_filter_executor.execute.return_value = _make_filter_result()

        # 4. Mock EmptyResultChecker
        mock_empty_checker = MagicMock()
        mock_empty_checker_class.return_value = mock_empty_checker
        mock_empty_checker.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # 5. Mock AnalysisExecutor
        mock_analysis_executor = MagicMock()
        mock_analysis_executor_class.return_value = mock_analysis_executor
        mock_analysis_executor.execute.return_value = _make_analysis_result()

        # 6. Mock QualityChecker
        mock_quality_checker = MagicMock()
        mock_quality_checker_class.return_value = mock_quality_checker
        mock_quality_checker.check.return_value = QualityResult(passed=True, issues=[], warnings=[])

        # 7. Mock ReportFormatter
        mock_report_formatter = MagicMock()
        mock_report_formatter_class.return_value = mock_report_formatter
        mock_final_report = {
            "report_type": "success",
            "title": "时间趋势分析 (2025-01-01 ~ 2025-01-07)",
            "highlights": [{"type": "info", "text": "✅ 数据加载完成"}]
        }
        mock_report_formatter.format.return_value = mock_final_report

        result = await analysis_node(state)

        assert "final_report" in result
        assert result["final_report"] == mock_final_report
        assert "pending_clarification_input" in result and result["pending_clarification_input"] is None
        assert "execution_trace" in result

        # 验证 CotPlanner 被调用时传入了合并后的 field_context
        call_args = mock_cot_planner.plan.call_args
        passed_field_context = call_args.kwargs.get("field_context")
        assert passed_field_context is not None
        # 验证 metrics 被合并
        assert "cost" in passed_field_context.metrics
        # 验证 time_range 来自新提取的 field_context
        assert passed_field_context.time_range is not None
        assert passed_field_context.time_range.start_date == "2025-01-01"
        # 验证 target_level 被保留
        assert passed_field_context.target_level == EntityLevel.CAMPAIGN


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
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context()
        mock_intent_analyzer.analyze.return_value = mock_intent_result

        # 2. Mock CotPlanner
        mock_cot_planner = MagicMock()
        mock_cot_planner_factory.return_value = mock_cot_planner
        mock_cot_planner.plan.return_value = _make_cot_success()

        # 3. Mock FilterExecutor
        mock_filter_executor = MagicMock()
        mock_filter_executor_class.return_value = mock_filter_executor
        mock_filter_executor.execute.return_value = _make_filter_result()

        # 4. Mock EmptyResultChecker
        mock_empty_checker = MagicMock()
        mock_empty_checker_class.return_value = mock_empty_checker
        mock_empty_checker.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # 5. Mock AnalysisExecutor
        mock_analysis_executor = MagicMock()
        mock_analysis_executor_class.return_value = mock_analysis_executor
        mock_analysis_executor.execute.return_value = _make_analysis_result()

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

        result = await analysis_node(state)

        assert "final_report" in result
        assert result["final_report"] == mock_final_report
        assert "pending_clarification_input" in result and result["pending_clarification_input"] is None

        # 验证 QualityChecker.check 没有被调用
        mock_quality_checker.check.assert_not_called()


@pytest.mark.asyncio
async def test_analysis_node_quality_hitl_rephrase():
    """测试 quality_hitl 后用户选择 rephrase，重新执行完整流程"""
    state = {
        "user_input": "查看广告主 123 最近 14 天的消耗趋势",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-quality-rephrase",
        "pending_clarification_input": "rephrase",
        "clarification": {"type": "quality_hitl"}
    }

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
        mock_filter_executor.execute.return_value = _make_filter_result()

        # 4. Mock EmptyResultChecker
        mock_empty_checker = MagicMock()
        mock_empty_checker_class.return_value = mock_empty_checker
        mock_empty_checker.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # 5. Mock AnalysisExecutor
        mock_analysis_executor = MagicMock()
        mock_analysis_executor_class.return_value = mock_analysis_executor
        mock_analysis_executor.execute.return_value = _make_analysis_result()

        # 6. Mock QualityChecker (应该被调用)
        mock_quality_checker = MagicMock()
        mock_quality_checker_class.return_value = mock_quality_checker
        mock_quality_checker.check.return_value = QualityResult(passed=True, issues=[], warnings=[])

        # 7. Mock ReportFormatter
        mock_report_formatter = MagicMock()
        mock_report_formatter_class.return_value = mock_report_formatter
        mock_final_report = {
            "report_type": "success",
            "title": "时间趋势分析 (2025-01-01 ~ 2025-01-14)",
            "highlights": [{"type": "info", "text": "✅ 数据加载完成"}]
        }
        mock_report_formatter.format.return_value = mock_final_report

        result = await analysis_node(state)

        assert "final_report" in result
        assert result["final_report"] == mock_final_report
        assert "pending_clarification_input" in result and result["pending_clarification_input"] is None
        mock_quality_checker.check.assert_called_once()


# ============================================================================
# 新增测试：A. analysis_node 边缘场景
# ============================================================================

@pytest.mark.asyncio
async def test_analysis_node_zero_entities_filter_result():
    """测试筛选结果为 0 个实体（空列表）但 EmptyResultChecker 未发现错误的边界情况

    场景：FilterResult.entity_ids 为空列表，但 EmptyResultChecker 没有发现错误
    （例如 filter_type=none 时 entity_ids 为空但 empty_checker 只检查 ES 数据存在性）。
    此时 AnalysisExecutor 应收到空 entity_ids 并正常执行。
    """
    state = {
        "user_input": "查看广告主 123 最近 7 天的消耗趋势",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-zero-entities"
    }

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_class, \
         patch('src.nl_dsl.quality_checker.QualityChecker') as mock_quality_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_formatter_class:

        # IntentAnalyzer
        mock_intent = MagicMock()
        mock_intent_factory.return_value = mock_intent
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context()
        mock_intent.analyze.return_value = mock_intent_result

        # CotPlanner
        mock_cot = MagicMock()
        mock_cot_factory.return_value = mock_cot
        mock_cot.plan.return_value = _make_cot_success()

        # FilterExecutor: 返回空 entity_ids
        mock_filter = MagicMock()
        mock_filter_class.return_value = mock_filter
        empty_filter = _make_filter_result(entity_ids=[], total_count=0)
        mock_filter.execute.return_value = empty_filter

        # EmptyResultChecker: 通过（未发现错误）
        mock_empty = MagicMock()
        mock_empty_class.return_value = mock_empty
        mock_empty.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # AnalysisExecutor: 用空 entity_ids 执行
        mock_analysis = MagicMock()
        mock_analysis_class.return_value = mock_analysis
        mock_analysis.execute.return_value = _make_analysis_result(
            chart_data={
                "chart_config": {"type": "line", "title": "消耗趋势"},
                "data": []
            }
        )

        # QualityChecker
        mock_quality = MagicMock()
        mock_quality_class.return_value = mock_quality
        mock_quality.check.return_value = QualityResult(passed=True, issues=[], warnings=[])

        # ReportFormatter
        mock_formatter = MagicMock()
        mock_formatter_class.return_value = mock_formatter
        mock_report = {"report_type": "success", "title": "测试", "highlights": []}
        mock_formatter.format.return_value = mock_report

        result = await analysis_node(state)

        assert "final_report" in result
        assert result["final_report"] == mock_report
        assert "execution_trace" in result

        # 验证 FilterExecutor 被调用且 AnalysisExecutor 收到了空 entity_ids
        mock_filter.execute.assert_called_once()
        mock_analysis.execute.assert_called_once()
        analysis_call_args = mock_analysis.execute.call_args
        assert analysis_call_args.kwargs.get("entity_ids") == []


@pytest.mark.asyncio
async def test_analysis_node_single_entity_boundary():
    """测试只有 1 个实体的边界情况（多系列检查的边界）

    当只有 1 个实体时，质量检查中的 max_series_count 等检查
    应该处于边界值（刚好通过）。本测试验证单实体场景下
    整个流程能正常完成。
    """
    state = {
        "user_input": "查看广告主 123 最近 7 天计划 999 的消耗趋势",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-single-entity"
    }

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_class, \
         patch('src.nl_dsl.quality_checker.QualityChecker') as mock_quality_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_formatter_class:

        # IntentAnalyzer
        mock_intent = MagicMock()
        mock_intent_factory.return_value = mock_intent
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context(
            metrics=["cost", "impressions"]
        )
        mock_intent.analyze.return_value = mock_intent_result

        # CotPlanner
        mock_cot = MagicMock()
        mock_cot_factory.return_value = mock_cot
        single_entity_plan = _make_plan_result(
            analysis_plan=_make_analysis_plan(
                analysis_type=AnalysisType.TIME_TREND,
                metrics=["cost"]
            ),
            filter_plan=FilterPlan(
                filter_type=FilterType.WHERE,
                target_level=EntityLevel.CAMPAIGN.value,
                steps=[]
            ),
        )
        mock_cot.plan.return_value = _make_cot_success(plan_result=single_entity_plan)

        # FilterExecutor: 返回单个实体
        mock_filter = MagicMock()
        mock_filter_class.return_value = mock_filter
        mock_filter.execute.return_value = _make_filter_result(
            entity_ids=[999], entity_level="campaign", total_count=1
        )

        # EmptyResultChecker
        mock_empty = MagicMock()
        mock_empty_class.return_value = mock_empty
        mock_empty.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # AnalysisExecutor: 单实体的数据
        mock_analysis = MagicMock()
        mock_analysis_class.return_value = mock_analysis
        mock_analysis.execute.return_value = _make_analysis_result(
            chart_data={
                "chart_config": {"type": "line", "title": "计划 999 消耗趋势", "series": [{"name": "计划 999"}]},
                "data": [
                    {"date": "2025-01-01", "cost": 100, "entity_id": 999},
                    {"date": "2025-01-02", "cost": 150, "entity_id": 999},
                    {"date": "2025-01-03", "cost": 200, "entity_id": 999},
                ]
            }
        )

        # QualityChecker: 单实体通过（没有 max_series 问题）
        mock_quality = MagicMock()
        mock_quality_class.return_value = mock_quality
        mock_quality.check.return_value = QualityResult(
            passed=True,
            issues=[],
            warnings=["仅 1 个实体，数据仅供参考"]
        )

        # ReportFormatter
        mock_formatter = MagicMock()
        mock_formatter_class.return_value = mock_formatter
        mock_report = {"report_type": "success", "title": "单实体趋势分析", "highlights": []}
        mock_formatter.format.return_value = mock_report

        result = await analysis_node(state)

        assert "final_report" in result
        assert result["final_report"] == mock_report
        assert "execution_trace" in result

        # 验证单个实体正确传递
        analysis_call = mock_analysis.execute.call_args
        assert analysis_call.kwargs.get("entity_ids") == [999]
        mock_quality.check.assert_called_once()


@pytest.mark.asyncio
async def test_analysis_node_quality_multiple_issues_mixed_severity():
    """测试质量检查返回多个问题（混合 warning + error/HITL）

    当 QualityChecker 返回多个不同严重级别的问题时：
    - severity == "warning" 的问题不触发 HITL
    - severity == "error" 且 suggested_action == "hitl" 的问题触发 HITL
    只要有一个 error + hitl 的问题，就应该触发 quality HITL。
    """
    state = {
        "user_input": "查看广告主 123 最近 7 天各计划的消耗排名",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-quality-mixed"
    }

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_class, \
         patch('src.nl_dsl.quality_checker.QualityChecker') as mock_quality_class, \
         patch('src.graph.nodes.build_clarification_state') as mock_build_clar:

        # IntentAnalyzer
        mock_intent = MagicMock()
        mock_intent_factory.return_value = mock_intent
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context(
            metrics=["cost"], target_level=EntityLevel.CAMPAIGN
        )
        mock_intent.analyze.return_value = mock_intent_result

        # CotPlanner
        mock_cot = MagicMock()
        mock_cot_factory.return_value = mock_cot
        plan = _make_plan_result(
            analysis_plan=_make_analysis_plan(
                analysis_type=AnalysisType.ENTITY_TABLE,
                chart_type=ChartType.TABLE,
                metrics=["cost"]
            ),
            filter_plan=FilterPlan(
                filter_type=FilterType.NONE,
                target_level=EntityLevel.CAMPAIGN.value,
                steps=[]
            ),
        )
        mock_cot.plan.return_value = _make_cot_success(plan_result=plan)

        # FilterExecutor
        mock_filter = MagicMock()
        mock_filter_class.return_value = mock_filter
        # 50 个实体（超过某些阈值）
        many_entities = list(range(1, 51))
        mock_filter.execute.return_value = _make_filter_result(
            entity_ids=many_entities, entity_level="campaign", total_count=50
        )

        # EmptyResultChecker
        mock_empty = MagicMock()
        mock_empty_class.return_value = mock_empty
        mock_empty.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # AnalysisExecutor
        mock_analysis = MagicMock()
        mock_analysis_class.return_value = mock_analysis
        mock_analysis.execute.return_value = _make_analysis_result(
            chart_data={
                "chart_config": {"type": "bar", "title": "消耗排名"},
                "data": [{"campaign_id": i, "cost": i * 100} for i in range(1, 51)]
            }
        )

        # QualityChecker: 混合严重级别的多个问题
        mock_quality = MagicMock()
        mock_quality_class.return_value = mock_quality
        mixed_quality_result = QualityResult(
            passed=False,
            issues=[
                QualityIssue(
                    check_type=QualityCheckType.MAX_ROWS,
                    severity="warning",
                    message="数据行数较多，建议关注前 N 条",
                    suggested_action=QualityAction.WARN,
                    threshold=30,
                    actual=50,
                ),
                QualityIssue(
                    check_type=QualityCheckType.MAX_CATEGORIES,
                    severity="error",
                    message="分类数量过多，可能影响图表可读性",
                    suggested_action=QualityAction.HITL,
                    threshold=20,
                    actual=50,
                ),
                QualityIssue(
                    check_type=QualityCheckType.MIN_DATA_POINTS,
                    severity="warning",
                    message="部分系列数据点较少，趋势可能不稳定",
                    suggested_action=QualityAction.WARN,
                ),
            ],
            warnings=[
                "数据行数较多",
                "部分系列数据点较少"
            ],
            actions=[QualityAction.WARN, QualityAction.HITL]
        )
        mock_quality.check.return_value = mixed_quality_result

        # build_clarification_state mock
        mock_build_clar.return_value = {
            "clarification": {
                "type": "quality_hitl",
                "question": "数据质量存在问题，是否继续查看结果？",
                "options": [
                    {"value": "continue", "label": "继续查看结果"},
                    {"value": "rephrase", "label": "重新表述问题"}
                ],
            }
        }

        result = await analysis_node(state)

        # 验证触发了 HITL
        assert result.get("needs_clarification") is True
        assert "hitl_request" in result
        assert result["clarification"]["type"] == "quality_hitl"

        # 验证 HITL 请求中包含所有质量问题信息
        hitl = result["hitl_request"]
        assert "quality_issues" in hitl
        assert len(hitl["quality_issues"]) == 3  # 三个问题都应该展示给用户

        # 验证问题类型正确
        issue_types = [q["type"] for q in hitl["quality_issues"]]
        assert QualityCheckType.MAX_ROWS.value in issue_types
        assert QualityCheckType.MAX_CATEGORIES.value in issue_types
        assert QualityCheckType.MIN_DATA_POINTS.value in issue_types

        # 验证 final_report 还没有生成（等待 HITL）
        assert "final_report" not in result

        # 验证执行追踪
        trace = result["execution_trace"]
        quality_steps = [s for s in trace if s["step"] == "quality_checker"]
        assert len(quality_steps) >= 1
        last_quality = quality_steps[-1]
        assert last_quality["status"] == "hitl_required"


@pytest.mark.asyncio
async def test_analysis_node_quality_hitl_skip_trace():
    """测试 quality_hitl continue 路径的 execution_trace 中包含 skipped 标记

    验证 quality_checker 步骤在 trace 中被标记为 skipped，
    并且 quality_result 被设置为空 issues 的结果。
    """
    state = {
        "user_input": "查看广告主 123 最近 7 天的消耗趋势",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-quality-skip-trace",
        "pending_clarification_input": "continue",
        "clarification": {"type": "quality_hitl"}
    }

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_class, \
         patch('src.nl_dsl.quality_checker.QualityChecker') as mock_quality_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_formatter_class:

        # IntentAnalyzer
        mock_intent = MagicMock()
        mock_intent_factory.return_value = mock_intent
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context()
        mock_intent.analyze.return_value = mock_intent_result

        # CotPlanner
        mock_cot = MagicMock()
        mock_cot_factory.return_value = mock_cot
        mock_cot.plan.return_value = _make_cot_success()

        # FilterExecutor
        mock_filter = MagicMock()
        mock_filter_class.return_value = mock_filter
        mock_filter.execute.return_value = _make_filter_result()

        # EmptyResultChecker
        mock_empty = MagicMock()
        mock_empty_class.return_value = mock_empty
        mock_empty.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # AnalysisExecutor
        mock_analysis = MagicMock()
        mock_analysis_class.return_value = mock_analysis
        mock_analysis.execute.return_value = _make_analysis_result()

        # QualityChecker: 不应该被调用
        mock_quality = MagicMock()
        mock_quality_class.return_value = mock_quality

        # ReportFormatter
        mock_formatter = MagicMock()
        mock_formatter_class.return_value = mock_formatter
        mock_report = {"report_type": "success", "title": "测试", "highlights": []}
        mock_formatter.format.return_value = mock_report

        result = await analysis_node(state)

        # 验证结果成功
        assert "final_report" in result
        assert result["pending_clarification_input"] is None

        # 验证 quality_checker 步骤在 trace 中标记为 skipped
        trace = result["execution_trace"]
        quality_steps = [s for s in trace if s["step"] == "quality_checker"]
        assert len(quality_steps) == 1
        assert quality_steps[0]["status"] == "skipped"

        # 验证 quality_result 被设置（空 issues）
        assert "quality_result" in result
        assert result["quality_result"]["issues"] == []

        # 验证 QualityChecker.check 从未被调用
        mock_quality.check.assert_not_called()


@pytest.mark.asyncio
async def test_analysis_node_with_derived_metrics():
    """测试包含衍生指标（CTR, CVR）的分析

    验证当分析计划包含衍生指标（如 CTR = clicks/impressions,
    CVR = conversions/clicks）时，整个流程正常工作，
    并且最终报告中正确包含衍生指标数据。
    """
    state = {
        "user_input": "查看广告主 123 最近 7 天的 CTR 和 CVR 趋势",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-derived-metrics"
    }

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_class, \
         patch('src.nl_dsl.quality_checker.QualityChecker') as mock_quality_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_formatter_class:

        # IntentAnalyzer: 提取出 CTR, CVR
        mock_intent = MagicMock()
        mock_intent_factory.return_value = mock_intent
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context(
            metrics=["ctr", "cvr", "clicks", "impressions", "conversions"]
        )
        mock_intent.analyze.return_value = mock_intent_result

        # CotPlanner: 生成包含衍生指标的计划
        mock_cot = MagicMock()
        mock_cot_factory.return_value = mock_cot
        derived_plan = _make_plan_result(
            analysis_plan=_make_analysis_plan(
                analysis_type=AnalysisType.TIME_TREND,
                chart_type=ChartType.LINE,
                metrics=["ctr", "cvr"]
            ),
        )
        mock_cot.plan.return_value = _make_cot_success(plan_result=derived_plan)

        # FilterExecutor
        mock_filter = MagicMock()
        mock_filter_class.return_value = mock_filter
        mock_filter.execute.return_value = _make_filter_result()

        # EmptyResultChecker
        mock_empty = MagicMock()
        mock_empty_class.return_value = mock_empty
        mock_empty.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # AnalysisExecutor: 返回包含衍生指标计算结果的数据
        mock_analysis = MagicMock()
        mock_analysis_class.return_value = mock_analysis
        derived_result = _make_analysis_result(
            chart_data={
                "chart_config": {
                    "type": "line",
                    "title": "CTR & CVR 趋势",
                    "series": [
                        {"name": "CTR", "unit": "%"},
                        {"name": "CVR", "unit": "%"},
                    ]
                },
                "data": [
                    {"date": "2025-01-01", "ctr": 0.052, "cvr": 0.021, "clicks": 1000, "impressions": 19200, "conversions": 21},
                    {"date": "2025-01-02", "ctr": 0.048, "cvr": 0.025, "clicks": 950, "impressions": 19800, "conversions": 24},
                    {"date": "2025-01-03", "ctr": 0.055, "cvr": 0.018, "clicks": 1100, "impressions": 20000, "conversions": 20},
                ]
            }
        )
        mock_analysis.execute.return_value = derived_result

        # QualityChecker
        mock_quality = MagicMock()
        mock_quality_class.return_value = mock_quality
        mock_quality.check.return_value = QualityResult(passed=True, issues=[], warnings=[])

        # ReportFormatter
        mock_formatter = MagicMock()
        mock_formatter_class.return_value = mock_formatter
        mock_report = {
            "report_type": "success",
            "title": "CTR & CVR 趋势分析 (2025-01-01 ~ 2025-01-07)",
            "highlights": [{"type": "info", "text": "✅ 数据加载完成，包含 CTR 和 CVR 衍生指标"}],
            "metrics": ["ctr", "cvr"],
            "derived_metrics": ["ctr", "cvr"],
        }
        mock_formatter.format.return_value = mock_report

        result = await analysis_node(state)

        assert "final_report" in result
        report = result["final_report"]
        assert report == mock_report
        assert report["report_type"] == "success"

        # 验证 chart_data 传递给了 ReportFormatter
        format_call = mock_formatter.format.call_args
        passed_analysis_result = format_call.kwargs.get("analysis_result")
        assert passed_analysis_result is not None
        chart_data = passed_analysis_result.chart_data
        assert chart_data is not None
        # 验证数据中包含衍生指标字段
        first_row = chart_data["data"][0]
        assert "ctr" in first_row
        assert "cvr" in first_row


@pytest.mark.asyncio
async def test_analysis_node_filter_type_none_all_entities():
    """测试 filter_type=none（不做筛选，使用所有实体）

    当 filter_type 为 NONE 时，FilterExecutor 应返回该层级下的所有实体，
    流程正常执行。这是最常见的场景。
    """
    state = {
        "user_input": "查看广告主 123 最近 7 天所有计划的消耗",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-filter-none"
    }

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_class, \
         patch('src.nl_dsl.quality_checker.QualityChecker') as mock_quality_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_formatter_class:

        # IntentAnalyzer
        mock_intent = MagicMock()
        mock_intent_factory.return_value = mock_intent
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context(
            metrics=["cost"], target_level=EntityLevel.CAMPAIGN
        )
        mock_intent.analyze.return_value = mock_intent_result

        # CotPlanner: filter_type=none
        mock_cot = MagicMock()
        mock_cot_factory.return_value = mock_cot
        plan_none = _make_plan_result(
            analysis_plan=_make_analysis_plan(
                analysis_type=AnalysisType.ENTITY_TABLE,
                chart_type=ChartType.TABLE,
                metrics=["cost"]
            ),
            filter_plan=FilterPlan(
                filter_type=FilterType.NONE,
                target_level=EntityLevel.CAMPAIGN.value,
                steps=[]
            ),
        )
        mock_cot.plan.return_value = _make_cot_success(plan_result=plan_none)

        # FilterExecutor: 返回全部 25 个计划
        mock_filter = MagicMock()
        mock_filter_class.return_value = mock_filter
        all_entity_ids = list(range(1001, 1026))  # 25 个计划
        mock_filter.execute.return_value = _make_filter_result(
            entity_ids=all_entity_ids, entity_level="campaign", total_count=25
        )

        # EmptyResultChecker
        mock_empty = MagicMock()
        mock_empty_class.return_value = mock_empty
        mock_empty.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # AnalysisExecutor
        mock_analysis = MagicMock()
        mock_analysis_class.return_value = mock_analysis
        mock_analysis.execute.return_value = _make_analysis_result()

        # QualityChecker
        mock_quality = MagicMock()
        mock_quality_class.return_value = mock_quality
        mock_quality.check.return_value = QualityResult(passed=True, issues=[], warnings=[])

        # ReportFormatter
        mock_formatter = MagicMock()
        mock_formatter_class.return_value = mock_formatter
        mock_report = {
            "report_type": "success",
            "title": "全部计划消耗 (25 个)",
            "highlights": [{"type": "info", "text": "✅ 共 25 个计划的数据"}]
        }
        mock_formatter.format.return_value = mock_report

        result = await analysis_node(state)

        assert "final_report" in result
        assert result["final_report"] == mock_report

        # 验证 FilterExecutor 被正确调用，filter_type 传递正确
        filter_call = mock_filter.execute.call_args
        passed_filter_plan = filter_call.kwargs.get("filter_plan")
        assert passed_filter_plan.filter_type == "none"

        # 验证 AnalysisExecutor 收到了全部 25 个 entity_ids
        analysis_call = mock_analysis.execute.call_args
        passed_entity_ids = analysis_call.kwargs.get("entity_ids")
        assert len(passed_entity_ids) == 25


@pytest.mark.asyncio
async def test_analysis_node_es_connection_failure_during_filter():
    """测试 ES 连接失败发生在 FilterExecutor 执行阶段

    模拟 Elasticsearch 连接失败异常，验证全局异常处理器
    能正确捕获并返回格式友好的错误报告。
    """
    state = {
        "user_input": "查看广告主 123 最近 7 天的消耗",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-es-filter-failure"
    }

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_formatter_class:

        # IntentAnalyzer
        mock_intent = MagicMock()
        mock_intent_factory.return_value = mock_intent
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context()
        mock_intent.analyze.return_value = mock_intent_result

        # CotPlanner
        mock_cot = MagicMock()
        mock_cot_factory.return_value = mock_cot
        mock_cot.plan.return_value = _make_cot_success()

        # FilterExecutor: 模拟 ES 连接失败
        mock_filter = MagicMock()
        mock_filter_class.return_value = mock_filter
        mock_filter.execute.side_effect = ConnectionError(
            "Elasticsearch connection refused: Connection error"
        )

        # ReportFormatter
        mock_formatter = MagicMock()
        mock_formatter_class.return_value = mock_formatter
        mock_error_report = {
            "report_type": "error",
            "title": "分析遇到问题",
            "highlights": [
                {"type": "negative", "text": "⚠️ 分析过程中发生错误: Elasticsearch connection refused"}
            ]
        }
        mock_formatter.format_error.return_value = mock_error_report

        result = await analysis_node(state)

        # 验证返回错误报告
        assert "final_report" in result
        assert result["final_report"] == mock_error_report
        assert result["final_report"]["report_type"] == "error"

        # 验证 error 字段
        assert "error" in result
        assert result["error"]["type"] == "analysis_error"
        assert "Elasticsearch" in result["error"]["message"]

        # 验证 execution_trace 中有错误步骤
        trace = result["execution_trace"]
        error_steps = [s for s in trace if s["step"] == "error"]
        assert len(error_steps) >= 1
        assert error_steps[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_analysis_node_es_connection_failure_during_analysis():
    """测试 ES 连接失败发生在 AnalysisExecutor 执行阶段

    模拟分析执行阶段 ES 连接失败，验证异常被正确捕获，
    返回错误报告而非崩溃。
    """
    state = {
        "user_input": "查看广告主 123 最近 7 天的消耗趋势",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-es-analysis-failure"
    }

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_formatter_class:

        # IntentAnalyzer
        mock_intent = MagicMock()
        mock_intent_factory.return_value = mock_intent
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context()
        mock_intent.analyze.return_value = mock_intent_result

        # CotPlanner
        mock_cot = MagicMock()
        mock_cot_factory.return_value = mock_cot
        mock_cot.plan.return_value = _make_cot_success()

        # FilterExecutor: 正常执行
        mock_filter = MagicMock()
        mock_filter_class.return_value = mock_filter
        mock_filter.execute.return_value = _make_filter_result()

        # EmptyResultChecker: 通过
        mock_empty = MagicMock()
        mock_empty_class.return_value = mock_empty
        mock_empty.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # AnalysisExecutor: 模拟 ES 连接失败
        mock_analysis = MagicMock()
        mock_analysis_class.return_value = mock_analysis
        mock_analysis.execute.side_effect = TimeoutError(
            "Elasticsearch query timeout: request timed out after 30s"
        )

        # ReportFormatter
        mock_formatter = MagicMock()
        mock_formatter_class.return_value = mock_formatter
        mock_error_report = {
            "report_type": "error",
            "title": "分析遇到问题",
            "highlights": [
                {"type": "negative", "text": "⚠️ 分析过程中发生错误: Elasticsearch query timeout"}
            ]
        }
        mock_formatter.format_error.return_value = mock_error_report

        result = await analysis_node(state)

        # 验证返回错误报告
        assert "final_report" in result
        assert result["final_report"]["report_type"] == "error"

        # 验证 error 字段
        assert "error" in result
        assert result["error"]["type"] == "analysis_error"
        assert "timeout" in result["error"]["message"].lower()

        # 验证 execution_trace
        trace = result["execution_trace"]
        # 应该有 filter_executor 成功的步骤（因为 filter 阶段已经完成）
        filter_steps = [s for s in trace if s["step"] == "filter_executor"]
        assert len(filter_steps) >= 1
        assert filter_steps[-1]["status"] == "success"

        # 应该有 error 步骤
        error_steps = [s for s in trace if s["step"] == "error"]
        assert len(error_steps) >= 1


@pytest.mark.asyncio
async def test_analysis_node_intent_analyzer_failure_graceful_continue():
    """测试 IntentAnalyzer 失败时，CotPlanner 仍能继续执行

    analysis_node 中 IntentAnalyzer 失败不会中断流程，
    CotPlanner 可以处理没有 field_context 的情况。
    验证此降级路径正常工作。
    """
    state = {
        "user_input": "查看消耗数据",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-intent-fail-graceful"
    }

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_class, \
         patch('src.nl_dsl.quality_checker.QualityChecker') as mock_quality_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_formatter_class:

        # IntentAnalyzer: 抛出异常
        mock_intent = MagicMock()
        mock_intent_factory.return_value = mock_intent
        mock_intent.analyze.side_effect = Exception("NLP 模型调用失败")

        # CotPlanner: 即使没有 field_context 也能生成计划
        mock_cot = MagicMock()
        mock_cot_factory.return_value = mock_cot
        mock_cot.plan.return_value = _make_cot_success()

        # FilterExecutor
        mock_filter = MagicMock()
        mock_filter_class.return_value = mock_filter
        mock_filter.execute.return_value = _make_filter_result()

        # EmptyResultChecker
        mock_empty = MagicMock()
        mock_empty_class.return_value = mock_empty
        mock_empty.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # AnalysisExecutor
        mock_analysis = MagicMock()
        mock_analysis_class.return_value = mock_analysis
        mock_analysis.execute.return_value = _make_analysis_result()

        # QualityChecker
        mock_quality = MagicMock()
        mock_quality_class.return_value = mock_quality
        mock_quality.check.return_value = QualityResult(passed=True, issues=[], warnings=[])

        # ReportFormatter
        mock_formatter = MagicMock()
        mock_formatter_class.return_value = mock_formatter
        mock_report = {"report_type": "success", "title": "分析结果", "highlights": []}
        mock_formatter.format.return_value = mock_report

        result = await analysis_node(state)

        # 验证最终成功（降级路径）
        assert "final_report" in result
        assert result["final_report"] == mock_report
        assert "execution_trace" in result

        # 验证 intent_analyzer 步骤标记为 failed
        trace = result["execution_trace"]
        intent_steps = [s for s in trace if s["step"] == "intent_analyzer"]
        assert len(intent_steps) >= 1
        assert intent_steps[-1]["status"] == "failed"

        # 验证 cot_planner 仍然被调用
        mock_cot.plan.assert_called_once()


@pytest.mark.asyncio
async def test_analysis_node_cot_planner_parse_failure():
    """测试 CotPlanner 返回非 SUCCESS 且非 NEEDS_CLARIFICATION 的状态

    例如 PARSE_FAILED 状态，验证生成错误报告而非崩溃。
    """
    state = {
        "user_input": "查看广告主 123 的数据",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-cot-parse-fail"
    }

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_factory, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_formatter_class:

        # IntentAnalyzer
        mock_intent = MagicMock()
        mock_intent_factory.return_value = mock_intent
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context()
        mock_intent.analyze.return_value = mock_intent_result

        # CotPlanner: 返回解析失败
        mock_cot = MagicMock()
        mock_cot_factory.return_value = mock_cot
        mock_cot_result = MagicMock()
        mock_cot_result.status = CotResultStatus.PARSE_FAILED
        mock_cot_result.reasoning = CotReasoning(steps=[], summary="解析失败")
        mock_cot.plan.return_value = mock_cot_result

        # ReportFormatter
        mock_formatter = MagicMock()
        mock_formatter_class.return_value = mock_formatter
        mock_error_report = {
            "report_type": "error",
            "title": "无法生成分析计划",
            "highlights": [{"type": "negative", "text": "⚠️ 无法生成分析计划，请尝试重新表述您的问题"}]
        }
        mock_formatter.format_error.return_value = mock_error_report

        result = await analysis_node(state)

        # 验证返回错误报告
        assert "final_report" in result
        assert result["final_report"] == mock_error_report

        # 验证 error 字段
        assert "error" in result
        assert result["error"]["type"] == "cot_planning_error"

        # 验证 execution_trace 中 cot_planner 标记为 failed
        trace = result["execution_trace"]
        cot_steps = [s for s in trace if s["step"] == "cot_planner"]
        assert len(cot_steps) >= 1
        assert cot_steps[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_analysis_node_filter_type_where_with_steps():
    """测试 filter_type=where（带条件筛选）的场景

    验证带有筛选步骤的场景能正确执行，筛选条件被传递给 FilterExecutor。
    """
    from src.nl_dsl.models import FilterStep, FilterCondition

    state = {
        "user_input": "查看广告主 123 中消耗大于 1000 的计划",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-filter-where"
    }

    with patch('src.analysis.intent_analyzer.create_intent_analyzer') as mock_intent_factory, \
         patch('src.analysis.cot_planner.get_cot_planner') as mock_cot_factory, \
         patch('src.nl_dsl.filter_executor.FilterExecutor') as mock_filter_class, \
         patch('src.nl_dsl.empty_checker.EmptyResultChecker') as mock_empty_class, \
         patch('src.nl_dsl.analysis_executor.AnalysisExecutor') as mock_analysis_class, \
         patch('src.nl_dsl.quality_checker.QualityChecker') as mock_quality_class, \
         patch('src.analysis.report_formatter.ReportFormatter') as mock_formatter_class:

        # IntentAnalyzer
        mock_intent = MagicMock()
        mock_intent_factory.return_value = mock_intent
        mock_intent_result = MagicMock()
        mock_intent_result.field_context = _make_field_context(
            metrics=["cost"], target_level=EntityLevel.CAMPAIGN
        )
        mock_intent.analyze.return_value = mock_intent_result

        # CotPlanner: filter_type=where 带筛选步骤
        mock_cot = MagicMock()
        mock_cot_factory.return_value = mock_cot
        where_plan = _make_plan_result(
            analysis_plan=_make_analysis_plan(
                analysis_type=AnalysisType.ENTITY_TABLE,
                chart_type=ChartType.TABLE,
                metrics=["cost"]
            ),
            filter_plan=FilterPlan(
                filter_type=FilterType.WHERE,
                target_level=EntityLevel.CAMPAIGN.value,
                steps=[
                    FilterStep(
                        step_id="step_1",
                        step_type="where_filter",
                        level="campaign",
                        index="ad_stat_data",
                        conditions=[
                            FilterCondition(
                                field="data_value",
                                operator=">",
                                value=1000,
                                metric="cost"
                            )
                        ],
                        output_field="campaign_id"
                    )
                ]
            ),
        )
        mock_cot.plan.return_value = _make_cot_success(plan_result=where_plan)

        # FilterExecutor: 返回筛选后的 10 个实体
        mock_filter = MagicMock()
        mock_filter_class.return_value = mock_filter
        filtered_ids = list(range(1, 11))
        mock_filter.execute.return_value = _make_filter_result(
            entity_ids=filtered_ids, entity_level="campaign", total_count=10
        )

        # EmptyResultChecker
        mock_empty = MagicMock()
        mock_empty_class.return_value = mock_empty
        mock_empty.async_check = AsyncMock(return_value=EmptyCheckResult(found_error=False))

        # AnalysisExecutor
        mock_analysis = MagicMock()
        mock_analysis_class.return_value = mock_analysis
        mock_analysis.execute.return_value = _make_analysis_result()

        # QualityChecker
        mock_quality = MagicMock()
        mock_quality_class.return_value = mock_quality
        mock_quality.check.return_value = QualityResult(passed=True, issues=[], warnings=[])

        # ReportFormatter
        mock_formatter = MagicMock()
        mock_formatter_class.return_value = mock_formatter
        mock_report = {"report_type": "success", "title": "筛选结果", "highlights": []}
        mock_formatter.format.return_value = mock_report

        result = await analysis_node(state)

        assert "final_report" in result
        assert result["final_report"] == mock_report

        # 验证 FilterExecutor 收到了正确的筛选计划
        filter_call = mock_filter.execute.call_args
        passed_filter_plan = filter_call.kwargs.get("filter_plan")
        assert passed_filter_plan.filter_type == "where"
        assert len(passed_filter_plan.steps) == 1
        assert passed_filter_plan.steps[0].step_type == "where_filter"
        assert passed_filter_plan.steps[0].conditions[0].field == "data_value"
        assert passed_filter_plan.steps[0].conditions[0].value == 1000

        # 验证 AnalysisExecutor 收到了筛选后的实体
        analysis_call = mock_analysis.execute.call_args
        assert len(analysis_call.kwargs.get("entity_ids")) == 10


# ============================================================================
# 测试统计
# ============================================================================
# 本文件包含以下测试：
# 1. test_analysis_node_import —— 基础导入测试
# 2. test_analysis_node_success_path —— 完整成功路径
# 3. test_analysis_node_hitl_from_cot_planner —— CoT HITL 澄清
# 4. test_analysis_node_error_handling —— 筛选阶段异常
# 5. test_analysis_node_empty_result —— 空结果检查
# 6. test_analysis_node_cot_clarification_reentry —— CoT 澄清后重入
# 7. test_analysis_node_quality_hitl_continue —— 质量 HITL continue
# 8. test_analysis_node_quality_hitl_rephrase —— 质量 HITL rephrase
# 9. test_analysis_node_zero_entities_filter_result —— 零实体边界
# 10. test_analysis_node_single_entity_boundary —— 单实体边界
# 11. test_analysis_node_quality_multiple_issues_mixed_severity —— 混合质量问题
# 12. test_analysis_node_quality_hitl_skip_trace —— quality skip 的 trace 验证
# 13. test_analysis_node_with_derived_metrics —— 衍生指标
# 14. test_analysis_node_filter_type_none_all_entities —— filter_type=none
# 15. test_analysis_node_es_connection_failure_during_filter —— ES 失败(筛选)
# 16. test_analysis_node_es_connection_failure_during_analysis —— ES 失败(分析)
# 17. test_analysis_node_intent_analyzer_failure_graceful_continue —— Intent 降级
# 18. test_analysis_node_cot_planner_parse_failure —— CoT 解析失败
# 19. test_analysis_node_filter_type_where_with_steps —— where 筛选
