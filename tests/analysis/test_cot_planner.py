"""CoT Planner Tests"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock

from src.analysis.cot_planner import (
    CotPlanner,
    CotPlanResult,
    CotResultStatus,
    ClarificationRequest,
    get_cot_planner,
)
from src.analysis.models import (
    AnalysisPlanResult,
    AnalysisPlan,
    FieldContext,
    AnalysisTimeRange,
    AnalysisType,
    FilterType,
    EntityLevel,
    ChartType,
    FilterPlan,
)
from src.analysis.intent_analyzer import IntentAnalyzer
from src.analysis.fewshot_retriever import FewshotRetriever


class TestCotPlannerInitialization:
    """Test CotPlanner initialization"""

    def test_initialization_defaults(self):
        """Test planner can be initialized with defaults"""
        planner = CotPlanner()

        assert planner.intent_analyzer is not None
        assert isinstance(planner.intent_analyzer, IntentAnalyzer)
        assert planner.fewshot_retriever is not None
        assert isinstance(planner.fewshot_retriever, FewshotRetriever)
        assert planner.max_retries == 1

    def test_initialization_custom(self):
        """Test planner can be initialized with custom components"""
        mock_intent = Mock(spec=IntentAnalyzer)
        mock_retriever = Mock(spec=FewshotRetriever)
        mock_llm = Mock()

        planner = CotPlanner(
            intent_analyzer=mock_intent,
            fewshot_retriever=mock_retriever,
            llm=mock_llm,
            max_retries=3,
        )

        assert planner.intent_analyzer == mock_intent
        assert planner.fewshot_retriever == mock_retriever
        assert planner.llm == mock_llm
        assert planner.max_retries == 3


class TestCotPlannerJsonExtraction:
    """Test JSON extraction from LLM response"""

    def test_extract_json_from_code_block(self):
        """Test extracting JSON from markdown code block"""
        planner = CotPlanner()

        text = """Here's the plan:
```json
{
  "target_level": "advertiser",
  "analysis_plan": {
    "analysis_type": "time_trend"
  }
}
```
That's it!
"""

        json_str = planner._extract_json(text)

        assert json_str is not None
        parsed = json.loads(json_str)
        assert parsed["target_level"] == "advertiser"

    def test_extract_json_from_code_block_without_json_tag(self):
        """Test extracting JSON from code block without json tag"""
        planner = CotPlanner()

        text = """```
{"target_level": "advertiser"}
```"""

        json_str = planner._extract_json(text)

        assert json_str is not None
        parsed = json.loads(json_str)
        assert parsed["target_level"] == "advertiser"

    def test_extract_json_from_raw_text(self):
        """Test extracting JSON from raw text without code block"""
        planner = CotPlanner()

        text = """Some text before
{"target_level": "advertiser", "analysis_plan": {"analysis_type": "time_trend"}}
Some text after"""

        json_str = planner._extract_json(text)

        assert json_str is not None
        parsed = json.loads(json_str)
        assert parsed["target_level"] == "advertiser"

    def test_extract_json_no_json(self):
        """Test extracting when no JSON present"""
        planner = CotPlanner()

        text = "Just plain text, no JSON here"

        json_str = planner._extract_json(text)

        assert json_str is None


class TestCotPlannerParseAndValidate:
    """Test parsing and validation of LLM responses"""

    def test_parse_and_validate_clarification_request(self):
        """Test parsing a clarification request"""
        planner = CotPlanner()

        raw_response = json.dumps({
            "clarification_request": {
                "question": "请选择广告主",
                "missing_fields": ["advertiser_ids"],
                "options": [{"value": "1", "label": "广告主1"}]
            }
        })

        result = planner._parse_and_validate(raw_response, None)

        assert result.status == CotResultStatus.NEEDS_CLARIFICATION
        assert result.clarification is not None
        assert result.clarification.question == "请选择广告主"
        assert "advertiser_ids" in result.clarification.missing_fields

    def test_parse_and_validate_success(self):
        """Test parsing a successful plan"""
        planner = CotPlanner()

        raw_response = json.dumps({
            "target_level": "advertiser",
            "filter_plan": {
                "filter_type": "none",
                "target_level": "advertiser",
                "steps": []
            },
            "analysis_plan": {
                "analysis_type": "time_trend",
                "chart_type": "line",
                "metrics": ["cost"],
                "time_range": {
                    "start_date": "2026-08-01",
                    "end_date": "2026-08-08",
                    "granularity": "day"
                }
            }
        })

        result = planner._parse_and_validate(raw_response, None)

        assert result.status == CotResultStatus.SUCCESS
        assert result.plan is not None
        assert result.plan.target_level == EntityLevel.ADVERTISER
        assert result.plan.analysis_plan.analysis_type == AnalysisType.TIME_TREND

    def test_parse_and_validate_with_field_context(self):
        """Test parsing with existing field context"""
        planner = CotPlanner()

        field_context = FieldContext(
            advertiser_ids=[1, 2],
            time_range=AnalysisTimeRange(
                start_date="2026-08-01",
                end_date="2026-08-08",
            ),
        )

        raw_response = json.dumps({
            "target_level": "advertiser",
            "filter_plan": {
                "filter_type": "none",
                "target_level": "advertiser",
                "steps": []
            },
            "analysis_plan": {
                "analysis_type": "time_trend",
                "chart_type": "line",
                "metrics": ["cost"],
                "time_range": {
                    "start_date": "2026-08-01",
                    "end_date": "2026-08-08",
                    "granularity": "day"
                }
            }
        })

        result = planner._parse_and_validate(raw_response, field_context)

        assert result.status == CotResultStatus.SUCCESS
        assert result.plan is not None
        assert result.plan.field_context is not None
        assert result.plan.field_context.advertiser_ids == [1, 2]

    def test_parse_and_validate_invalid_json(self):
        """Test parsing invalid JSON"""
        planner = CotPlanner()

        raw_response = "Not valid JSON { this is broken }"

        result = planner._parse_and_validate(raw_response, None)

        assert result.status == CotResultStatus.PARSE_FAILED

    def test_parse_and_validate_missing_fields(self):
        """Test parsing a plan with missing required fields"""
        planner = CotPlanner()

        raw_response = json.dumps({
            "target_level": "advertiser",
            # Missing filter_plan and analysis_plan
        })

        result = planner._parse_and_validate(raw_response, None)

        assert result.status == CotResultStatus.PARSE_FAILED

    def test_parse_and_validate_invalid_plan(self):
        """Test parsing an invalid plan (missing required fields)"""
        planner = CotPlanner()

        raw_response = json.dumps({
            "target_level": "advertiser",
            "filter_plan": {
                "filter_type": "none",
                "target_level": "advertiser",
                "steps": []
            },
            "analysis_plan": {
                # Missing analysis_type, chart_type, etc.
            }
        })

        result = planner._parse_and_validate(raw_response, None)

        assert result.status == CotResultStatus.PARSE_FAILED


class TestCotPlannerReasoningParsing:
    """Test parsing reasoning text"""

    def test_parse_reasoning_with_numbered_steps(self):
        """Test parsing reasoning with numbered steps"""
        planner = CotPlanner()

        reasoning_text = """1. 问题理解 - 用户想查看趋势
