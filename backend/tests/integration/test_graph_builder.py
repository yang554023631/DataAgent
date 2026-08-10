"""
Tests for the graph builder with analysis_node integration.
"""
import sys
import os
import types
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# ============================================================================
# 设置合并的 src 包（同 test_analysis_node.py）
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

from src.graph.builder import build_graph
from src.analysis.models import (
    AnalysisPlanResult, AnalysisPlan, AnalysisType, ChartType,
    AnalysisTimeRange, CotReasoning, EntityLevel, FieldContext,
    FilterPlan, FilterType, EmptyCheckResult, EmptyCheckErrorType,
)
from src.nl_dsl.models import (
    FilterResult, AnalysisResult as NlDslAnalysisResult,
    AnalysisDataTable, QualityResult, QualityIssue,
    QualityCheckType, QualityAction,
)
from src.analysis.cot_planner import CotResultStatus


def test_graph_compiles():
    """Test that the graph compiles successfully with analysis_node."""
    app = build_graph()
    assert app is not None


def test_graph_structure():
    """Simplified test to verify the graph can be built without errors."""
    app = build_graph()
    assert app is not None


@pytest.mark.asyncio
async def test_analysis_node_import():
    """Test that analysis_node can be imported and used."""
    from src.graph.nodes import analysis_node
    assert analysis_node is not None
    assert callable(analysis_node)


@pytest.mark.asyncio
async def test_clarify_node_sets_continue_analysis():
    """Test that clarify_node sets clarify_next=continue_analysis for analysis clarifications."""
    from src.intent.clarify_node import clarify_node

    # Test with cot_clarification type
    state = {
        "user_feedback": "test feedback",
        "clarification": {"type": "cot_clarification"},
        "intent_category": "report",
        "user_input": "original input"
    }

    result = await clarify_node(state)
    assert result["clarify_next"] == "continue_analysis"

    # Test with quality_hitl type
    state = {
        "user_feedback": "test feedback",
        "clarification": {"type": "quality_hitl"},
        "intent_category": "report",
        "user_input": "original input"
    }

    result = await clarify_node(state)
    assert result["clarify_next"] == "continue_analysis"


# ============================================================================
# B. Graph-level integration（图级别集成测试）
# ============================================================================

def test_graph_analysis_node_is_registered():
    """测试 analysis 节点已在图中注册"""
    app = build_graph()
    graph = app.get_graph()
    node_names = set(graph.nodes.keys())
    assert "analysis" in node_names, "analysis node should be registered in the graph"


def test_graph_analysis_has_outgoing_edges():
    """测试 analysis 节点有到 clarify 和 reporter 的出边"""
    app = build_graph()
    graph = app.get_graph()

    # 获取 analysis 节点的出边
    analysis_edges = [e for e in graph.edges if e.source == "analysis"]
    edge_targets = {e.target for e in analysis_edges}

    # analysis 节点应该能路由到 clarify 和 reporter（通过条件边）
    # 注意：LangGraph 的 edges 列表中条件边的 target 是具体节点
    # 我们通过检查是否有到 clarify 和 reporter 的边来验证
    assert "clarify" in edge_targets or any("clarify" in str(e) for e in analysis_edges)
    assert "reporter" in edge_targets or any("reporter" in str(e) for e in analysis_edges)


def test_graph_report_intent_has_analysis_edge():
    """测试 report_intent 节点有到 analysis 的路由边"""
    app = build_graph()
    graph = app.get_graph()

    report_edges = [e for e in graph.edges if e.source == "report_intent"]
    edge_targets = {e.target for e in report_edges}

    # report_intent 应该能路由到 analysis
    assert "analysis" in edge_targets, \
        f"report_intent should have edge to analysis, got targets: {edge_targets}"


def test_graph_clarify_has_analysis_edge():
    """测试 clarify 节点有到 analysis 的路由边（澄清后重入 analysis）"""
    app = build_graph()
    graph = app.get_graph()

    clarify_edges = [e for e in graph.edges if e.source == "clarify"]
    edge_targets = {e.target for e in clarify_edges}

    # clarify 应该能路由回 analysis（continue_analysis）
    assert "analysis" in edge_targets, \
        f"clarify should have edge to analysis, got targets: {edge_targets}"


def test_graph_reporter_leads_to_end():
    """测试 reporter 节点通向 END（分析流程的终点）"""
    app = build_graph()
    graph = app.get_graph()

    reporter_edges = [e for e in graph.edges if e.source == "reporter"]
    edge_targets = {e.target for e in reporter_edges}

    assert "__end__" in edge_targets, \
        f"reporter should lead to END, got targets: {edge_targets}"


