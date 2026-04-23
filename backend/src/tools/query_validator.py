from langchain_core.tools import tool
from typing import Dict, Any, List
from datetime import datetime

@tool
def validate_and_warn(query_request: Dict[str, Any]) -> List[str]:
    """
    校验查询参数并返回警告列表

    检查项:
    - 维度数量限制（最多3个）
    - 时间范围大小限制（最多90天）
    - 预计数据量警告
    """
    warnings = []

    # 维度数量检查
    group_by = query_request.get("group_by", [])
    if len(group_by) > 3:
        warnings.append("分组维度超过3个，图表可能难以阅读")

    # 时间范围检查
    time_range = query_request.get("time_range", {})
    if isinstance(time_range, dict):
        start = time_range.get("start_date")
        end = time_range.get("end_date")

        if start and end:
            try:
                start_date = datetime.fromisoformat(start)
                end_date = datetime.fromisoformat(end)
                days = (end_date - start_date).days

                if days > 90:
                    warnings.append(
                        "时间范围超过90天，查询可能较慢 need_confirm"
                    )
            except (ValueError, TypeError):
                pass

    return warnings
