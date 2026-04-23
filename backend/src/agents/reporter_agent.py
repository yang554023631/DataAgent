from typing import Dict, Any, List
from src.tools.formatters import (
    format_number,
    format_percent,
    format_currency,
    format_change,
    get_metric_display_name
)

def get_trend(change: float) -> str:
    """判断趋势：up, down, flat"""
    if change is None:
        return "flat"
    if change > 0.05:
        return "up"
    if change < -0.05:
        return "down"
    return "flat"

async def reporter_agent(
    query_intent: Dict[str, Any],
    query_request: Dict[str, Any],
    query_result: Dict[str, Any],
    analysis_result: Dict[str, Any]
) -> Dict[str, Any]:
    """报告生成 Agent"""
    metrics = query_request.get("metrics", [])
    data = query_result.get("data", [])
    anomalies = analysis_result.get("anomalies", [])
    rankings = analysis_result.get("rankings", {})

    # 1. 计算总体指标（汇总）
    formatted_metrics = []
    for metric in metrics:
        total = sum(float(row.get(metric, 0)) for row in data) if data else 0

        # 根据指标类型选择格式化
        if metric in ["ctr", "cvr"]:
            value = format_percent.func(total / len(data) if data else 0)
        elif metric == "cost":
            value = format_currency.func(total)
        else:
            value = format_number.func(total)

        formatted_metrics.append({
            "name": get_metric_display_name.func(metric),
            "value": value,
            "change": None,
            "trend": "flat"
        })

    # 2. 生成亮点/告警
    highlights = []
    for anomaly in anomalies:
        emoji = "🟢" if anomaly.get("change_percent", 0) > 0 else "🔴"
        metric_name = get_metric_display_name.func(anomaly.get("metric", ""))
        change_str = format_change.func(anomaly.get("change_percent", 0)) if anomaly.get("change_percent") is not None else ""
        highlights.append({
            "type": "positive" if anomaly.get("change_percent", 0) > 0 else "negative",
            "text": f"{emoji} {anomaly.get('dimension_value', '')} {metric_name} 异常：{change_str}"
        })

    # 加入洞察
    for insight in analysis_result.get("insights", []):
        highlights.append({
            "type": "info",
            "text": f"ℹ️ {insight}"
        })

    # 加入建议
    for rec in analysis_result.get("recommendations", []):
        highlights.append({
            "type": "info",
            "text": f"💡 {rec}"
        })

    # 3. 准备表格数据
    if data:
        columns = list(data[0].keys())
        rows = [list(row.values()) for row in data]
    else:
        columns = []
        rows = []

    # 4. 推荐后续查询
    next_queries = []
    if rankings.get("top"):
        next_queries.append(f"查看 {rankings['top'][0]['name']} 的详细数据")
    if len(anomalies) > 0:
        next_queries.append("按创意维度下钻分析异常点")

    # 生成标题
    time_range = query_request.get("time_range", {})
    start = time_range.get("start_date", "")
    end = time_range.get("end_date", "")
    title = f"{start} ~ {end} 广告报表分析"

    return {
        "title": title,
        "time_range": {"start": start, "end": end},
        "metrics": formatted_metrics,
        "highlights": highlights,
        "data_table": {"columns": columns, "rows": rows},
        "next_queries": next_queries
    }
