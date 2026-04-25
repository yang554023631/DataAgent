from langchain_core.tools import tool
from typing import Dict, Any, List

@tool
def auto_select_chart_type(metrics: List[str], dimensions: List[str]) -> Dict[str, Any]:
    """
    根据指标和维度自动选择合适的图表类型

    规则:
    - 有时间维度 → line 折线图
    - 分类维度 < 10 → bar 柱状图
    - 分类维度 < 5 + 看占比场景 → pie 饼图
    - 其他 → table 表格
    """
    has_time = "data_date" in dimensions or "data_week" in dimensions or "data_month" in dimensions

    if has_time:
        return {
            "type": "line",
            "x_axis": dimensions[0] if dimensions else "data_date",
            "y_axis": metrics
        }

    dim_count = len(dimensions)

    if 0 < dim_count < 5:
        return {
            "type": "bar",
            "x_axis": dimensions[0],
            "y_axis": metrics
        }

    if 5 <= dim_count < 10:
        return {
            "type": "bar",
            "x_axis": dimensions[0],
            "y_axis": metrics
        }

    return {"type": "table"}
