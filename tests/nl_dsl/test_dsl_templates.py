import pytest
from typing import Optional, Dict, List, Any
from src.nl_dsl.dsl_templates.common import (
    LEVEL_TO_FIELD,
    DERIVED_METRICS,
    get_data_type,
    is_derived_metric,
    get_level_field,
    build_time_filter,
    build_bucket_script,
    build_bucket_selector,
    build_base_metric_sum_aggs,
    build_common_filters,
)
from src.nl_dsl.field_mapping import METRICS


class TestCommonHelpers:
    def test_get_data_type_basic(self):
        # Test known metrics from METRICS
        assert get_data_type("cost") == 3
        assert get_data_type("clicks") == 2
        assert get_data_type("impressions") == 1
        # Test unknown metric returns None
        assert get_data_type("unknown_metric") is None

    def test_get_level_field(self):
        assert get_level_field("advertiser") == "advertiser_id"
        assert get_level_field("campaign") == "campaign_id"
        assert get_level_field("ad_group") == "adgroup_id"
        assert get_level_field("creative") == "creative_id"

    def test_is_derived_metric(self):
        assert is_derived_metric("ctr") is True
        assert is_derived_metric("cost") is False
        assert is_derived_metric("cvr") is True
        assert is_derived_metric("cpc") is True
        assert is_derived_metric("cpm") is True
        # Test non-existent metric
        assert is_derived_metric("fake_metric") is False

    def test_build_time_filter(self):
        start_date = "2024-01-01"
        end_date = "2024-01-02"

        # Default field
        filter_dict = build_time_filter(start_date, end_date)
        expected_default = {
            "range": {
                "data_date": {
                    "gte": start_date,
                    "lte": end_date
                }
            }
        }
        assert filter_dict == expected_default

        # Custom date field
        custom_filter = build_time_filter(start_date, end_date, field="custom_date")
        assert "custom_date" in custom_filter["range"]
        assert custom_filter["range"]["custom_date"]["gte"] == start_date

    def test_build_bucket_selector(self):
        value_path = "count"
        operator = "gte"
        threshold = 10.0

        result = build_bucket_selector(value_path, operator, threshold)
        assert "having_filter" in result

        bucket_selector = result["having_filter"]["bucket_selector"]
        assert bucket_selector is not None
        assert "script" in bucket_selector
        assert "params.value" in bucket_selector["script"]
        assert f"params.value {operator} {threshold}" in bucket_selector["script"]
        assert bucket_selector["buckets_path"] == {"value": value_path}

    def test_build_common_filters(self):
        advertiser_ids = ["1", "2", "3"]
        start_date = "2024-01-01"
        end_date = "2024-01-02"
        data_types = [1, 2]

        # With data_types filter
        filters = build_common_filters(advertiser_ids, start_date, end_date, data_types)
        assert len(filters) == 3

        # Check advertiser ID terms filter
        assert filters[0] == {"terms": {"advertiser_id": advertiser_ids}}
        # Check date range filter
        assert "range" in filters[1]
        assert filters[1]["range"]["data_date"]["gte"] == start_date
        # Check data_types terms filter
        assert filters[2] == {"terms": {"data_type": data_types}}

        # Without data_types filter
        filters_no_dt = build_common_filters(advertiser_ids, start_date, end_date)
        assert len(filters_no_dt) == 2
        # Should not have data_type filter
        assert not any(f.get("terms", {}).get("data_type") for f in filters_no_dt)

    def test_derived_metrics_definition(self):
        expected_derived = {
            "ctr": {
                "depends_on": ["clicks", "impressions"],
                "unit": "%",
                "display_name_cn": "点击率"
            },
            "cvr": {
                "depends_on": ["conversions", "clicks"],
                "unit": "%",
                "display_name_cn": "转化率"
            },
            "cpc": {
                "depends_on": ["cost", "clicks"],
                "unit": "元",
                "display_name_cn": "单次点击成本"
            },
            "cpm": {
                "depends_on": ["cost", "impressions"],
                "unit": "元",
                "display_name_cn": "千次曝光成本"
            }
        }

        for metric, expected in expected_derived.items():
            assert metric in DERIVED_METRICS, f"Derived metric {metric} missing"
            actual = DERIVED_METRICS[metric]
            assert actual["depends_on"] == expected["depends_on"], f"Wrong depends_on for {metric}"
            assert actual["unit"] == expected["unit"], f"Wrong unit for {metric}"
            assert actual["display_name_cn"] == expected["display_name_cn"], f"Wrong display name for {metric}"

    def test_build_base_metric_sum_aggs(self):
        metrics = ["cost", "clicks"]
        aggs = build_base_metric_sum_aggs(metrics)

        # Check correct number of aggregations
        assert len(aggs) == 2
        assert "sum_cost" in aggs
        assert "sum_clicks" in aggs

        # Check cost aggregation structure
        cost_agg = aggs["sum_cost"]
        assert cost_agg["filter"] == {"term": {"data_type": 3}}
        assert "aggs" in cost_agg
        assert "value" in cost_agg["aggs"]
        assert cost_agg["aggs"]["value"]["sum"] == {"field": "data_value"}

        # Check clicks aggregation structure
        clicks_agg = aggs["sum_clicks"]
        assert clicks_agg["filter"] == {"term": {"data_type": 2}}
        assert "aggs" in clicks_agg
        assert "value" in clicks_agg["aggs"]
        assert clicks_agg["aggs"]["value"]["sum"] == {"field": "data_value"}

    def test_build_bucket_script(self):
        # Test CTR bucket script
        ctr_result = build_bucket_script("ctr")
        assert "ctr" in ctr_result

        ctr_bucket = ctr_result["ctr"]["bucket_script"]
        assert ctr_bucket["buckets_path"] == {
            "clicks": "sum_clicks>value",
            "impressions": "sum_impressions>value"
        }
        assert ctr_bucket["script"] == "params.clicks / params.impressions"

        # Test CPC bucket script
        cpc_result = build_bucket_script("cpc")
        assert "cpc" in cpc_result

        cpc_bucket = cpc_result["cpc"]["bucket_script"]
        assert cpc_bucket["buckets_path"] == {
            "cost": "sum_cost>value",
            "clicks": "sum_clicks>value"
        }
        assert cpc_bucket["script"] == "params.cost / params.clicks"

        # Test CPM bucket script
        cpm_result = build_bucket_script("cpm")
        assert "cpm" in cpm_result

        cpm_bucket = cpm_result["cpm"]["bucket_script"]
        assert cpm_bucket["buckets_path"] == {
            "cost": "sum_cost>value",
            "impressions": "sum_impressions>value"
        }
        assert cpm_bucket["script"] == "params.cost / params.impressions * 1000"


