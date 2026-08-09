"""CoT Analysis Planner Pydantic Models

This module contains the Pydantic models for the Chain-of-Thought analysis planner,
including reasoning steps, filter plans, analysis plans, quality checks, and results.
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field

# Re-export existing models from nl_dsl.models for convenience
from src.nl_dsl.models import (
    FilterCondition,
    FilterStep,
    FilterPlan,
    FilterResult,
    AnalysisChartConfig,
    AnalysisDataTable,
    AnalysisResult,
    QualityCheckType,
    QualityAction,
    QualityIssue,
    QualityResult,
    EmptyCheckErrorType,
    EmptyCheckResult,
)

# =============================================================================
# Enums
# =============================================================================

class EntityLevel(str, Enum):
    """Entity level enumeration."""
    ADVERTISER = "advertiser"
    CAMPAIGN = "campaign"
    AD_GROUP = "ad_group"
    CREATIVE = "creative"


class FilterType(str, Enum):
    """Filter type enumeration."""
    NONE = "none"
    WHERE = "where"
    HAVING = "having"
    CROSS_LEVEL = "cross_level"
    MIXED = "mixed"


class AnalysisType(str, Enum):
    """Analysis type enumeration."""
    ENTITY_TABLE = "entity_table"
    TIME_TREND = "time_trend"
    PERIOD_COMPARISON = "period_comparison"
    AUDIENCE_DISTRIBUTION = "audience_distribution"
    SUMMARY = "summary"


class ChartType(str, Enum):
    """Chart type enumeration."""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    KPI_CARD = "kpi_card"
    TABLE = "table"


# =============================================================================
# CoT Reasoning Models
# =============================================================================

class CotStep(BaseModel):
    """Single step in the CoT reasoning chain."""
    step_id: str = Field(..., description="Step identifier, e.g., 'step_1'")
    step_name: str = Field(..., description="Step name, e.g., '问题理解'")
    content: str = Field(..., description="Step content in Chinese")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score for this step")


class CotReasoning(BaseModel):
    """Complete Chain-of-Thought reasoning."""
    steps: List[CotStep] = Field(default_factory=list, description="Ordered list of reasoning steps")
    summary: str = Field("", description="Brief summary of the reasoning")
    raw_text: Optional[str] = Field(None, description="Raw reasoning text from LLM")


# =============================================================================
# Quality Check Model (standalone, different from existing QualityCheckType)
# =============================================================================

class QualityCheck(BaseModel):
    """Quality check configuration for analysis plans."""
    check_type: QualityCheckType = Field(..., description="Type of quality check")
    threshold: Any = Field(..., description="Threshold value for the check")
    action: QualityAction = Field(..., description="Action to take if check fails")


# =============================================================================
# Analysis Plan (refined per design doc)
# =============================================================================

class AnalysisTimeRange(BaseModel):
    """Analysis time range."""
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    granularity: Optional[str] = Field("day", description="Time granularity: day/week/month")


class AnalysisComparison(BaseModel):
    """Period comparison configuration."""
    compare_start_date: str = Field(..., description="Comparison period start date")
    compare_end_date: str = Field(..., description="Comparison period end date")


class AnalysisPlan(BaseModel):
    """Analysis plan (the analysis part, different from existing AnalysisPlan)."""
    analysis_type: AnalysisType = Field(..., description="Type of analysis")
    chart_type: ChartType = Field(..., description="Type of chart to generate")
    metrics: List[str] = Field(default_factory=list, description="List of metrics to analyze")
    time_range: AnalysisTimeRange = Field(..., description="Time range for analysis")
    compare_time_range: Optional[AnalysisComparison] = Field(None, description="Comparison period (for period_comparison)")
    time_granularity: str = Field("day", description="Time granularity: day/week/month")
    audience_dimension: Optional[str] = Field(None, description="Audience dimension (for audience_distribution)")
    group_by: Optional[str] = Field(None, description="Group by field (for entity_table or multi-series trend)")
    order_by: Optional[str] = Field(None, description="Order by field")
    order_dir: str = Field("desc", description="Order direction: asc/desc")
    limit: int = Field(100, description="Limit number of results")
    quality_checks: List[QualityCheck] = Field(default_factory=list, description="Quality checks to apply")


# =============================================================================
# Field Context (shared field pool)
# =============================================================================

class FieldContext(BaseModel):
    """Shared field context pool for CoT reasoning."""
    advertiser_ids: Optional[List[int]] = Field(None, description="Advertiser IDs")
    time_range: Optional[AnalysisTimeRange] = Field(None, description="Time range")
    target_level: Optional[EntityLevel] = Field(None, description="Target entity level")
    metrics: Optional[List[str]] = Field(None, description="Metrics list")
    audience_dimension: Optional[str] = Field(None, description="Audience dimension")
    compare_time_range: Optional[AnalysisComparison] = Field(None, description="Comparison time range")
    entity_ids: Optional[List[Any]] = Field(None, description="Pre-filtered entity IDs")
    additional_fields: Dict[str, Any] = Field(default_factory=dict, description="Additional custom fields")


# =============================================================================
# Top-Level Analysis Plan Result
# =============================================================================

class AnalysisPlanResult(BaseModel):
    """Top-level analysis plan result combining filter and analysis plans."""
    target_level: EntityLevel = Field(..., description="Target entity level")
    filter_plan: FilterPlan = Field(..., description="Filter plan")
    analysis_plan: AnalysisPlan = Field(..., description="Analysis plan")
    reasoning: Optional[CotReasoning] = Field(None, description="CoT reasoning")
    field_context: Optional[FieldContext] = Field(None, description="Shared field context")
    quality_checks: List[QualityCheck] = Field(default_factory=list, description="Quality checks (combined)")


# =============================================================================
# Few-Shot Example Model
# =============================================================================

class CotExample(BaseModel):
    """Few-shot example for CoT reasoning."""
    example_id: str = Field(..., description="Unique example identifier")
    question: str = Field(..., description="User question")
    category: str = Field(..., description="Category: positive/negative")
    analysis_type: Optional[AnalysisType] = Field(None, description="Analysis type for this example")
    filter_type: Optional[FilterType] = Field(None, description="Filter type for this example")
    reasoning_chinese: str = Field(..., description="Chinese reasoning steps (6-7 steps)")
    plan: Dict[str, Any] = Field(..., description="Condensed JSON plan (AnalysisPlanResult format)")
    notes: Optional[str] = Field(None, description="Notes for negative examples: what's wrong + correct approach")


__all__ = [
    # Enums
    "EntityLevel",
    "FilterType",
    "AnalysisType",
    "ChartType",
    # CoT Reasoning
    "CotStep",
    "CotReasoning",
    # Quality Check
    "QualityCheck",
    # Analysis Plan
    "AnalysisTimeRange",
    "AnalysisComparison",
    "AnalysisPlan",
    # Field Context
    "FieldContext",
    # Top-Level Result
    "AnalysisPlanResult",
    # Example
    "CotExample",
    # Re-exports
    "FilterCondition",
    "FilterStep",
    "FilterPlan",
    "FilterResult",
    "AnalysisChartConfig",
    "AnalysisDataTable",
    "AnalysisResult",
    "QualityCheckType",
    "QualityAction",
    "QualityIssue",
    "QualityResult",
    "EmptyCheckErrorType",
    "EmptyCheckResult",
]
