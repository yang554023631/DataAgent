from typing import Dict, Any, List
from src.tools.anomaly_detector import (
    detect_sudden_change,
    detect_z_score_outliers,
    calculate_rankings,
    Anomaly
)

async def analyst_agent(query_result: Dict[str, Any], query_request: Dict[str, Any]) -> Dict[str, Any]:
    """数据分析 Agent"""
    data = query_result.get("data", [])
    metrics = query_request.get("metrics", ["impressions"])

    all_anomalies: List[Anomaly] = []

    for metric in metrics:
        # 检测环比突变
        if data and any("wow" in key.lower() for key in data[0].keys()):
            changes = detect_sudden_change.func(data, metric)
            all_anomalies.extend(changes)

        # 检测离群点
        outliers = detect_z_score_outliers.func(data, metric)
        all_anomalies.extend(outliers)

    # 计算排名（取第一个指标）
    main_metric = metrics[0] if metrics else "impressions"
    rankings = calculate_rankings.func(data, main_metric)

    # 生成洞察
    insights = []
    if all_anomalies:
        high_count = sum(1 for a in all_anomalies if a.severity == "high")
        if high_count > 0:
            insights.append(f"发现 {high_count} 个高度异常的数据点，建议重点关注")

    if len(all_anomalies) == 0:
        insights.append("数据表现平稳，未发现显著异常")

    # 生成建议
    recommendations = []
    if rankings.get("bottom"):
        recommendations.append(f"建议重点关注表现较差的渠道：{rankings['bottom'][0]['name']}")

    # 总结
    summary_parts = []
    if all_anomalies:
        summary_parts.append(f"检测到 {len(all_anomalies)} 个异常点")
    else:
        summary_parts.append("整体数据表现平稳")
    summary = "，".join(summary_parts)

    return {
        "summary": summary,
        "anomalies": [a.__dict__ for a in all_anomalies],
        "insights": insights,
        "rankings": rankings,
        "recommendations": recommendations
    }
