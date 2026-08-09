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
        advertiser_ids = [1, 2, 3]
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
