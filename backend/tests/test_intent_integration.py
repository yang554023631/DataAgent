"""
意图识别集成测试

测试场景：
1. 规则快筛命中报表查询 → 信息完整 → 直接进入 planner
2. 报表查询缺广告主 → 澄清 → 用户补充 → 继续流程
3. 领域外输入 → 拒绝回答
4. 低置信度输入 → 意图确认澄清 → 用户明确后继续
5. 知识类问题 → 路由到 RAG 模块
6. 意图回退场景（用户澄清时改变意图）
7. 超过最大回退次数 → 重置会话
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.graph.builder import app as graph_app
from src.graph.state import AdReportState
from src.intent.top_classifier import IntentTopClassifier
from src.intent.report_intent import ReportIntentAnalyzer
from src.intent.llm_client import IntentLLMClient


@pytest.fixture
def mock_top_classifier_llm():
    """Mock 顶层分类器的 LLM 客户端"""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def mock_report_intent_llm():
    """Mock 报表意图识别的 LLM 客户端"""
    mock_client = MagicMock()
    return mock_client


class TestIntentIntegration:
    """意图识别集成测试"""

    def _make_mock_top_classifier(self, category: str = "report", confidence: float = 0.9, source: str = "llm"):
        """创建 Mock 顶层分类器"""
        mock_classifier = MagicMock(spec=IntentTopClassifier)
        mock_result = MagicMock()
        mock_result.category = category
        mock_result.confidence = confidence
        mock_result.source = source
        mock_result.reason = "test reason"
        mock_classifier.classify = AsyncMock(return_value=mock_result)
        mock_classifier.confidence_threshold = 0.7
        return mock_classifier

    def _make_mock_report_analyzer(self, has_all_fields: bool = True, clarification: MagicMock = None):
        """创建 Mock 报表意图分析器"""
        from src.intent.models import ReportIntentResult, ReportTimeRange

        mock_analyzer = MagicMock(spec=ReportIntentAnalyzer)

        # 使用真实对象而不是 MagicMock，确保可序列化
        if has_all_fields:
            result = ReportIntentResult(
                advertiser_ids=["123"],
                time_range=ReportTimeRange(
                    start_date="2024-01-01",
                    end_date="2024-01-31",
                    unit="day",
                    is_lifetime=False
                ),
                metrics=["impressions", "clicks", "cost"],
                ad_level="campaign",
                group_by=[],
                filters=[],
                is_comparison=False,
                compare_time_range=None,
                confidence=0.95,
                alias_mappings={},
            )
        else:
            result = ReportIntentResult(
                advertiser_ids=[],
                time_range=None,
                metrics=["impressions"],
                ad_level="campaign",
                group_by=[],
                filters=[],
                is_comparison=False,
                compare_time_range=None,
                confidence=0.95,
                alias_mappings={},
            )

        mock_analyzer.analyze = AsyncMock(return_value=(result if has_all_fields else None, clarification, None))
        mock_analyzer.check_required_fields = MagicMock(return_value=(has_all_fields, None))
        mock_analyzer.check_capabilities = MagicMock(return_value=(True, None))

        return mock_analyzer

    @pytest.mark.asyncio
    @patch("src.graph.nodes.get_top_classifier")
    @patch("src.graph.nodes.get_report_intent_analyzer")
    async def test_rule_fastpath_report_flow(self, mock_get_analyzer, mock_get_classifier):
        """
        测试场景 1：规则快筛命中报表查询，信息完整 → 直接进入 planner
        """
        # Setup
        mock_classifier = self._make_mock_top_classifier(category="report", confidence=1.0, source="rule_fastpath")
        mock_get_classifier.return_value = mock_classifier

        mock_analyzer = self._make_mock_report_analyzer(has_all_fields=True)
        mock_get_analyzer.return_value = mock_analyzer

        # Initial state
        initial_state: AdReportState = {
            "session_id": "test_session_1",
            "user_id": "test_user",
            "user_input": "昨天的曝光点击消耗",
            "conversation_history": [],
            "intent_category": None,
            "intent_confidence": 0.0,
            "intent_classify_source": "",
            "intent_reason": "",
            "reentry_count": 0,
            "needs_clarification": False,
            "clarification": None,
            "clarify_next": None,
            "pending_clarification_input": None,
            "reject_reason": None,
            "report_intent_result": None,
            "query_type": "report",
            "rag_context": [],
            "rag_answer": None,
            "query_intent": None,
            "ambiguity": None,
            "user_feedback": None,
            "clarification_count": 0,
            "query_request": None,
            "query_requests": [],
            "query_warnings": [],
            "query_result": None,
            "query_results": [],
            "execution_time_ms": None,
            "analysis_result": None,
            "drill_down_level": 0,
            "needs_drill_down": False,
            "insights": None,
            "final_report": None,
            "advertiser_ids": [],
            "show_advertiser_list": False,
            "error": None
        }

        # Run the graph step by step
        # First, run intent_classifier
        result = await graph_app.ainvoke(initial_state, config={"configurable": {"thread_id": initial_state["session_id"]}})

        # Verify intent classification
        assert result["intent_category"] == "report"
        assert result["intent_confidence"] == 1.0
        assert result["intent_classify_source"] == "rule_fastpath"
        assert result["needs_clarification"] is False

        # Now we should be at report_intent node
        # Let's check that the mock analyzer was called
        assert mock_analyzer.analyze.await_count == 1

        # After report_intent, should have report_intent_result and go to planner
        assert "report_intent_result" in result
        assert result["report_intent_result"] is not None
        assert result["needs_clarification"] is False

    @pytest.mark.asyncio
    @patch("src.graph.nodes.get_top_classifier")
    @patch("src.graph.nodes.get_report_intent_analyzer")
    async def test_missing_advertiser_clarification_flow(self, mock_get_analyzer, mock_get_classifier):
        """
        测试场景 2：报表查询缺广告主 → 触发澄清
        """
        # Setup
        mock_classifier = self._make_mock_top_classifier(category="report", confidence=0.9, source="llm")
        mock_get_classifier.return_value = mock_classifier

        # Create clarification info
        mock_clarification = MagicMock()
        mock_clarification.type = "missing_advertiser"
        mock_clarification.question = "请问你想查看哪个广告主的数据？"
        mock_clarification.options = []
        mock_clarification.allow_custom_input = True
        mock_clarification.missing_fields = ["advertiser_ids"]

        # Mock analyzer to return with clarification
        from src.intent.models import ReportIntentResult, ReportTimeRange
        mock_analyzer = self._make_mock_report_analyzer(has_all_fields=False, clarification=mock_clarification)
        # Override analyze to return (partial result, clarification)
        mock_result = ReportIntentResult(
            advertiser_ids=[],
            time_range=ReportTimeRange(
                start_date="2024-01-01",
                end_date="2024-01-31",
                unit="day",
                is_lifetime=False,
            ),
            metrics=["impressions"],
            ad_level="campaign",
            group_by=[],
            filters=[],
            is_comparison=False,
            compare_time_range=None,
            confidence=0.95,
            alias_mappings={},
        )
        mock_analyzer.analyze = AsyncMock(return_value=(mock_result, mock_clarification, None))
        mock_get_analyzer.return_value = mock_analyzer

        # Initial state
        initial_state: AdReportState = {
            "session_id": "test_session_2",
            "user_id": "test_user",
            "user_input": "昨天的曝光数据",
            "conversation_history": [],
            "intent_category": None,
            "intent_confidence": 0.0,
            "intent_classify_source": "",
            "intent_reason": "",
            "reentry_count": 0,
            "needs_clarification": False,
            "clarification": None,
            "clarify_next": None,
            "pending_clarification_input": None,
            "reject_reason": None,
            "report_intent_result": None,
            "query_type": "report",
            "rag_context": [],
            "rag_answer": None,
            "query_intent": None,
            "ambiguity": None,
            "user_feedback": None,
            "clarification_count": 0,
            "query_request": None,
            "query_requests": [],
            "query_warnings": [],
            "query_result": None,
            "query_results": [],
            "execution_time_ms": None,
            "analysis_result": None,
            "drill_down_level": 0,
            "needs_drill_down": False,
            "insights": None,
            "final_report": None,
            "advertiser_ids": [],
            "show_advertiser_list": False,
            "error": None
        }

        # Run the graph
        result = await graph_app.ainvoke(initial_state, config={"configurable": {"thread_id": initial_state["session_id"]}})

        # Verify we need clarification
        assert result["needs_clarification"] is True
        assert result["clarification"] is not None
        assert result["clarification"]["type"] == "missing_advertiser"

    @pytest.mark.asyncio
    @patch("src.graph.nodes.get_top_classifier")
    async def test_out_of_domain_reject_flow(self, mock_get_classifier):
        """
        测试场景 3：领域外输入 → 拒绝回答
        """
        # Setup
        mock_classifier = self._make_mock_top_classifier(category="out_of_domain", confidence=0.95)
        mock_get_classifier.return_value = mock_classifier

        # Initial state
        initial_state: AdReportState = {
            "session_id": "test_session_3",
            "user_id": "test_user",
            "user_input": "今天天气怎么样",
            "conversation_history": [],
            "intent_category": None,
            "intent_confidence": 0.0,
            "intent_classify_source": "",
            "intent_reason": "",
            "reentry_count": 0,
            "needs_clarification": False,
            "clarification": None,
            "clarify_next": None,
            "pending_clarification_input": None,
            "reject_reason": None,
            "report_intent_result": None,
            "query_type": "report",
            "rag_context": [],
            "rag_answer": None,
            "query_intent": None,
            "ambiguity": None,
            "user_feedback": None,
            "clarification_count": 0,
            "query_request": None,
            "query_requests": [],
            "query_warnings": [],
            "query_result": None,
            "query_results": [],
            "execution_time_ms": None,
            "analysis_result": None,
            "drill_down_level": 0,
            "needs_drill_down": False,
            "insights": None,
            "final_report": None,
            "advertiser_ids": [],
            "show_advertiser_list": False,
            "error": None
        }

        # Run the graph
        result = await graph_app.ainvoke(initial_state, config={"configurable": {"thread_id": initial_state["session_id"]}})

        # Verify rejection
        assert result["intent_category"] == "out_of_domain"
        # Should have final_report from reject_node
        assert "final_report" in result
        assert result["final_report"] is not None

    @pytest.mark.asyncio
    @patch("src.graph.nodes.get_top_classifier")
    async def test_low_confidence_clarification_flow(self, mock_get_classifier):
        """
        测试场景 4：低置信度输入 → 意图确认澄清
        """
        # Setup
        mock_classifier = MagicMock(spec=IntentTopClassifier)
        mock_result = MagicMock()
        mock_result.category = "report"
        mock_result.confidence = 0.5  # Low confidence
        mock_result.source = "llm"
        mock_result.reason = "用户输入太模糊"
        mock_classifier.classify = AsyncMock(return_value=mock_result)
        mock_classifier.confidence_threshold = 0.7  # Threshold higher than confidence
        mock_get_classifier.return_value = mock_classifier

        # Initial state
        initial_state: AdReportState = {
            "session_id": "test_session_4",
            "user_id": "test_user",
            "user_input": "帮我看看数据",
            "conversation_history": [],
            "intent_category": None,
            "intent_confidence": 0.0,
            "intent_classify_source": "",
            "intent_reason": "",
            "reentry_count": 0,
            "needs_clarification": False,
            "clarification": None,
            "clarify_next": None,
            "pending_clarification_input": None,
            "reject_reason": None,
            "report_intent_result": None,
            "query_type": "report",
            "rag_context": [],
            "rag_answer": None,
            "query_intent": None,
            "ambiguity": None,
            "user_feedback": None,
            "clarification_count": 0,
            "query_request": None,
            "query_requests": [],
            "query_warnings": [],
            "query_result": None,
            "query_results": [],
            "execution_time_ms": None,
            "analysis_result": None,
            "drill_down_level": 0,
            "needs_drill_down": False,
            "insights": None,
            "final_report": None,
            "advertiser_ids": [],
            "show_advertiser_list": False,
            "error": None
        }

        # Run the graph
        result = await graph_app.ainvoke(initial_state, config={"configurable": {"thread_id": initial_state["session_id"]}})

        # Verify clarification
        assert result["needs_clarification"] is True
        assert result["clarification"] is not None
        assert result["clarification"]["type"] == "intent_confirm"

    @pytest.mark.asyncio
    @patch("src.graph.nodes.get_top_classifier")
    async def test_knowledge_question_to_rag_flow(self, mock_get_classifier):
        """
        测试场景 5：知识类问题 → 路由到 RAG 模块
        """
        # Setup
        mock_classifier = self._make_mock_top_classifier(category="knowledge", confidence=0.9)
        mock_get_classifier.return_value = mock_classifier

        # Initial state
        initial_state: AdReportState = {
            "session_id": "test_session_5",
            "user_id": "test_user",
            "user_input": "什么是 CTR",
            "conversation_history": [],
            "intent_category": None,
            "intent_confidence": 0.0,
            "intent_classify_source": "",
            "intent_reason": "",
            "reentry_count": 0,
            "needs_clarification": False,
            "clarification": None,
            "clarify_next": None,
            "pending_clarification_input": None,
            "reject_reason": None,
            "report_intent_result": None,
            "query_type": "report",
            "rag_context": [],
            "rag_answer": None,
            "query_intent": None,
            "ambiguity": None,
            "user_feedback": None,
            "clarification_count": 0,
            "query_request": None,
            "query_requests": [],
            "query_warnings": [],
            "query_result": None,
            "query_results": [],
            "execution_time_ms": None,
            "analysis_result": None,
            "drill_down_level": 0,
            "needs_drill_down": False,
            "insights": None,
            "final_report": None,
            "advertiser_ids": [],
            "show_advertiser_list": False,
            "error": None
        }

        # Run the graph step by step (we won't mock rag nodes, just check the routing)
        result = await graph_app.ainvoke(initial_state, config={"configurable": {"thread_id": initial_state["session_id"]}})

        # Verify intent classification
        assert result["intent_category"] == "knowledge"
        assert result["needs_clarification"] is False

    @pytest.mark.asyncio
    @patch("src.intent.clarify_node.detect_intent_change")
    async def test_intent_reentry_flow(self, mock_detect_change):
        """
        测试场景 6：意图回退场景
        """
        # Setup detect_intent_change to return a change
        mock_detect_change.return_value = (True, "knowledge")

        # Create a state where we're in clarification after a report query
        state: AdReportState = {
            "session_id": "test_session_6",
            "user_id": "test_user",
            "user_input": "昨天的曝光数据",
            "conversation_history": [],
            "intent_category": "report",
            "intent_confidence": 0.9,
            "intent_classify_source": "llm",
            "intent_reason": "test reason",
            "reentry_count": 0,
            "needs_clarification": True,
            "clarification": {
                "type": "missing_advertiser",
                "question": "请问你想查看哪个广告主的数据？",
                "options": [],
                "allow_custom_input": True,
                "missing_fields": ["advertiser_ids"]
            },
            "clarify_next": None,
            "pending_clarification_input": None,
            "reject_reason": None,
            "report_intent_result": None,
            "query_type": "report",
            "rag_context": [],
            "rag_answer": None,
            "query_intent": None,
            "ambiguity": None,
            "user_feedback": "我其实想了解什么是 CTR",  # User changes intent
            "clarification_count": 0,
            "query_request": None,
            "query_requests": [],
            "query_warnings": [],
            "query_result": None,
            "query_results": [],
            "execution_time_ms": None,
            "analysis_result": None,
            "drill_down_level": 0,
            "needs_drill_down": False,
            "insights": None,
            "final_report": None,
            "advertiser_ids": [],
            "show_advertiser_list": False,
            "error": None
        }

        # Import and test clarify_node directly
        from src.intent.clarify_node import clarify_node
        result = await clarify_node(state)

        # Verify reentry
        assert result["clarify_next"] == "reentry_top"
        assert result["intent_category"] == "knowledge"
        assert result["reentry_count"] == 1

    @pytest.mark.asyncio
    @patch("src.intent.clarify_node.detect_intent_change")
    async def test_max_reentry_exceeded(self, mock_detect_change):
        """
        测试场景 7：超过最大回退次数 → 重置会话
        """
        # Setup detect_intent_change to return a change
        mock_detect_change.return_value = (True, "knowledge")

        # Create a state with reentry_count already at MAX_REENTRY_COUNT
        from src.intent.clarify_node import MAX_REENTRY_COUNT
        state: AdReportState = {
            "session_id": "test_session_7",
            "user_id": "test_user",
            "user_input": "昨天的曝光数据",
            "conversation_history": [],
            "intent_category": "report",
            "intent_confidence": 0.9,
            "intent_classify_source": "llm",
            "intent_reason": "test reason",
            "reentry_count": MAX_REENTRY_COUNT,  # Already at max
            "needs_clarification": True,
            "clarification": {
                "type": "missing_advertiser",
                "question": "请问你想查看哪个广告主的数据？",
                "options": [],
                "allow_custom_input": True,
                "missing_fields": ["advertiser_ids"]
            },
            "clarify_next": None,
            "pending_clarification_input": None,
            "reject_reason": None,
            "report_intent_result": None,
            "query_type": "report",
            "rag_context": [],
            "rag_answer": None,
            "query_intent": None,
            "ambiguity": None,
            "user_feedback": "我其实想了解什么是 CTR",
            "clarification_count": 0,
            "query_request": None,
            "query_requests": [],
            "query_warnings": [],
            "query_result": None,
            "query_results": [],
            "execution_time_ms": None,
            "analysis_result": None,
            "drill_down_level": 0,
            "needs_drill_down": False,
            "insights": None,
            "final_report": None,
            "advertiser_ids": [],
            "show_advertiser_list": False,
            "error": None
        }

        # Test clarify_node
        from src.intent.clarify_node import clarify_node
        result = await clarify_node(state)

        # Verify max reentry exceeded
        assert result["clarify_next"] == "max_reentry_exceeded"
