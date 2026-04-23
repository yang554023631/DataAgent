from typing import List, Dict, Any
from langchain_core.tools import tool
from src.tools.term_mapper import FILTER_VALUE_MAPPING

@tool
def parse_filters(text: str) -> List[Dict[str, Any]]:
    """
    解析自然语言中的过滤条件

    示例:
    "安卓端" → [{"field": "audience_os", "op": "=", "value": 2}]
    "非iOS" → [{"field": "audience_os", "op": "!=", "value": 1}]
    "男性" → [{"field": "audience_gender", "op": "=", "value": 1}]
    """
    filters = []

    for term, mapping in FILTER_VALUE_MAPPING.items():
        if term in text:
            filters.append({
                "field": mapping["field"],
                "op": "=",
                "value": mapping["value"]
            })

    return filters
