"""CoT Analysis Planner Models Tests"""
import pytest
from src.analysis.models import (
    # Enums
    EntityLevel,
    FilterType,
    AnalysisType,
    ChartType,
    # CoT Reasoning
    CotStep,
    CotReasoning,
    # Quality Check
    QualityCheck,
    # Analysis Plan
    AnalysisTimeRange,
    AnalysisComparison,
    AnalysisPlan,
    # Field Context
    FieldContext,
    # Top-Level Result
    AnalysisPlanResult,
    # Example
    CotExample,
    # Re-exports
    FilterCondition,
    FilterStep,
    FilterPlan,
    QualityCheckType,
    QualityAction,
)


class TestEnums:
    """Test enumeration values"""

    def test_entity_level_values(self):
        """Test EntityLevel has correct values"""
        assert EntityLevel.ADVERTISER == "advertiser"
        assert EntityLevel.CAMPAIGN == "campaign"
        assert EntityLevel.AD_GROUP == "ad_group"
        assert EntityLevel.CREATIVE == "creative"

    def test_filter_type_values(self):
        """Test FilterType has correct values"""
        assert FilterType.NONE == "none"
        assert FilterType.WHERE == "where"
        assert FilterType.HAVING == "having"
        assert FilterType.CROSS_LEVEL == "cross_level"
        assert FilterType.MIXED == "mixed"

    def test_analysis_type_values(self):
        """Test AnalysisType has correct values"""
        assert AnalysisType.ENTITY_TABLE == "entity_table"
        assert AnalysisType.TIME_TREND == "time_trend"
        assert AnalysisType.PERIOD_COMPARISON == "period_comparison"
        assert AnalysisType.AUDIENCE_DISTRIBUTION == "audience_distribution"
        assert AnalysisType.SUMMARY == "summary"

    def test_chart_type_values(self):
        """Test ChartType has correct values"""
        assert ChartType.LINE == "line"
        assert ChartType.BAR == "bar"
        assert ChartType.PIE == "pie"
        assert ChartType.KPI_CARD == "kpi_card"
        assert ChartType.TABLE == "table"


class TestCotReasoningModels:
    """Test CoT reasoning models"""

    def test_cot_step_creation(self):
        """Test CotStep can be created with valid data"""
        step = CotStep(
            step_id="step_1",
            step_name="问题理解",
            content="用户想查看最近7天的消耗趋势",
            confidence=0.9,
        )
        assert step.step_id == "step_1"
        assert step.step_name == "问题理解"
        assert "消耗趋势" in step.content
        assert step.confidence == 0.9

    def test_cot_step_confidence_optional(self):
        """Test CotStep confidence is optional"""
        step = CotStep(
            step_id="step_1",
            step_name="问题理解",
            content="用户想查看数据",
        )
        assert step.confidence is None

    def test_cot_reasoning_creation(self):
        """Test CotReasoning can be created"""
        steps = [
            CotStep(step_id="step_1", step_name="理解", content="理解问题"),
            CotStep(step_id="step_2", step_name="分析", content="分析需求"),
        ]
        reasoning = CotReasoning(
            steps=steps,
            summary="问题分析完成",
            raw_text="原始推理文本",
        )
        assert len(reasoning.steps) == 2
        assert reasoning.summary == "问题分析完成"
        assert reasoning.raw_text == "原始推理文本"

    def test_cot_reasoning_defaults(self):
        """Test CotReasoning defaults"""
        reasoning = CotReasoning()
        assert reasoning.steps == []
        assert reasoning.summary == ""


class TestQualityCheckModel:
    """Test QualityCheck model"""

    def test_quality_check_creation(self):
        """Test QualityCheck can be created"""
        check = QualityCheck(
            check_type=QualityCheckType.MIN_DATA_POINTS,
            threshold=2,
            action=QualityAction.WARN,
        )
        assert check.check_type == QualityCheckType.MIN_DATA_POINTS
        assert check.threshold == 2
        assert check.action == QualityAction.WARN


