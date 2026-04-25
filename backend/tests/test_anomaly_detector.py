import pytest
from src.tools.anomaly_detector import detect_sudden_change, detect_z_score_outliers, calculate_rankings


def test_detect_sudden_change():
    data = [
        {"name": "渠道A", "impressions": 1000, "wow_change": 0.5},
        {"name": "渠道B", "impressions": 2000, "wow_change": -0.1},
    ]
    anomalies = detect_sudden_change.func(data, "impressions")
    assert len(anomalies) == 1
    assert anomalies[0].severity == "high"


def test_detect_z_score_outliers():
    data = [
        {"name": "A", "ctr": 0.01},
        {"name": "B", "ctr": 0.015},
        {"name": "C", "ctr": 0.012},
        {"name": "D", "ctr": 0.011},
        {"name": "E", "ctr": 0.013},
        {"name": "F", "ctr": 0.014},
        {"name": "G", "ctr": 0.05},  # 离群点
    ]
    outliers = detect_z_score_outliers.func(data, "ctr")
    assert len(outliers) >= 1


def test_calculate_rankings():
    data = [
        {"name": "渠道A", "impressions": 1000},
        {"name": "渠道B", "impressions": 2000},
        {"name": "渠道C", "impressions": 500},
    ]
    result = calculate_rankings.func(data, "impressions")
    assert "top" in result
    assert "bottom" in result
    assert result["top"][0]["name"] == "渠道B"
