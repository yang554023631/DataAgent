"""
Tools - 工具模块集合

按领域划分为三个逻辑子模块（deep modules）：

1. query_engine  查询引擎
   - 职责：ES 查询构建、执行、结果解析
   - 主入口：execute_ad_report_query(query_request)
   - 内部实现：custom_report_client, hierarchy_utils, term_mapper,
               time_parser, filter_parser, business_rules, query_validator

2. insights  洞察分析
   - 职责：洞察规则计算、异常检测、LLM 洞察生成
   - 主入口：（待整合，目前直接使用 insight_rules 等）
   - 内部实现：insight_rules, insight_llm, insight_config, anomaly_detector

3. reporting  报告辅助
   - 职责：图表选择、格式化、澄清问题生成
   - 内部实现：chart_selector, formatters, clarification_generator

注：目前文件仍在 tools/ 根目录，逐步迁移到子模块中。
调用方应优先从逻辑分组中 import，而非直接 import 单个文件。
"""

# === 查询引擎 (query_engine) ===
from .custom_report_client import (
    CustomReportClient,
    create_custom_report_client,
    init_custom_report_client,
)
from .executor import execute_ad_report_query
from .query_validator import validate_and_warn
from .business_rules import apply_business_rules
from .filter_parser import parse_filters

# === 洞察分析 (insights) ===
# （注：insight_rules 等模块较大，暂时直接暴露，后续逐步收敛到统一入口）

# === 报告辅助 (reporting) ===
from .chart_selector import auto_select_chart_type
from .clarification_generator import generate_clarification_options, ClarificationQuestion
from .formatters import (
    format_number,
    format_percent,
    format_currency,
    format_change,
    get_metric_display_name,
    METRIC_NAMES,
)

# === 公共 API ===
__all__ = [
    # 查询引擎
    "CustomReportClient",
    "create_custom_report_client",
    "init_custom_report_client",
    "execute_ad_report_query",
    "validate_and_warn",
    "apply_business_rules",
    "parse_filters",
    # 报告辅助
    "auto_select_chart_type",
    "generate_clarification_options",
    "ClarificationQuestion",
    "format_number",
    "format_percent",
    "format_currency",
    "format_change",
    "get_metric_display_name",
    "METRIC_NAMES",
]