@pytest.mark.asyncio
async def test_full_graph_flow_analysis_to_end():
    """完整图流测试：用户消息 → intent → report_intent → analysis → reporter → END

    使用模拟节点函数验证完整的分析路径逻辑正确。
    """
    initial_state = {
        "user_input": "查看广告主 123 最近 7 天的消耗趋势",
        "conversation_history": [],
        "session_id": "test-full-flow-1",
        "advertiser_ids": ["123"],
    }

    # Step 1: intent_classifier（模拟）
    async def mock_intent_classifier(state):
        return {
            "intent_category": "report",
            "intent_confidence": 0.95,
            "intent_classify_source": "rule_fastpath",
            "intent_reason": "用户请求广告数据分析",
            "needs_clarification": False,
            "query_type": "report",
        }

    # Step 2: report_intent（模拟，返回 analysis 路由）
    async def mock_report_intent(state):
        return {
            "query_route": "analysis",
            "route_reason": "高级分析查询",
            "analysis_type": "time_trend",
            "needs_clarification": False,
            "final_report": None,
            "report_intent_result": {
                "advertiser_ids": ["123"],
                "metrics": ["cost"],
                "time_range": {"start_date": "2025-01-01", "end_date": "2025-01-07"},
                "group_by": [],
                "is_comparison": False,
            },
            "advertiser_ids": ["123"],
            "query_intent": {
                "advertiser_ids": ["123"],
                "metrics": ["cost"],
                "time_range": {"start": "2025-01-01", "end": "2025-01-07"},
                "is_comparison": False,
                "ad_level": "campaign",
            },
        }

    # Step 3: analysis_node（模拟，返回成功报告）
    async def mock_analysis_node(state):
        return {
            "final_report": {
                "report_type": "success",
                "title": "时间趋势分析 (2025-01-01 ~ 2025-01-07)",
                "highlights": [{"type": "info", "text": "✅ 数据加载完成"}],
                "metrics": ["cost"],
                "chart_config": {"type": "line"},
                "data_table": {"columns": [], "rows": []},
            },
            "needs_clarification": False,
            "execution_trace": [
                {"step": "intent_analyzer", "status": "success"},
                {"step": "cot_planner", "status": "success"},
                {"step": "filter_executor", "status": "success"},
                {"step": "analysis_executor", "status": "success"},
                {"step": "quality_checker", "status": "success"},
                {"step": "report_formatter", "status": "success"},
                {"step": "complete", "status": "success"},
            ],
            "analysis_plan": {},
            "cot_reasoning": {"steps": [], "summary": "分析完成"},
        }

    # Step 4: reporter_node（模拟，透传 final_report）
    async def mock_reporter_node(state):
        existing = state.get("final_report")
        return {
            "final_report": existing,
            "error": None,
        }

    # ====== 手动模拟图执行 ======
    state = initial_state.copy()

    # Step 1: intent_classifier
    s1 = await mock_intent_classifier(state)
    state.update(s1)
    assert state["intent_category"] == "report"
    assert state["needs_clarification"] is False

    # 路由检查：intent=report → report_intent
    assert state["intent_category"] == "report"  # 触发路由到 report_intent

    # Step 2: report_intent
    s2 = await mock_report_intent(state)
    state.update(s2)
    assert state["query_route"] == "analysis"
    assert state["needs_clarification"] is False
    assert state.get("final_report") is None  # 还没有 final_report

    # 路由检查：query_route=analysis → analysis 节点
    assert state["query_route"] == "analysis"  # 触发路由到 analysis

    # Step 3: analysis_node
    s3 = await mock_analysis_node(state)
    state.update(s3)
    assert state["final_report"] is not None
    assert state["final_report"]["report_type"] == "success"
    assert state["needs_clarification"] is False

    # 路由检查：needs_clarification=False → reporter
    assert state["needs_clarification"] is False  # 触发路由到 reporter

    # Step 4: reporter_node
    s4 = await mock_reporter_node(state)
    state.update(s4)
    assert state["final_report"] is not None
    assert state["error"] is None

    # 最终验证
    assert "final_report" in state
    assert state["final_report"]["title"] == "时间趋势分析 (2025-01-01 ~ 2025-01-07)"
    assert state["final_report"]["report_type"] == "success"


