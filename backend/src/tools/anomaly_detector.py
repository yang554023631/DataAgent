from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from dataclasses import dataclass

@dataclass
class Anomaly:
    type: str  # sudden_change, outlier
    metric: str
    dimension_key: str
    dimension_value: str
    current_value: float
    change_percent: Optional[float] = None
    z_score: Optional[float] = None
    severity: str = "medium"  # low, medium, high

@tool
def detect_sudden_change(
    data: List[Dict[str, Any]],
    metric_field: str,
    change_field: str = "wow_change",
    threshold_high: float = 0.4,
    threshold_medium: float = 0.2
) -> List[Anomaly]:
    """检测环比突变"""
    anomalies = []

    for row in data:
        change = row.get(change_field)
        if change is None:
            continue

        abs_change = abs(float(change))
        if abs_change >= threshold_medium:
            severity = "high" if abs_change >= threshold_high else "medium"

            anomalies.append(Anomaly(
                type="sudden_change",
                metric=metric_field,
                dimension_key=row.get("dimension", "unknown"),
                dimension_value=str(row.get("name", row.get("id", "unknown"))),
                current_value=float(row.get(metric_field, 0)),
                change_percent=float(change),
                severity=severity
            ))

    return anomalies

@tool
def detect_z_score_outliers(
    data: List[Dict[str, Any]],
    metric_field: str,
    threshold: float = 2.0
) -> List[Anomaly]:
    """使用 Z-score 检测离群点"""
    values = [float(row.get(metric_field, 0)) for row in data if metric_field in row]

    if len(values) < 3:
        return []

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = variance ** 0.5

    if std == 0:
        return []

    anomalies = []
    for row in data:
        value = float(row.get(metric_field, 0))
        z_score = (value - mean) / std

        if abs(z_score) >= threshold:
            severity = "high" if abs(z_score) >= 3 else "medium"
            anomalies.append(Anomaly(
                type="outlier",
                metric=metric_field,
                dimension_key=row.get("dimension", "unknown"),
                dimension_value=str(row.get("name", row.get("id", "unknown"))),
                current_value=value,
                z_score=z_score,
                severity=severity
            ))

    return anomalies

@tool
def calculate_rankings(
    data: List[Dict[str, Any]],
    metric_field: str,
    top_n: int = 5
) -> Dict[str, List[Dict[str, Any]]]:
    """计算 Top/Bottom 排名"""
    sorted_data = sorted(
        data,
        key=lambda x: float(x.get(metric_field, 0)),
        reverse=True
    )

    return {
        "top": [
            {"name": str(row.get("name", row.get("id", i))), "value": float(row.get(metric_field, 0))}
            for i, row in enumerate(sorted_data[:top_n])
        ],
        "bottom": [
            {"name": str(row.get("name", row.get("id", len(sorted_data)-i-1))), "value": float(row.get(metric_field, 0))}
            for i, row in enumerate(sorted_data[-top_n:])
        ]
    }
