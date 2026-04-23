from typing import Dict, Any
from src.tools.business_rules import apply_business_rules
from src.tools.chart_selector import auto_select_chart_type
from src.tools.query_validator import validate_and_warn

async def planner_agent(query_intent: Dict[str, Any], user_feedback: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    查询规划 Agent

    Args:
        query_intent: NLU 输出的查询意图
        user_feedback: 用户澄清反馈（如果有）

    Returns:
        query_request 和 query_warnings
    """
    # Step 1: 应用业务规则
    intent_with_rules = apply_business_rules.func(query_intent)

    # Step 2: 自动选择图表类型
    metrics = intent_with_rules.get("metrics", [])
    dimensions = intent_with_rules.get("group_by", [])
    chart_config = auto_select_chart_type.func(metrics, dimensions)

    # Step 3: 构建 QueryRequest
    query_request = {
        "index_type": intent_with_rules.get("index_type", "general"),
        "time_range": intent_with_rules.get("time_range", {}),
        "metrics": metrics,
        "group_by": dimensions,
        "filters": intent_with_rules.get("filters", []),
        "chart_config": chart_config
    }

    # Step 4: 校验参数生成警告
    query_warnings = validate_and_warn.func(query_request)

    return {
        "query_request": query_request,
        "query_warnings": query_warnings
    }