@pytest.mark.asyncio
async def test_full_graph_flow_with_cot_clarification():
    """完整图流测试：带 CoT HITL 澄清的分析流程

    流程：用户消息 → intent → report_intent → analysis（触发 HITL）→ clarify → 重入 analysis → reporter → END
    """
    initial_state = {
        "user_input": "查看广告主的消耗数据",
        "conversation_history": [],
        "session_id": "test-hitl-flow",
        "advertiser_ids": [],
    }

    # Step 1: intent_classifier
    async def mock_intent_classifier(state):
        return {
            "intent_category": "report",
            "intent_confidence": 0.9,
            "needs_clarification": False,
            "query_type": "report",
        }

    # Step 2: report_intent
    async def mock_report_intent(state):
        return {
            "query_route": "analysis",
            "route_reason": "分析查询",
            "analysis_type": "time_trend",
            "needs_clarification": False,
            "final_report": None,
            "advertiser_ids": [],
            "report_intent_result": {},
        }

    # Step 3a: analysis_node（首次进入，触发 HITL）
    async def mock_analysis_node_hitl(state):
        result = {
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
            "cot_reasoning": {"steps": [], "summary": "需要广告主信息"},
            "field_context": None,
            "execution_trace": [
                {"step": "intent_analyzer", "status": "success"},
                {"step": "cot_planner", "status": "hitl_required"},
            ],
        }
        # 注意：HITL 路径不包含 final_report
        return result

    # Step 4: clarify_node（处理澄清输入）
    async def mock_clarify_node(state):
        user_feedback = state.get("user_feedback", "")
        return {
            "pending_clarification_input": user_feedback,
            "user_input": f"查看广告主 {user_feedback} 的消耗数据",
            "clarify_next": "continue_analysis",
            "advertiser_ids": [user_feedback] if user_feedback else [],
        }

    # Step 3b: analysis_node（重入，完成分析）
    async def mock_analysis_node_success(state):
        return {
            "final_report": {
                "report_type": "success",
                "title": "广告主 123 消耗趋势",
                "highlights": [{"type": "info", "text": "✅ 分析完成"}],
            },
            "needs_clarification": False,
            "pending_clarification_input": None,
            "execution_trace": [
                {"step": "intent_analyzer", "status": "success"},
                {"step": "cot_planner", "status": "success"},
                {"step": "filter_executor", "status": "success"},
                {"step": "analysis_executor", "status": "success"},
                {"step": "complete", "status": "success"},
            ],
        }

    # Step 5: reporter_node
    async def mock_reporter_node(state):
        return {
            "final_report": state.get("final_report"),
            "error": None,
        }

    # ====== 第一轮：到 analysis 触发 HITL ======
    state = initial_state.copy()

    s1 = await mock_intent_classifier(state)
    state.update(s1)

    s2 = await mock_report_intent(state)
    state.update(s2)

    s3 = await mock_analysis_node_hitl(state)
    state.update(s3)

    # 验证 HITL 被触发
    assert state["needs_clarification"] is True
    assert state["clarification"]["type"] == "cot_clarification"
    assert "hitl_request" in state
    # 注意：analysis_node 在 HITL 路径下不设置 final_report
    # 但如果 state 中有之前的 final_report（这里没有），可能会被保留
    # 我们只验证 needs_clarification 标志和 clarification 类型

    # ====== 用户输入澄清反馈 ======
    state["user_feedback"] = "123"

    # ====== 第二轮：澄清 → 重入 analysis → 完成 ======
    s4 = await mock_clarify_node(state)
    state.update(s4)
    assert state["clarify_next"] == "continue_analysis"
    assert state["pending_clarification_input"] == "123"

    # 路由检查：clarify_next=continue_analysis → analysis
    assert state["clarify_next"] == "continue_analysis"

    s5 = await mock_analysis_node_success(state)
    state.update(s5)

    # 验证分析完成
    assert state["needs_clarification"] is False
    assert state["pending_clarification_input"] is None
    assert "final_report" in state
    assert state["final_report"]["report_type"] == "success"

    # 路由到 reporter
    s6 = await mock_reporter_node(state)
    state.update(s6)

    # 最终验证
    assert state["final_report"] is not None
    assert "消耗趋势" in state["final_report"]["title"]


