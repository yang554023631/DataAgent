"""CoT Analysis Planner Module"""

from .prompts import (
    COT_SYSTEM_PROMPT,
    COT_USER_PROMPT_TEMPLATE,
    build_cot_user_prompt,
    build_field_context_section,
    build_advertisers_section,
    build_few_shot_section
)
from .intent_analyzer import (
    IntentAnalyzer,
    IntentAnalysisResult,
    RuleBasedExtractor,
    create_intent_analyzer
)
from .fewshot_retriever import (
    FewshotRetriever,
    RetrievedExample,
    get_fewshot_retriever,
)
from .cot_planner import (
    CotPlanner,
    CotPlanResult,
    CotResultStatus,
    ClarificationRequest,
    get_cot_planner,
)
from .report_formatter import (
    ReportFormatter,
)
from .models import (
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
    FilterResult,
    AnalysisChartConfig,
    AnalysisDataTable,
    AnalysisResult,
    QualityCheckType,
    QualityAction,
    QualityIssue,
    QualityResult,
)

__all__ = [
    # Prompts
    "COT_SYSTEM_PROMPT",
    "COT_USER_PROMPT_TEMPLATE",
    "build_cot_user_prompt",
    "build_field_context_section",
    "build_advertisers_section",
    "build_few_shot_section",
    # Intent Analyzer
    "IntentAnalyzer",
    "IntentAnalysisResult",
    "RuleBasedExtractor",
    "create_intent_analyzer",
    # Few-shot Retriever
    "FewshotRetriever",
    "RetrievedExample",
    "get_fewshot_retriever",
    # CoT Planner
    "CotPlanner",
    "CotPlanResult",
    "CotResultStatus",
    "ClarificationRequest",
    "get_cot_planner",
    # Report Formatter
    "ReportFormatter",
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
]
