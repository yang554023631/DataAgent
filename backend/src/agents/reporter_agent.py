from typing import Dict, Any, List, Optional
from src.tools.formatters import (
    format_number,
    format_percent,
    format_currency,
    format_change,
    get_metric_display_name
)


def auto_select_chart_type_for_comparison(group_by: List[str]) -> str:
    """根据维度自动选择对比图表类型"""
    time_dimensions = {"data_date", "data_day", "data_hour", "date", "day", "hour"}
    if any(dim in group_by for dim in time_dimensions):
        return "line"  # 时间维度对比用折线图
    return "bar"  # 分类维度对比用柱状图


def format_comparison_report(
    query_intent: Dict[str, Any],
    query_requests: List[Dict[str, Any]],
    query_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """格式化对比查询报告"""
    if len(query_results) < 2:
        return None

    result1, result2 = query_results[:2]
    data1 = result1.get("data", [])
    data2 = result2.get("data", [])
    metrics = query_requests[0].get("metrics", [])
    group_by = query_requests[0].get("group_by", [])

    # 计算两个周期的总指标
    formatted_metrics = []
    for metric in metrics:
        total1 = sum(float(row.get(metric, 0)) for row in data1) if data1 else 0
        total2 = sum(float(row.get(metric, 0)) for row in data2) if data2 else 0

        # 根据指标类型选择格式化
        if metric in ["ctr", "cvr"]:
            value1 = format_percent.func(total1 / len(data1) if data1 else 0)
            value2 = format_percent.func(total2 / len(data2) if data2 else 0)
        elif metric == "cost":
            value1 = format_currency.func(total1)
            value2 = format_currency.func(total2)
        else:
            value1 = format_number.func(total1)
            value2 = format_number.func(total2)

        # 计算变化率
        change = (total2 - total1) / total1 * 100 if total1 != 0 else 0
        trend = "up" if change > 0 else "down" if change < 0 else "flat"

        formatted_metrics.append({
            "name": get_metric_display_name.func(metric),
            "period1": value1,
            "period2": value2,
            "change": f"{change:+.1f}%",
            "trend": trend
        })

    # 获取两个周期的标签
    time_range1 = query_requests[0].get("time_range", {})
    time_range2 = query_requests[1].get("time_range", {})
    period1_label = f"{time_range1.get('start_date', '')}"
    period2_label = f"{time_range2.get('start_date', '')}"

    # 生成图表配置
    chart_type = auto_select_chart_type_for_comparison(group_by)

    # 颜色配置（绿色表示第一个周期，蓝色表示第二个周期）
    colors = ["#10b981", "#3b82f6"]

    chart_config = {
        "type": chart_type,
        "series": [
            {"name": period1_label, "color": colors[0]},
            {"name": period2_label, "color": colors[1]}
        ],
        "comparison_data": {
            "period1": {"name": period1_label, "color": colors[0], "data": data1},
            "period2": {"name": period2_label, "color": colors[1], "data": data2}
        }
    }

    # 生成标题
    title = f"{period1_label} vs {period2_label} 对比分析"

    # 生成亮点（变化率提示）
    highlights = []
    for metric in formatted_metrics:
        if metric["trend"] == "up":
            highlights.append({
                "type": "positive",
                "text": f"🟢 {metric['name']} 上升 {metric['change']}，表现良好"
            })
        elif metric["trend"] == "down":
            highlights.append({
                "type": "negative",
                "text": f"🔴 {metric['name']} 下降 {metric['change']}，需要关注"
            })

    # 准备合并后的表格数据
    columns = ["维度", f"{period1_label}", f"{period2_label}", "变化"]
    rows = []

    # 如果有分组维度，展示每个维度的对比
    if group_by and data1 and data2 and len(data1) == len(data2):
        for i, (row1, row2) in enumerate(zip(data1, data2)):
            dim_value = row1.get("name") or row1.get(group_by[0]) or f"第{i+1}项"
            metric_value1 = row1.get(metrics[0], 0) if metrics else 0
            metric_value2 = row2.get(metrics[0], 0) if metrics else 0
            change = (metric_value2 - metric_value1) / metric_value1 * 100 if metric_value1 != 0 else 0
            rows.append([
                str(dim_value),
                format_number.func(metric_value1),
                format_number.func(metric_value2),
                f"{change:+.1f}%"
            ])
    else:
        # 无分组维度，展示总指标对比
        for metric in formatted_metrics:
            rows.append([
                metric["name"],
                metric["period1"],
                metric["period2"],
                metric["change"]
            ])

    return {
        "title": title,
        "is_comparison": True,
        "time_range": {"start": period1_label, "end": period2_label},
        "metrics": formatted_metrics,
        "highlights": highlights,
        "data_table": {"columns": columns, "rows": rows},
        "chart_config": chart_config,
        "next_queries": [
            "查看更多维度的对比分析",
            "分渠道对比效果",
            "分受众对比效果"
        ]
    }

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
        change_percent = anomaly.get("change_percent", 0) or 0
        emoji = "🟢" if change_percent > 0 else "🔴"
        metric_name = get_metric_display_name.func(anomaly.get("metric", ""))
        change_str = format_change.func(change_percent) if change_percent != 0 else ""
        highlights.append({
            "type": "positive" if change_percent > 0 else "negative",
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

        # 检测是否有实际维度列（如果有，则移除重复的name列）
        dimension_columns = {
            "性别", "年龄段", "操作系统", "系统版本", "国家", "城市", "行业",
            "兴趣标签", "日期", "月份", "周", "小时", "渠道", "计划ID", "广告主ID"
        }
        has_actual_dimensions = any(col in dimension_columns for col in columns)

        # 如果有实际维度列，则移除name列（避免重复显示）
        if has_actual_dimensions and "name" in columns:
            columns.remove("name")

        rows = [list(row[col] for col in columns) for row in data]
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

    # 5. 生成图表配置（用于前端渲染）
    group_by = query_request.get("group_by", [])
    chart_config = None
    if data and len(data) > 1 and metrics:  # 至少有2条数据才渲染图表
        chart_type = auto_select_chart_type_for_comparison(group_by)
        chart_config = {
            "type": chart_type,
            "series": [{"name": get_metric_display_name.func(m), "color": "#3b82f6"} for m in metrics],
            "metrics": metrics
        }

    return {
        "title": title,
        "time_range": {"start": start, "end": end},
        "metrics": formatted_metrics,
        "highlights": highlights,
        "data_table": {"columns": columns, "rows": rows},
        "chart_config": chart_config,
        "next_queries": next_queries
    }