class TestFilterTemplates:
    def test_having_filter_basic(self):
        from src.nl_dsl.dsl_templates.filter_templates import build_having_filter
        dsl = build_having_filter(
            advertiser_ids=["6"],
            start_date="2026-04-01",
            end_date="2026-04-30",
            metric="cost",
            operator=">",
            threshold=10,
            group_by_level="campaign",
        )
        # 结构校验
        assert "index" in dsl
        assert dsl["index"] == "ad_stat_data"
        assert "query" in dsl
        assert "bool" in dsl["query"]
        assert "filter" in dsl["query"]["bool"]
        assert dsl["size"] == 0
        assert "by_campaign" in dsl["aggs"]
        assert dsl["aggs"]["by_campaign"]["terms"]["field"] == "campaign_id"
        assert "metric_sum" in dsl["aggs"]["by_campaign"]["aggs"]
        assert "having_filter" in dsl["aggs"]["by_campaign"]["aggs"]
        # 广告主过滤
        filters = dsl["query"]["bool"]["filter"]
        assert any("advertiser_id" in str(f) for f in filters)
        # data_type 过滤
        assert any("data_type" in str(f) for f in filters)

    def test_having_filter_invalid_operator(self):
        from src.nl_dsl.dsl_templates.filter_templates import build_having_filter
        import pytest
        with pytest.raises(ValueError, match="Invalid operator"):
            build_having_filter(
                advertiser_ids=["6"],
                start_date="2026-04-01",
                end_date="2026-04-30",
                metric="cost",
                operator="invalid",
                threshold=10,
                group_by_level="campaign",
            )

    def test_derived_having_filter(self):
        from src.nl_dsl.dsl_templates.filter_templates import build_derived_having_filter
        dsl = build_derived_having_filter(
            advertiser_ids=["6"],
            start_date="2026-04-01",
            end_date="2026-04-30",
            metric="ctr",
            operator=">",
            threshold=0.05,
            group_by_level="campaign",
        )
        assert "index" in dsl
        assert dsl["index"] == "ad_stat_data"
        aggs = dsl["aggs"]["by_campaign"]["aggs"]
        assert "sum_clicks" in aggs
        assert "sum_impressions" in aggs
        assert "ctr" in aggs
        assert "bucket_script" in aggs["ctr"]
        assert "having_filter" in aggs

    def test_derived_having_filter_invalid_operator(self):
        from src.nl_dsl.dsl_templates.filter_templates import build_derived_having_filter
        import pytest
        with pytest.raises(ValueError, match="Invalid operator"):
            build_derived_having_filter(
                advertiser_ids=["6"],
                start_date="2026-04-01",
                end_date="2026-04-30",
                metric="ctr",
                operator="invalid",
                threshold=0.05,
                group_by_level="campaign",
            )

    def test_where_dimension_filter(self):
        from src.nl_dsl.dsl_templates.filter_templates import build_where_dimension_filter
        dsl = build_where_dimension_filter(
            advertiser_ids=["6"],
            level="campaign",
            conditions=[
                {"field": "status", "operator": "=", "value": "enabled"},
                {"field": "create_time", "operator": ">=", "value": "2026-01-01"},
            ],
        )
        assert "index" in dsl
        assert dsl["index"] == "campaign"
        assert dsl["size"] == 0
        assert "by_campaign" in dsl["aggs"]
        filters = dsl["query"]["bool"]["filter"]
        assert len(filters) >= 2  # advertiser + conditions

    def test_where_dimension_filter_invalid_operator(self):
        from src.nl_dsl.dsl_templates.filter_templates import build_where_dimension_filter
        import pytest
        with pytest.raises(ValueError, match="Invalid operator"):
            build_where_dimension_filter(
                advertiser_ids=["6"],
                level="campaign",
                conditions=[
                    {"field": "status", "operator": "invalid", "value": "enabled"},
                ],
            )

    def test_cross_level_up_filter(self):
        from src.nl_dsl.dsl_templates.filter_templates import build_cross_level_up_filter
        dsl = build_cross_level_up_filter(
            advertiser_ids=["6"],
            low_level="creative",
            low_level_field="creative_name",
            low_level_value="618",
            low_level_operator="contains",
            target_level="campaign",
            index="creative",
        )
        assert "index" in dsl
        assert dsl["index"] == "creative"
        assert "match" in str(dsl["query"]["bool"]["filter"])
        assert "by_campaign" in dsl["aggs"]
        assert dsl["aggs"]["by_campaign"]["terms"]["field"] == "campaign_id"

    def test_cross_level_down_filter_two_step(self):
        from src.nl_dsl.dsl_templates.filter_templates import build_cross_level_down_filter_step1
        dsl = build_cross_level_down_filter_step1(
            advertiser_ids=["6"],
            high_level="campaign",
            conditions=[{"field": "campaign_name", "operator": "contains", "value": "618"}],
        )
        assert "index" in dsl
        assert dsl["index"] == "campaign"
        assert "by_campaign" in dsl["aggs"]

    def test_full_filter(self):
        from src.nl_dsl.dsl_templates.filter_templates import build_full_filter
        result = build_full_filter(
            advertiser_ids=["6"],
            level="campaign",
        )
        # 全量筛选返回 None 或空步骤（不需要查询，用 advertiser_id + level 直接过滤即可）
        assert result is None or result["steps"] == []


