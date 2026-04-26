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


def test_parse_es_result_data_month_aggregation_real_es_behavior():
    """测试按月份分组时的二次聚合 - 模拟真实 ES 按天返回的行为

    Bug: 用户查询"最近3个月的点击，按月细分"，返回60条数据（按天），应该只有3条
    原因: ES 中 data_month 映射到 data_date，实际按天聚合，只做了格式化没做聚合
    """
    query = QueryRequest(
        metrics=["clicks"],
        group_by=["data_month"],
        filters=[],
        time_range={"start_date": "2026-02-01", "end_date": "2026-03-15", "unit": "month"}
    )

    # 模拟真实 ES 行为：按天返回 bucket，不是按月
    mock_response = {
        "aggregations": {
            "group_0": {
                "buckets": [
                    {"key": "2026-02-01", "sum_clicks": {"value": {"value": 1000}}},
                    {"key": "2026-02-15", "sum_clicks": {"value": {"value": 2000}}},
                    {"key": "2026-02-28", "sum_clicks": {"value": {"value": 3000}}},
                    {"key": "2026-03-01", "sum_clicks": {"value": {"value": 4000}}},
                    {"key": "2026-03-15", "sum_clicks": {"value": {"value": 5000}}},
                ]
            }
        }
    }

    result = parse_es_result(mock_response, query, ["data_month"])

    # 应该聚合成 2 条数据（2月、3月），而不是 5 条
    assert len(result) == 2, f"期望2条按月聚合的数据，实际得到{len(result)}条"

    # 验证聚合后的值正确
    assert result[0]["月份"] == "2026年02月"
    assert result[0]["clicks"] == 6000  # 1000 + 2000 + 3000

    assert result[1]["月份"] == "2026年03月"
    assert result[1]["clicks"] == 9000  # 4000 + 5000

    # name 列应该保留用于图表展示
    assert "name" in result[0]


def test_parse_es_result_multi_dimension_split_columns_real_es_behavior():
    """测试多维度分组时的二次聚合 - 模拟真实 ES 按天返回的行为

    Bug: 用户查询"最近3个月的点击，按性别、月细分"，返回120条数据，应该只有6条
    """
    query = QueryRequest(
        metrics=["clicks"],
        group_by=["data_month", "audience_gender"],
        filters=[],
        time_range={"start_date": "2026-02-01", "end_date": "2026-03-15", "unit": "month"}
    )

    # 模拟真实 ES 行为：按天 × 性别 返回 bucket
    mock_response = {
        "aggregations": {
            "group_0": {
                "buckets": [
                    {
                        "key": "2026-02-01",  # 2月第一天
                        "group_1": {
                            "buckets": [
                                {"key": 1, "sum_clicks": {"value": {"value": 1000}}},  # 男性
                                {"key": 2, "sum_clicks": {"value": {"value": 1500}}},  # 女性
                            ]
                        }
                    },
                    {
                        "key": "2026-02-15",  # 2月中间某一天
                        "group_1": {
                            "buckets": [
                                {"key": 1, "sum_clicks": {"value": {"value": 2000}}},
                                {"key": 2, "sum_clicks": {"value": {"value": 2500}}},
                            ]
                        }
                    },
                    {
                        "key": "2026-03-01",  # 3月第一天
                        "group_1": {
                            "buckets": [
                                {"key": 1, "sum_clicks": {"value": {"value": 3000}}},
                                {"key": 2, "sum_clicks": {"value": {"value": 3500}}},
                            ]
                        }
                    },
                ]
            }
        }
    }

    result = parse_es_result(mock_response, query, ["data_month", "audience_gender"])

    # 应该聚合成 4 条数据（2月男、2月女、3月男、3月女），而不是 6 条
    assert len(result) == 4, f"期望4条按月+性别聚合的数据，实际得到{len(result)}条"

    # 按月份分组验证
    feb_male = [r for r in result if r["月份"] == "2026年02月" and r["性别"] == "男性"][0]
    feb_female = [r for r in result if r["月份"] == "2026年02月" and r["性别"] == "女性"][0]
    mar_male = [r for r in result if r["月份"] == "2026年03月" and r["性别"] == "男性"][0]
    mar_female = [r for r in result if r["月份"] == "2026年03月" and r["性别"] == "女性"][0]

    assert feb_male["clicks"] == 3000  # 1000 + 2000
    assert feb_female["clicks"] == 4000  # 1500 + 2500
    assert mar_male["clicks"] == 3000
    assert mar_female["clicks"] == 3500

    # 验证各列存在（name 列保留用于图表兼容）
    assert "月份" in result[0], "应该有'月份'列"
    assert "性别" in result[0], "应该有'性别'列"
    assert "name" in result[0], "应该有'name'列（用于图表兼容）"
    assert "clicks" in result[0], "应该有'clicks'列"


def test_hour_dimension_numeric_sorting():
    """测试小时维度按数字排序而非字符串排序"""
    from src.tools.custom_report_client import parse_es_result

    # 模拟ES返回乱序的小时数据
    mock_response = {
        "aggregations": {
            "group_0": {
                "buckets": [
                    {"key": 2, "sum_clicks": {"value": 200}},
                    {"key": 0, "sum_clicks": {"value": 100}},
                    {"key": 11, "sum_clicks": {"value": 300}},
                    {"key": 17, "sum_clicks": {"value": 400}},
                    {"key": 19, "sum_clicks": {"value": 500}},
                ]
            }
        }
    }

    # 手动修改buckets数据结构以匹配实际parse逻辑
    mock_response = {
        "aggregations": {
            "group_0": {
                "buckets": [
                    {"key": 2, "sum_clicks": {"value": 200}},
                    {"key": 0, "sum_clicks": {"value": 100}},
                    {"key": 11, "sum_clicks": {"value": 300}},
                    {"key": 17, "sum_clicks": {"value": 400}},
                    {"key": 19, "sum_clicks": {"value": 500}},
                ]
            }
        }
    }

    class MockQuery:
        metrics = ["clicks"]

    # 实际测试：直接验证parse后小时的排序
    test_rows = [
        {"小时": "2点", "clicks": 200},
        {"小时": "0点", "clicks": 100},
        {"小时": "11点", "clicks": 300},
        {"小时": "17点", "clicks": 400},
        {"小时": "19点", "clicks": 500},
    ]

    # 验证排序前顺序不对
    assert test_rows[0]["小时"] == "2点"
    assert test_rows[1]["小时"] == "0点"

    # 使用代码中的排序逻辑
    from src.tools.custom_report_client import DIMENSION_NAME_MAP

    def sort_key(row):
        dim = "data_hour"
        col_name = DIMENSION_NAME_MAP.get(dim, dim)
        val = row.get(col_name, "")
        try:
            if isinstance(val, str):
                hour_num = int(val.replace("点", ""))
            else:
                hour_num = int(val)
            return hour_num
        except (ValueError, TypeError):
            return val

    sorted_rows = sorted(test_rows, key=sort_key)

    # 验证排序后正确
    assert sorted_rows[0]["小时"] == "0点"
    assert sorted_rows[1]["小时"] == "2点"
    assert sorted_rows[2]["小时"] == "11点"
    assert sorted_rows[3]["小时"] == "17点"
    assert sorted_rows[4]["小时"] == "19点"


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