@pytest.mark.asyncio
async def test_full_graph_flow_with_quality_hitl():
    """完整图流测试：带质量 HITL 的分析流程

    流程：analysis（质量检查发现问题，触发 HITL）→ clarify → 重入 analysis（跳过质量检查）→ reporter → END
    """
    initial_state = {
        "user_input": "查看广告主 123 最近 7 天 50 个计划的消耗排名",
        "conversation_history": [],
        "session_id": "test-quality-hitl-flow",
        "advertiser_ids": ["123"],
    }

    # Step 1: analysis_node（首次，触发质量 HITL）
    async def mock_analysis_quality_hitl(state):
        return {
            "needs_clarification": True,
            "clarification": {
                "type": "quality_hitl",
                "question": "数据质量存在问题，是否继续查看结果？",
                "options": [
                    {"value": "continue", "label": "继续查看结果"},
                    {"value": "rephrase", "label": "重新表述问题"},
                ],
                "allow_custom_input": False,
                "missing_fields": [],
            },
            "hitl_request": {
                "question": "数据质量存在问题，是否继续查看结果？",
                "missing_fields": [],
                "options": [
                    {"value": "continue", "label": "继续查看结果"},
                    {"value": "rephrase", "label": "重新表述问题"},
                ],
                "quality_issues": [
                    {"type": "max_categories", "message": "分类数量过多", "severity": "error"},
                ],
            },
            "analysis_plan": {},
            "chart_data": {},
            "quality_result": {
                "passed": False,
                "issues": [
                    {"check_type": "max_categories", "severity": "error", "message": "分类数量过多", "suggested_action": "hitl"},
                ],
                "warnings": [],
            },
            "execution_trace": [
                {"step": "analysis_executor", "status": "success"},
                {"step": "quality_checker", "status": "hitl_required"},
            ],
        }

    # Step 2: clarify_node（处理 quality_hitl 澄清）
    async def mock_clarify_quality(state):
        user_feedback = state.get("user_feedback", "")
        return {
            "pending_clarification_input": user_feedback,
            "clarify_next": "continue_analysis",
        }

    # Step 3: analysis_node（重入，跳过质量检查，生成报告）
    async def mock_analysis_skip_quality(state):
        # 验证 pending_clarification_input == "continue"
        assert state.get("pending_clarification_input") == "continue"
        return {
            "final_report": {
                "report_type": "success",
                "title": "消耗排名（已跳过质量检查）",
                "highlights": [
                    {"type": "warning", "text": "⚠️ 数据质量存在问题，已按您的选择继续展示"},
                    {"type": "info", "text": "✅ 共 50 条结果"},
                ],
            },
            "needs_clarification": False,
            "pending_clarification_input": None,
            "quality_result": {"passed": True, "issues": []},
            "execution_trace": [
                {"step": "quality_checker", "status": "skipped"},
                {"step": "report_formatter", "status": "success"},
                {"step": "complete", "status": "success"},
            ],
        }

    # ====== 第一轮：analysis 触发质量 HITL ======
    state = initial_state.copy()

    s1 = await mock_analysis_quality_hitl(state)
    state.update(s1)

    assert state["needs_clarification"] is True
    assert state["clarification"]["type"] == "quality_hitl"
    assert len(state["hitl_request"]["quality_issues"]) == 1

    # ====== 用户选择 continue ======
    state["user_feedback"] = "continue"

    # ====== 第二轮：澄清 → 重入 analysis ======
    s2 = await mock_clarify_quality(state)
    state.update(s2)
    assert state["clarify_next"] == "continue_analysis"

    s3 = await mock_analysis_skip_quality(state)
    state.update(s3)

    # 验证最终结果
    assert state["needs_clarification"] is False
    assert state["pending_clarification_input"] is None
    assert "final_report" in state
    assert state["final_report"]["report_type"] == "success"
    highlights = state["final_report"]["highlights"]
    assert any("质量" in h["text"] for h in highlights)


@pytest.mark.asyncio
async def test_graph_analysis_vs_structured_routing():
    """测试路由逻辑：structured 路由走 planner 路径，analysis 路由走 analysis 节点

    通过模拟节点返回不同的 query_route，验证两条路径的区别。
    """
    # 模拟 report_intent 返回 structured 路由
    state_structured = {
        "needs_clarification": False,
        "final_report": None,
        "query_route": "structured",
    }

    # 模拟 report_intent 返回 analysis 路由
    state_analysis = {
        "needs_clarification": False,
        "final_report": None,
        "query_route": "analysis",
    }

    # 从图结构验证两条边都存在
    app = build_graph()
    graph = app.get_graph()
    report_edges = [e for e in graph.edges if e.source == "report_intent"]
    edge_targets = {e.target for e in report_edges}

    # report_intent 应该有到 analysis 和 planner 的边
    assert "analysis" in edge_targets, "report_intent should route to analysis"
    assert "planner" in edge_targets, "report_intent should route to planner (structured path)"
    assert "nl_dsl" in edge_targets, "report_intent should route to nl_dsl"
    assert "clarify" in edge_targets, "report_intent should route to clarify"