class TestAnalysisPlanModels:
    """Test Analysis Plan models"""

    def test_analysis_time_range_creation(self):
        """Test AnalysisTimeRange"""
        time_range = AnalysisTimeRange(
            start_date="2026-04-01",
            end_date="2026-04-30",
            granularity="day",
        )
        assert time_range.start_date == "2026-04-01"
        assert time_range.end_date == "2026-04-30"
        assert time_range.granularity == "day"

    def test_analysis_time_range_default_granularity(self):
        """Test AnalysisTimeRange default granularity"""
        time_range = AnalysisTimeRange(
            start_date="2026-04-01",
            end_date="2026-04-30",
        )
        assert time_range.granularity == "day"

    def test_analysis_comparison_creation(self):
        """Test AnalysisComparison"""
        comparison = AnalysisComparison(
            compare_start_date="2026-03-01",
            compare_end_date="2026-03-31",
        )
        assert comparison.compare_start_date == "2026-03-01"
        assert comparison.compare_end_date == "2026-03-31"

    def test_analysis_plan_creation_minimal(self):
        """Test AnalysisPlan with minimal fields"""
        time_range = AnalysisTimeRange(
            start_date="2026-04-01",
            end_date="2026-04-30",
        )
        plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=time_range,
        )
        assert plan.analysis_type == AnalysisType.TIME_TREND
        assert plan.chart_type == ChartType.LINE
        assert plan.metrics == ["cost"]
        assert plan.time_granularity == "day"
        assert plan.limit == 100

    def test_analysis_plan_creation_full(self):
        """Test AnalysisPlan with all fields"""
        time_range = AnalysisTimeRange(
            start_date="2026-04-01",
            end_date="2026-04-30",
        )
        comparison = AnalysisComparison(
            compare_start_date="2026-03-01",
            compare_end_date="2026-03-31",
        )
        quality_check = QualityCheck(
            check_type=QualityCheckType.MAX_ROWS,
            threshold=100,
            action=QualityAction.TRIM_TOP,
        )

        plan = AnalysisPlan(
            analysis_type=AnalysisType.PERIOD_COMPARISON,
            chart_type=ChartType.BAR,
            metrics=["cost", "impression"],
            time_range=time_range,
            compare_time_range=comparison,
            time_granularity="week",
            group_by="campaign_id",
            order_by="cost",
            order_dir="asc",
            limit=50,
            quality_checks=[quality_check],
        )
        assert plan.analysis_type == AnalysisType.PERIOD_COMPARISON
        assert plan.compare_time_range is not None
        assert plan.time_granularity == "week"
        assert plan.limit == 50
        assert len(plan.quality_checks) == 1


class TestFieldContextModel:
    """Test FieldContext model"""

    def test_field_context_creation(self):
        """Test FieldContext creation"""
        time_range = AnalysisTimeRange(
            start_date="2026-04-01",
            end_date="2026-04-30",
        )
        context = FieldContext(
            advertiser_ids=[1, 2, 3],
            time_range=time_range,
            target_level=EntityLevel.CAMPAIGN,
            metrics=["cost", "click"],
            audience_dimension="gender",
            entity_ids=[101, 102, 103],
            additional_fields={"custom": "value"},
        )
        assert context.advertiser_ids == [1, 2, 3]
        assert context.target_level == EntityLevel.CAMPAIGN
        assert context.additional_fields == {"custom": "value"}

    def test_field_context_defaults(self):
        """Test FieldContext defaults"""
        context = FieldContext()
        assert context.advertiser_ids is None
        assert context.additional_fields == {}


class TestAnalysisPlanResultModel:
    """Test AnalysisPlanResult model"""

    def test_analysis_plan_result_creation(self):
        """Test full AnalysisPlanResult creation"""
        time_range = AnalysisTimeRange(
            start_date="2026-04-01",
            end_date="2026-04-30",
        )
        filter_plan = FilterPlan(
            filter_type="none",
            target_level="advertiser",
            steps=[],
        )
        analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=time_range,
        )
        cot_reasoning = CotReasoning(
            steps=[
                CotStep(step_id="step_1", step_name="理解", content="理解问题"),
            ],
            summary="分析完成",
        )

        result = AnalysisPlanResult(
            target_level=EntityLevel.ADVERTISER,
            filter_plan=filter_plan,
            analysis_plan=analysis_plan,
            reasoning=cot_reasoning,
        )

        assert result.target_level == EntityLevel.ADVERTISER
        assert result.filter_plan.filter_type == "none"
        assert result.analysis_plan.analysis_type == AnalysisType.TIME_TREND
        assert result.reasoning is not None
        assert len(result.quality_checks) == 0


class TestCotExampleModel:
    """Test CotExample model"""

    def test_cot_example_positive_creation(self):
        """Test positive CotExample creation"""
        example = CotExample(
            example_id="test_01",
            question="广告主最近7天的消耗趋势",
            category="positive",
            analysis_type=AnalysisType.TIME_TREND,
            filter_type=FilterType.NONE,
            reasoning_chinese="Step 1: 问题理解\n用户想查看趋势",
            plan={"target_level": "advertiser"},
        )
        assert example.example_id == "test_01"
        assert example.category == "positive"
        assert example.analysis_type == AnalysisType.TIME_TREND
        assert example.notes is None

    def test_cot_example_negative_with_notes(self):
        """Test negative CotExample with notes"""
        example = CotExample(
            example_id="neg_01",
            question="错误的问题",
            category="negative",
            reasoning_chinese="Step 1: 错误示范",
            plan={"target_level": "advertiser"},
            notes="这是错误示例，原因是...",
        )
        assert example.category == "negative"
        assert example.notes is not None
        assert "错误示例" in example.notes

    def test_cot_example_optional_fields(self):
        """Test CotExample optional fields"""
        example = CotExample(
            example_id="test_02",
            question="简单问题",
            category="positive",
            reasoning_chinese="Step 1: 简单",
            plan={"test": "plan"},
        )
        assert example.analysis_type is None
        assert example.filter_type is None
