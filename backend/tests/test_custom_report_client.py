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