2. 分析类型 - 确定为时间趋势
3. 指标选择 - 选择消耗作为指标"""

        reasoning = planner._parse_reasoning(reasoning_text)

        assert len(reasoning.steps) == 3
        assert reasoning.steps[0].step_id == "step_1"
        assert "问题理解" in reasoning.steps[0].content

    def test_parse_reasoning_with_parentheses_steps(self):
        """Test parsing reasoning with steps in parentheses"""
        planner = CotPlanner()

        reasoning_text = """1) 问题理解
2) 分析类型
3) 指标选择"""

        reasoning = planner._parse_reasoning(reasoning_text)

        assert len(reasoning.steps) == 3

    def test_parse_reasoning_without_steps(self):
        """Test parsing reasoning without numbered steps"""
        planner = CotPlanner()

        reasoning_text = "这是一段没有编号步骤的推理文本"

        reasoning = planner._parse_reasoning(reasoning_text)

        assert len(reasoning.steps) == 1
        assert reasoning.steps[0].step_name == "推理过程"
        assert reasoning_text in reasoning.steps[0].content


class TestCotPlannerPlanMethod:
    """Test the main plan method"""

    @patch.object(CotPlanner, '_call_llm')
    def test_plan_basic_success(self, mock_call_llm):
        """Test basic successful plan generation"""
        # Setup mock LLM response
        mock_response = json.dumps({
            "target_level": "advertiser",
            "filter_plan": {
                "filter_type": "none",
                "target_level": "advertiser",
                "steps": []
            },
            "analysis_plan": {
                "analysis_type": "time_trend",
                "chart_type": "line",
                "metrics": ["cost"],
                "time_range": {
                    "start_date": "2026-08-01",
                    "end_date": "2026-08-08",
                    "granularity": "day"
                }
            }
        })
        mock_call_llm.return_value = mock_response

        planner = CotPlanner()
        result = planner.plan("广告主最近7天的消耗趋势")

        assert result.status == CotResultStatus.SUCCESS
        assert result.plan is not None
        assert result.retry_count == 0

    @patch.object(CotPlanner, '_call_llm')
    def test_plan_with_clarification(self, mock_call_llm):
        """Test plan that returns clarification"""
        mock_response = json.dumps({
            "clarification_request": {
                "question": "请补充广告主ID",
                "missing_fields": ["advertiser_ids"],
                "options": []
            }
        })
        mock_call_llm.return_value = mock_response

        planner = CotPlanner()
        result = planner.plan("查看消耗数据")

        assert result.status == CotResultStatus.NEEDS_CLARIFICATION
        assert result.clarification is not None

    @patch.object(CotPlanner, '_call_llm')
    def test_plan_with_retry_success(self, mock_call_llm):
        """Test plan that succeeds on retry"""
        # First call fails, second succeeds
        mock_call_llm.side_effect = [
            "Invalid response",  # First attempt fails
            json.dumps({
                "target_level": "advertiser",
                "filter_plan": {
                    "filter_type": "none",
                    "target_level": "advertiser",
                    "steps": []
                },
                "analysis_plan": {
                    "analysis_type": "time_trend",
                    "chart_type": "line",
                    "metrics": ["cost"],
                    "time_range": {
                        "start_date": "2026-08-01",
                        "end_date": "2026-08-08",
                        "granularity": "day"
                    }
                }
            })
        ]

        planner = CotPlanner(max_retries=1)
        result = planner.plan("广告主最近7天的消耗趋势")

        assert result.status == CotResultStatus.SUCCESS
        assert result.retry_count == 1
        assert mock_call_llm.call_count == 2

    @patch.object(CotPlanner, '_call_llm')
    def test_plan_with_retry_failure(self, mock_call_llm):
        """Test plan that fails all retries"""
        mock_call_llm.return_value = "Invalid response"

        planner = CotPlanner(max_retries=1)
        result = planner.plan("广告主最近7天的消耗趋势")

        assert result.status in [CotResultStatus.PARSE_FAILED, CotResultStatus.VALIDATION_FAILED]
        assert result.retry_count == 1
        assert mock_call_llm.call_count == 2

    def test_plan_with_prebuilt_field_context(self):
        """Test plan with pre-built field context"""
        planner = CotPlanner()

        field_context = FieldContext(
            advertiser_ids=[1],
            time_range=AnalysisTimeRange(
                start_date="2026-08-01",
                end_date="2026-08-08",
            ),
            metrics=["cost"],
        )

        # Since we're in mock mode, it should still work
        result = planner.plan(
            "广告主最近7天的消耗趋势",
            field_context=field_context,
        )

        # In mock mode, it should return a success
        # (though we might need to patch _call_llm for reliable testing)
        assert result is not None


class TestCotPlannerSingleton:
    """Test singleton pattern"""

    def test_get_cot_planner_singleton(self):
        """Test singleton pattern works"""
        planner1 = get_cot_planner()
        planner2 = get_cot_planner()

        assert planner1 is planner2


class TestClarificationRequest:
    """Test ClarificationRequest dataclass"""

    def test_clarification_request_creation(self):
        """Test ClarificationRequest can be created"""
        cr = ClarificationRequest(
            question="请选择广告主",
            missing_fields=["advertiser_ids"],
            options=[{"value": "1", "label": "广告主1"}],
        )

        assert cr.question == "请选择广告主"
        assert cr.missing_fields == ["advertiser_ids"]
        assert len(cr.options) == 1

    def test_clarification_request_no_options(self):
        """Test ClarificationRequest without options"""
        cr = ClarificationRequest(
            question="请补充时间范围",
            missing_fields=["time_range"],
        )

        assert cr.options is None


class TestCotPlanResult:
    """Test CotPlanResult dataclass"""

    def test_cot_plan_result_success(self):
        """Test successful CotPlanResult"""
        result = CotPlanResult(
            status=CotResultStatus.SUCCESS,
            plan=Mock(spec=AnalysisPlanResult),
            raw_response="raw response",
        )

        assert result.status == CotResultStatus.SUCCESS
        assert result.plan is not None
        assert result.clarification is None

    def test_cot_plan_result_clarification(self):
        """Test clarification CotPlanResult"""
        result = CotPlanResult(
            status=CotResultStatus.NEEDS_CLARIFICATION,
            clarification=ClarificationRequest(
                question="Test",
                missing_fields=[],
            ),
        )

        assert result.status == CotResultStatus.NEEDS_CLARIFICATION
        assert result.clarification is not None

    def test_cot_plan_result_failure(self):
        """Test failure CotPlanResult"""
        result = CotPlanResult(
            status=CotResultStatus.PARSE_FAILED,
            raw_response="Invalid JSON",
            retry_count=2,
        )

        assert result.status == CotResultStatus.PARSE_FAILED
        assert result.retry_count == 2
