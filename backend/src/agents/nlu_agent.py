from typing import Dict, Any
from src.tools.time_parser import parse_time_range
from src.tools.term_mapper import map_metrics, map_dimensions
from src.tools.filter_parser import parse_filters
from src.prompts.nlu_prompt import NLU_PROMPT

async def nlu_agent(user_input: str, conversation_history: list = None) -> Dict[str, Any]:
    """
    意图理解 Agent（简化版，先用纯规则）

    Args:
        user_input: 用户自然语言输入
        conversation_history: 会话历史

    Returns:
        QueryIntent 结构化数据
    """
    # Step 1: 先用工具解析可确定的部分
    time_range_result = parse_time_range.invoke(user_input)
    metrics_result = map_metrics.invoke(user_input)
    group_by_result = map_dimensions.invoke(user_input)
    filters_result = parse_filters.invoke(user_input)

    # Step 2: 构建结果（简化版，先用纯规则）
    result = {
        "time_range": {
            "start_date": time_range_result.start_date,
            "end_date": time_range_result.end_date,
            "unit": time_range_result.unit
        },
        "metrics": metrics_result,
        "group_by": group_by_result,
        "filters": filters_result,
        "is_incremental": False,
        "intent_type": "query",
        "ambiguity": {
            "has_ambiguity": False,
            "type": None,
            "reason": None,
            "options": []
        }
    }

    return result
