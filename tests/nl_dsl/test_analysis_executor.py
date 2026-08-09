"""分析执行器测试"""
import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any, List
from src.nl_dsl.analysis_executor import AnalysisExecutor
from src.nl_dsl.models import (
    AnalysisPlan,
    AnalysisTimeRange,
    AnalysisComparison,
    AnalysisChartConfig,
)


@pytest.fixture
def mock_es_client():
    """Mock Elasticsearch client"""
    client = Mock()
    return client


@pytest.fixture
def entity_name_resolver():
    """实体名称解析器"""
    return {
        101: "618大促计划",
        102: "品牌推广计划",
        103: "新品上市计划",
    }


@pytest.fixture
def analysis_executor(mock_es_client, entity_name_resolver):
    """Analysis executor instance with mocked ES client"""
    return AnalysisExecutor(
        es_client=mock_es_client,
        entity_name_resolver=entity_name_resolver,
    )


@pytest.fixture
def sample_time_range():
    """Sample time range"""
    return AnalysisTimeRange(
        start_date="2026-04-01",
        end_date="2026-04-30",
        granularity="day",
    )


class TestAnalysisExecutor:
    """分析执行器测试"""

    def test_execute_single_series_trend(self, analysis_executor, mock_es_client, sample_time_range):
        """测试单系列时间趋势分析"""
        analysis_plan = AnalysisPlan(
            analysis_type="time_trend",
            time_range=sample_time_range,
            metrics=["cost"],
        )

        # Mock ES response
        mock_es_client.search.return_value = {
            "aggregations": {
                "by_date": {
                    "buckets": [
                        {"key": "2026-04-01", "doc_count": 10, "metric_sum": {"value": 100}},
                        {"key": "2026-04-02", "doc_count": 10, "metric_sum": {"value": 150}},
                        {"key": "2026-04-03", "doc_count": 10, "metric_sum": {"value": 120}},
                    ],
                },
            },
        }

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is True
        assert result.chart_data is not None
        assert result.data_table is not None
        assert len(result.chart_data["data"]) == 3
        assert result.chart_data["data"][0]["date"] == "2026-04-01"
        assert result.chart_data["data"][0]["cost"] == 100
        assert mock_es_client.search.called

    def test_execute_multi_series_trend(self, analysis_executor, mock_es_client, sample_time_range):
        """测试多系列时间趋势分析"""
        analysis_plan = AnalysisPlan(
            analysis_type="time_trend",
            time_range=sample_time_range,
            metrics=["cost"],
            series_level="campaign",
        )

        # Mock ES response
        mock_es_client.search.return_value = {
            "aggregations": {
                "by_date": {
                    "buckets": [
                        {
                            "key": "2026-04-01",
                            "doc_count": 10,
                            "by_campaign": {
                                "buckets": [
                                    {"key": 101, "doc_count": 5, "metric_sum": {"value": 60}},
                                    {"key": 102, "doc_count": 5, "metric_sum": {"value": 40}},
                                ],
                            },
                        },
                        {
                            "key": "2026-04-02",
                            "doc_count": 10,
                            "by_campaign": {
                                "buckets": [
                                    {"key": 101, "doc_count": 5, "metric_sum": {"value": 80}},
                                    {"key": 102, "doc_count": 5, "metric_sum": {"value": 70}},
                                ],
                            },
                        },
                    ],
                },
            },
        }

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            entity_ids=[101, 102],
            entity_level="campaign",
            advertiser_ids=["6"],
        )

        assert result.success is True
        assert result.chart_data is not None
        assert result.data_table is not None
        assert len(result.chart_data["data"]) == 2
        assert "101" in result.chart_data["data"][0]
        assert "102" in result.chart_data["data"][0]

    def test_execute_entity_table(self, analysis_executor, mock_es_client, sample_time_range):
        """测试实体表格分析"""
        analysis_plan = AnalysisPlan(
            analysis_type="entity_table",
            time_range=sample_time_range,
            metrics=["cost", "impressions", "ctr"],
            group_by_level="campaign",
            order_by="cost",
            order_dir="desc",
            limit=10,
        )

        # Mock ES response
        mock_es_client.search.return_value = {
            "aggregations": {
                "by_campaign": {
                    "buckets": [
                        {
                            "key": 101,
                            "doc_count": 10,
                            "sum_cost": {"value": 1000},
                            "sum_impressions": {"value": 10000},
                            "ctr": {"value": 0.1},
                        },
                        {
                            "key": 102,
                            "doc_count": 10,
                            "sum_cost": {"value": 800},
                            "sum_impressions": {"value": 8000},
                            "ctr": {"value": 0.08},
                        },
                    ],
                },
            },
        }

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is True
        assert result.data_table is not None
        assert len(result.data_table.rows) == 2
        assert result.data_table.rows[0]["campaign_name"] == "618大促计划"
        assert result.data_table.rows[0]["cost"] == 1000
        assert mock_es_client.search.called

    def test_execute_entity_table_with_entity_filter(self, analysis_executor, mock_es_client, sample_time_range):
        """测试带实体过滤的实体表格分析"""
        analysis_plan = AnalysisPlan(
            analysis_type="entity_table",
            time_range=sample_time_range,
            metrics=["cost", "impressions"],
            group_by_level="campaign",
        )

        # Mock ES response
        mock_es_client.search.return_value = {
            "aggregations": {
                "by_campaign": {
                    "buckets": [
                        {
                            "key": 101,
                            "doc_count": 10,
                            "sum_cost": {"value": 1000},
                            "sum_impressions": {"value": 10000},
                        },
                    ],
                },
            },
        }

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            entity_ids=[101, 102],
            entity_level="campaign",
            advertiser_ids=["6"],
        )

        assert result.success is True

        # Verify that entity filter was included in DSL
        call_args = mock_es_client.search.call_args
        dsl = call_args[1]["body"]
        has_terms_filter = False
        for filter_cond in dsl["query"]["bool"]["filter"]:
            if isinstance(filter_cond, dict) and "terms" in filter_cond:
                if "campaign_id" in filter_cond["terms"]:
                    assert set(filter_cond["terms"]["campaign_id"]) == {101, 102}
                    has_terms_filter = True
        assert has_terms_filter, "DSL should include terms filter for campaign_ids"

    def test_execute_period_comparison(self, analysis_executor, mock_es_client, sample_time_range):
        """测试时期对比分析"""
        analysis_plan = AnalysisPlan(
            analysis_type="period_comparison",
            time_range=sample_time_range,
            metrics=["cost", "impressions", "ctr"],
            comparison=AnalysisComparison(
                compare_start_date="2026-03-01",
                compare_end_date="2026-03-31",
            ),
        )

        # Mock ES response
        mock_es_client.search.return_value = {
            "aggregations": {
                "current_period": {
                    "doc_count": 100,
                    "sum_cost": {"value": 10000},
                    "sum_impressions": {"value": 100000},
                    "ctr": {"value": 0.1},
                },
                "compare_period": {
                    "doc_count": 100,
                    "sum_cost": {"value": 8000},
                    "sum_impressions": {"value": 80000},
                    "ctr": {"value": 0.09},
                },
            },
        }

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is True
        assert result.chart_data is not None
        assert result.data_table is not None
        assert len(result.data_table.rows) == 3  # 3 metrics

        # Check that change calculation is correct
        cost_row = next(r for r in result.data_table.rows if r["metric"] == "cost")
        assert cost_row["current"] == 10000
        assert cost_row["compare"] == 8000
        assert cost_row["change"] == 2000
        assert cost_row["change_pct"] == 25.0

    def test_execute_audience_distribution(self, analysis_executor, mock_es_client, sample_time_range):
        """测试受众分布分析"""
        analysis_plan = AnalysisPlan(
            analysis_type="audience_distribution",
            time_range=sample_time_range,
            metrics=["cost"],
            audience_type="gender",
        )

        # Mock ES response
        mock_es_client.search.return_value = {
            "aggregations": {
                "by_audience": {
                    "buckets": [
                        {"key": "male", "doc_count": 10, "metric_sum": {"value": 600}},
                        {"key": "female", "doc_count": 10, "metric_sum": {"value": 400}},
                    ],
                },
            },
        }

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is True
        assert result.chart_data is not None
        assert result.data_table is not None
        assert len(result.chart_data["data"]) == 2

        # Check percentage calculation
        assert result.data_table.rows[0]["percentage"] == 60.0
        assert result.data_table.rows[1]["percentage"] == 40.0

    def test_execute_summary(self, analysis_executor, mock_es_client, sample_time_range):
        """测试汇总指标分析"""
        analysis_plan = AnalysisPlan(
            analysis_type="summary",
            time_range=sample_time_range,
            metrics=["cost", "impressions", "clicks", "ctr"],
        )

        # Mock ES response
        mock_es_client.search.return_value = {
            "aggregations": {
                "sum_cost": {"value": 10000},
                "sum_impressions": {"value": 100000},
                "sum_clicks": {"value": 10000},
                "ctr": {"value": 0.1},
            },
        }

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is True
        assert result.chart_data is not None
        assert result.data_table is not None
        assert len(result.data_table.rows) == 4

    def test_execute_with_retry_success(self, analysis_executor, mock_es_client, sample_time_range):
        """测试重试成功"""
        analysis_plan = AnalysisPlan(
            analysis_type="summary",
            time_range=sample_time_range,
            metrics=["cost"],
        )

        # 第一次失败，第二次成功
        mock_es_client.search.side_effect = [
            Exception("Connection error"),
            {
                "aggregations": {
                    "sum_cost": {"value": 10000},
                },
            },
        ]

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is True
        assert mock_es_client.search.call_count == 2

    def test_execute_with_retry_failure(self, analysis_executor, mock_es_client, sample_time_range):
        """测试重试失败"""
        analysis_plan = AnalysisPlan(
            analysis_type="summary",
            time_range=sample_time_range,
            metrics=["cost"],
        )

        # 两次都失败
        mock_es_client.search.side_effect = Exception("Connection error")

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is False
        assert "Connection error" in result.error
        assert mock_es_client.search.call_count == 2

    def test_execute_unknown_analysis_type(self, analysis_executor, mock_es_client, sample_time_range):
        """测试未知的分析类型"""
        analysis_plan = AnalysisPlan(
            analysis_type="unknown_type",
            time_range=sample_time_range,
            metrics=["cost"],
        )

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is False
        assert "Unknown analysis type" in result.error

    def test_execute_entity_table_missing_group_by_level(self, analysis_executor, sample_time_range):
        """测试实体表格分析缺少 group_by_level"""
        analysis_plan = AnalysisPlan(
            analysis_type="entity_table",
            time_range=sample_time_range,
            metrics=["cost"],
        )

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is False
        assert "requires group_by_level" in result.error

    def test_execute_audience_distribution_missing_audience_type(self, analysis_executor, sample_time_range):
        """测试受众分布分析缺少 audience_type"""
        analysis_plan = AnalysisPlan(
            analysis_type="audience_distribution",
            time_range=sample_time_range,
            metrics=["cost"],
        )

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is False
        assert "requires audience_type" in result.error

    def test_execute_period_comparison_missing_comparison(self, analysis_executor, sample_time_range):
        """测试时期对比分析缺少 comparison 配置"""
        analysis_plan = AnalysisPlan(
            analysis_type="period_comparison",
            time_range=sample_time_range,
            metrics=["cost"],
        )

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is False
        assert "requires comparison config" in result.error

    def test_execute_with_custom_chart_config(self, analysis_executor, mock_es_client, sample_time_range):
        """测试自定义图表配置"""
        custom_chart_config = AnalysisChartConfig(
            type="bar",
            title="自定义图表标题",
            x_axis={"field": "date", "label": "自定义X轴"},
            y_axis={"field": "cost", "label": "自定义Y轴"},
        )

        analysis_plan = AnalysisPlan(
            analysis_type="time_trend",
            time_range=sample_time_range,
            metrics=["cost"],
            chart_config=custom_chart_config,
        )

        # Mock ES response
        mock_es_client.search.return_value = {
            "aggregations": {
                "by_date": {
                    "buckets": [
                        {"key": "2026-04-01", "doc_count": 10, "metric_sum": {"value": 100}},
                    ],
                },
            },
        }

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is True
        assert result.chart_data["chart_config"]["type"] == "bar"
        assert result.chart_data["chart_config"]["title"] == "自定义图表标题"

    def test_derived_metrics_are_decimal_format(self, analysis_executor, mock_es_client, sample_time_range):
        """Test that derived metrics (CTR, etc.) are in decimal format (0.05 = 5%), not percentage format (5.0)"""
        analysis_plan = AnalysisPlan(
            analysis_type="entity_table",
            time_range=sample_time_range,
            metrics=["ctr", "cost"],  # Include CTR (derived) and cost (base)
            group_by_level="campaign",
        )

        # Mock ES response with CTR = 0.1 (10%), cost = 100
        mock_es_client.search.return_value = {
            "aggregations": {
                "by_campaign": {
                    "buckets": [
                        {
                            "key": 101,
                            "doc_count": 10,
                            "sum_cost": {"value": 100},
                            "sum_clicks": {"value": 100},
                            "sum_impressions": {"value": 1000},
                            "ctr": {"value": 0.1},  # Decimal format: 0.1 = 10%
                        },
                    ],
                },
            },
        }

        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.success is True
        assert result.data_table is not None
        assert len(result.data_table.rows) == 1

        # Verify CTR is in decimal format (0.1), not percentage (10.0)
        campaign_row = result.data_table.rows[0]
        assert campaign_row["ctr"] == 0.1  # Should be 0.1 (10% as decimal)
        assert campaign_row["ctr"] != 10.0  # Should NOT be 10.0 (percentage format)

        # Also verify base metric comes through correctly
        assert campaign_row["cost"] == 100

    def test_multi_series_trend_with_entity_filter(self, analysis_executor, mock_es_client, sample_time_range):
        """Test that multi-series trend applies entity filter correctly (even when series_level != entity_level)"""
        analysis_plan = AnalysisPlan(
            analysis_type="time_trend",
            time_range=sample_time_range,
            metrics=["cost"],
            series_level="campaign",  # Show series by campaign
        )

        # Mock ES response
        mock_es_client.search.return_value = {
            "aggregations": {
                "by_date": {
                    "buckets": [
                        {
                            "key": "2026-04-01",
                            "doc_count": 10,
                            "by_campaign": {
                                "buckets": [
                                    {"key": 101, "doc_count": 5, "metric_sum": {"value": 60}},
                                ],
                            },
                        },
                    ],
                },
            },
        }

        # Execute with entity_ids at ad_group level (different from series_level)
        result = analysis_executor.execute(
            analysis_plan=analysis_plan,
            entity_ids=[201, 202, 203],  # Filter to these ad group IDs
            entity_level="ad_group",     # Entity level is ad_group (different from series_level=campaign)
            advertiser_ids=["6"],
        )

        assert result.success is True

        # Verify that the entity filter was added to the DSL
        call_args = mock_es_client.search.call_args
        dsl = call_args[1]["body"]

        # Check that we have a terms filter for adgroup_id (entity_level = ad_group maps to adgroup_id)
        has_entity_filter = False
        for filter_cond in dsl["query"]["bool"]["filter"]:
            if isinstance(filter_cond, dict) and "terms" in filter_cond:
                if "adgroup_id" in filter_cond["terms"]:
                    assert set(filter_cond["terms"]["adgroup_id"]) == {201, 202, 203}
                    has_entity_filter = True

        assert has_entity_filter, "Multi-series trend should include entity filter even when series_level != entity_level"
