from typing import Any
from langchain_core.tools import tool

@tool
def format_number(value: Any, decimals: int = 0) -> str:
    """格式化数字为千分位"""
    try:
        num = float(value)
        if decimals > 0:
            return f"{num:,.{decimals}f}"
        return f"{int(num):,}"
    except (ValueError, TypeError):
        return str(value)

@tool
def format_percent(value: Any, decimals: int = 2) -> str:
    """格式化百分比"""
    try:
        num = float(value)
        return f"{num * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return str(value)

@tool
def format_currency(value: Any, symbol: str = "¥") -> str:
    """格式化货币"""
    try:
        num = float(value)
        return f"{symbol}{num:,.2f}"
    except (ValueError, TypeError):
        return str(value)

@tool
def format_change(value: Any) -> str:
    """格式化环比变化，带正负号"""
    try:
        num = float(value)
        sign = "+" if num >= 0 else ""
        return f"{sign}{num * 100:.2f}%"
    except (ValueError, TypeError):
        return str(value)

# 指标名称映射
METRIC_NAMES = {
    "impressions": "曝光量",
    "clicks": "点击量",
    "cost": "花费",
    "reach": "触达人数",
    "frequency": "频次",
    "ctr": "CTR",
    "cvr": "CVR",
    "roi": "ROI",
}

@tool
def get_metric_display_name(metric: str) -> str:
    """获取指标的中文名称"""
    return METRIC_NAMES.get(metric, metric)
