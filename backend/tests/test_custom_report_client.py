import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch, MagicMock
from src.tools.custom_report_client import CustomReportClient, build_es_query, parse_es_result
from src.models import QueryRequest


@pytest.mark.asyncio
async def test_build_es_query_simple():
    """测试构建简单 ES 查询"""
    query = QueryRequest(
        metrics=["impressions", "clicks"],
        group_by=[],
        filters=[],
        time_range={"start_date": "2026-01-01", "end_date": "2026-01-31", "unit": "day"}
    )

    index, es_query = build_es_query(query)
    assert index == "ad_stat_data"
    assert "query" in es_query
    assert "aggs" in es_query
    assert "sum_impressions" in es_query["aggs"]
    assert "sum_clicks" in es_query["aggs"]


@pytest.mark.asyncio
async def test_build_es_query_with_filters():
    """测试构建带过滤条件的 ES 查询"""
    query = QueryRequest(
        metrics=["impressions"],
        group_by=[],
        filters=[{"field": "advertiser_id", "op": "eq", "value": 1}],
        time_range={"start_date": "2026-01-01", "end_date": "2026-01-31", "unit": "day"}
    )

    index, es_query = build_es_query(query)
    assert "bool" in es_query["query"]
    assert "must" in es_query["query"]["bool"]


@pytest.mark.asyncio
async def test_parse_es_result_no_group():
    """测试解析无分组的查询结果"""
    query = QueryRequest(
        metrics=["impressions", "clicks"],
        group_by=[],
        filters=[],
        time_range={"start_date": "2026-01-01", "end_date": "2026-01-31", "unit": "day"}
    )

    mock_response = {
        "aggregations": {
            "sum_impressions": {"value": {"value": 1000000}},
            "sum_clicks": {"value": {"value": 20000}},
        }
    }

    result = parse_es_result(mock_response, query, [])
    assert len(result) == 1
    assert result[0]["impressions"] == 1000000
    assert result[0]["clicks"] == 20000
    assert "ctr" in result[0]


def test_no_wow_change_in_result():
    """测试查询结果中不包含wow_change字段"""
    query = QueryRequest(
        metrics=["impressions"],
        group_by=[],
        filters=[],
        time_range={"start_date": "2026-01-01", "end_date": "2026-01-31", "unit": "day"}
    )

    mock_response = {
        "aggregations": {
            "sum_impressions": {"value": {"value": 1000}}
        }
    }

    result = parse_es_result(mock_response, query, group_by=[])

    assert len(result) > 0
    assert "wow_change" not in result[0], "wow_change 字段应该被移除"


@pytest.mark.asyncio
async def test_real_es_query():
    """测试真实 ES 查询（集成测试）"""
    client = CustomReportClient()

    query = QueryRequest(
        metrics=["impressions", "clicks", "cost"],
        group_by=[],
        filters=[],
        time_range={"start_date": "2026-01-01", "end_date": "2026-01-31", "unit": "day"}
    )

    result = await client.execute_query(query)
    assert result.success is True
    assert result.total_rows == 1
    assert len(result.data) == 1
    assert result.data[0]["impressions"] > 0
    assert result.data[0]["clicks"] > 0
    assert result.data[0]["cost"] > 0
    assert result.execution_time_ms is not None


def test_parse_es_result_date_formatting():
    """测试日期维度格式化：data_month, data_week, data_date"""
    query = QueryRequest(
        metrics=["clicks"],
        group_by=["data_month", "data_date", "data_week"],
        filters=[],
        time_range={"start_date": "2026-01-01", "end_date": "2026-01-31", "unit": "day"}
    )

    # Mock ES response with timestamp keys in milliseconds
    mock_response = {
        "aggregations": {
            "group_0": {
                "buckets": [
                    {
                        "key": 1770076800000,  # 2026-02-03 00:00:00 UTC
                        "group_1": {
                            "buckets": [
                                {
                                    "key": 1770076800000,
                                    "group_2": {
                                        "buckets": [
                                            {
                                                "key": 1770076800000,
                                                "sum_clicks": {"value": {"value": 1000}}
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
    }

    result = parse_es_result(mock_response, query, ["data_month", "data_date", "data_week"])

    assert len(result) == 1
    name_parts = result[0]["name"].split(" / ")
    assert len(name_parts) == 3

    # data_month 应该格式化为 "YYYY年MM月"
    assert "年" in name_parts[0] and "月" in name_parts[0], f"data_month 格式错误: {name_parts[0]}"

    # data_date 应该格式化为 "YYYY-MM-DD"
    assert "-" in name_parts[1] and len(name_parts[1]) == 10, f"data_date 格式错误: {name_parts[1]}"

    # data_week 应该格式化为 "YYYY年第X周"
    assert "年第" in name_parts[2] and "周" in name_parts[2], f"data_week 格式错误: {name_parts[2]}"


def test_parse_es_result_data_month_formatting():
    """测试单独按月份分组时的日期格式化"""
    query = QueryRequest(
        metrics=["clicks"],
        group_by=["data_month"],
        filters=[],
        time_range={"start_date": "2026-01-01", "end_date": "2026-03-31", "unit": "month"}
    )

    mock_response = {
        "aggregations": {
            "group_0": {
                "buckets": [
                    {"key": 1767196800000, "sum_clicks": {"value": {"value": 5000}}},  # 2026-01-01 00:00:00
                    {"key": 1769875200000, "sum_clicks": {"value": {"value": 6000}}},  # 2026-02-01 00:00:00
                    {"key": 1772294400000, "sum_clicks": {"value": {"value": 7000}}},  # 2026-03-01 00:00:00
                ]
            }
        }
    }

    result = parse_es_result(mock_response, query, ["data_month"])

    assert len(result) == 3
    assert result[0]["name"] == "2026年01月"
    assert result[1]["name"] == "2026年02月"
    assert result[2]["name"] == "2026年03月"
    assert result[0]["clicks"] == 5000


@pytest.mark.asyncio
async def test_real_es_query_with_group_by():
    """测试真实带分组的 ES 查询"""
    client = CustomReportClient()

    query = QueryRequest(
        metrics=["impressions", "clicks"],
        group_by=[{"field": "campaign_id"}],
        filters=[],
        time_range={"start_date": "2026-01-01", "end_date": "2026-01-31", "unit": "day"}
    )

    result = await client.execute_query(query)
    assert result.success is True
    assert result.total_rows >= 0  # 可能有数据或没数据，但不能失败
