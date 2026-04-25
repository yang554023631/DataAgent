from langchain_core.tools import tool
from typing import Dict, Any, List

@tool
def apply_business_rules(intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    应用广告报表查询业务规则

    1. 如果分组维度包含 audience_* 字段，必须切换到 audience 索引
    2. 切换索引后必须添加对应的 audience_type 过滤
    3. 把 advertiser_ids 转换为查询过滤条件
    """
    result = intent.copy()
    group_by = intent.get("group_by", [])
    filters = intent.get("filters", [])
    advertiser_ids = intent.get("advertiser_ids", [])

    # 把广告主 ID 转换为过滤条件
    for adv_id in advertiser_ids:
        # 检查是否已存在相同的广告主过滤
        exists = any(
            f.get("field") == "advertiser_id" and str(f.get("value")) == str(adv_id)
            for f in filters
        )
        if not exists:
            filters.append({"field": "advertiser_id", "op": "eq", "value": int(adv_id)})

    result["filters"] = filters

    # 维度去重：date 和 month 同时出现时，保留 date，移除 month
    if "data_date" in group_by and "data_month" in group_by:
        group_by.remove("data_month")
        warnings = intent.get("warnings", [])
        warnings.append("检测到同时选择按天和按月，已自动保留按天维度")
        result["warnings"] = warnings
        result["group_by"] = group_by

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