class TestAnalysisTemplates:
    def test_single_series_trend(self):
        from src.nl_dsl.dsl_templates.analysis_templates import build_single_series_trend
        dsl = build_single_series_trend(
            advertiser_ids=["6"],
            start_date="2026-04-01",
            end_date="2026-04-30",
            metric="cost",
            granularity="day",
        )
        assert "by_date" in dsl["aggs"]
        assert "date_histogram" in dsl["aggs"]["by_date"]
        assert "metric_sum" in dsl["aggs"]["by_date"]["aggs"]
        assert dsl["size"] == 0

    def test_multi_series_trend(self):
        from src.nl_dsl.dsl_templates.analysis_templates import build_multi_series_trend
        dsl = build_multi_series_trend(
            advertiser_ids=["6"],
            start_date="2026-04-01",
            end_date="2026-04-30",
            metric="cost",
            series_level="campaign",
            series_ids=[101, 102, 103],
            granularity="day",
        )
        assert "by_date" in dsl["aggs"]
        assert "by_campaign" in dsl["aggs"]["by_date"]["aggs"]
        assert "metric_sum" in dsl["aggs"]["by_date"]["aggs"]["by_campaign"]["aggs"]

    def test_entity_table(self):
        from src.nl_dsl.dsl_templates.analysis_templates import build_entity_table
        dsl = build_entity_table(
            advertiser_ids=["6"],
            start_date="2026-04-01",
            end_date="2026-04-30",
            metrics=["cost", "clicks", "ctr"],
            group_by_level="campaign",
            order_by="cost",
            order_dir="desc",
            limit=20,
        )
        aggs = dsl["aggs"]["by_campaign"]["aggs"]
        assert "sum_cost" in aggs
        assert "sum_clicks" in aggs
        assert "ctr" in aggs  # 衍生指标

    def test_period_comparison(self):
        from src.nl_dsl.dsl_templates.analysis_templates import build_period_comparison_summary
        dsl = build_period_comparison_summary(
            advertiser_ids=["6"],
            current_start="2026-04-01",
            current_end="2026-04-30",
            compare_start="2026-03-01",
            compare_end="2026-03-31",
            metrics=["cost", "clicks"],
        )
        assert "current_period" in dsl["aggs"]
        assert "compare_period" in dsl["aggs"]
        assert "filter" in dsl["aggs"]["current_period"]

    def test_audience_distribution(self):
        from src.nl_dsl.dsl_templates.analysis_templates import build_audience_distribution
        dsl = build_audience_distribution(
            advertiser_ids=["6"],
            start_date="2026-04-01",
            end_date="2026-04-30",
            metric="cost",
            audience_type="gender",
        )
        assert "by_audience" in dsl["aggs"]
        filters = dsl["query"]["bool"]["filter"]
        assert any("audience_type" in str(f) for f in filters)

    def test_summary(self):
        from src.nl_dsl.dsl_templates.analysis_templates import build_summary
        dsl = build_summary(
            advertiser_ids=["6"],
            start_date="2026-04-01",
            end_date="2026-04-30",
            metrics=["cost", "clicks", "impressions", "ctr"],
        )
        assert "sum_cost" in dsl["aggs"]
        assert "sum_clicks" in dsl["aggs"]
        assert "ctr" in dsl["aggs"]  # 衍生指标

    def test_detail_list(self):
        from src.nl_dsl.dsl_templates.analysis_templates import build_detail_list
        dsl = build_detail_list(
            advertiser_ids=["6"],
            start_date="2026-04-01",
            end_date="2026-04-30",
            metric="cost",
            value_operator=">",
            value_threshold=100,
            page=1,
            page_size=20,
        )
        assert dsl["from"] == 0
        assert dsl["size"] == 20
        assert "sort" in dsl
        assert "data_value" in str(dsl["query"])
