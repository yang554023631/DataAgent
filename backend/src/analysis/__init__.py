"""
CoT Analysis Planner Module

Public interface (deep module):
- CotPlanner / get_cot_planner     : 主入口，生成分析计划
- IntentAnalyzer / create_intent_analyzer : 意图分析
- ReportFormatter                  : 报告格式化
- AnalysisPlanResult / CotResultStatus : 核心结果类型

内部实现（不保证稳定，请从子模块直接导入）:
- prompts, models, fewshot_retriever, chart_validator 等
"""

# === 公共接口 ===
from .intent_analyzer import IntentAnalyzer, create_intent_analyzer
from .cot_planner import CotPlanner, CotResultStatus, get_cot_planner
from .report_formatter import ReportFormatter
from .models import (
    AnalysisPlanResult,
    AnalysisResult,
    QualityResult,
    QualityIssue,
    FieldContext,
    CotReasoning,
    AnalysisTimeRange,
    FilterPlan,
    FilterResult,
)

__all__ = [
    # 主入口
    "CotPlanner",
    "get_cot_planner",
    "IntentAnalyzer",
    "create_intent_analyzer",
    "ReportFormatter",
    # 核心状态/结果类型
    "AnalysisPlanResult",
    "CotResultStatus",
    # 下游节点需要传递的类型
    "AnalysisResult",
    "QualityResult",
    "QualityIssue",
    "FieldContext",
    "CotReasoning",
    "AnalysisTimeRange",
    "FilterPlan",
    "FilterResult",
]
