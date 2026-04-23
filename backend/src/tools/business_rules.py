from langchain_core.tools import tool
from typing import Dict, Any, List

@tool
def apply_business_rules(intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    应用广告报表查询业务规则

    1. 如果分组维度包含 audience_* 字段，必须切换到 audience 索引
    2. 切换索引后必须添加对应的 audience_type 过滤
    """
    result = intent.copy()
    group_by = intent.get("group_by", [])
    filters = intent.get("filters", [])

    has_audience_dim = any(d.startswith("audience_") for d in group_by)

    if has_audience_dim:
        result["index_type"] = "audience"

        # 自动添加 audience_type 过滤（避免重复）
        existing_audience_type = any(
            f.get("field") == "audience_type" for f in filters
        )

        if not existing_audience_type:
            if "audience_gender" in group_by:
                filters.append({"field": "audience_type", "op": "=", "value": 1})
            if "audience_age" in group_by:
                filters.append({"field": "audience_type", "op": "=", "value": 2})
            if "audience_os" in group_by:
                filters.append({"field": "audience_type", "op": "=", "value": 3})

        result["filters"] = filters
    else:
        result["index_type"] = "general"

    return result
