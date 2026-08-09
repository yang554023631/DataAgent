import pytest
from typing import Dict, Any, List
from src.nl_dsl.dsl_templates.result_extractors import (
    extract_entity_ids,
    extract_trend_data,
    extract_entity_table_data,
    extract_summary_data,
    extract_comparison_data,
    extract_audience_data,
    extract_detail_data
)


class TestResultExtractors:
    # Mock ES response data
    @pytest.fixture
    def mock_entity_buckets_response(self) -> Dict[str, Any]:
        """Mock response with terms buckets for entities"""
        return {
            "aggregations": {
                "by_campaign": {
                    "buckets": [
                        {"key": 101, "doc_count": 5},
                        {"key": 102, "doc_count": 3},
                        {"key": 103, "doc_count": 2}
                    ]
                }
            }
        }

    @pytest.fixture
    def mock_single_series_trend_response(self) -> Dict[str, Any]:
        """Mock single series trend response"""
        return {
            "aggregations": {
                "by_date": {
                    "buckets": [
                        {
                            "key": "2026-04-01",
                            "sum_cost": {"value": 100.0},
                            "sum_clicks": {"value": 50}
                        },
                        {
                            "key": "2026-04-02",
                            "sum_cost": {"value": 200.0},
                            "sum_clicks": {"value": 100}
                        }
                    ]
                }
            }
        }

    @pytest.fixture
    def mock_multi_series_trend_response(self) -> Dict[str, Any]:
        """Mock multi-series trend response"""
        return {
            "aggregations": {
                "by_date": {
                    "buckets": [
                        {
                            "key": "2026-04-01",
                            "by_campaign": {
                                "buckets": [
                                    {"key": 101, "sum_cost": {"value": 50.0}},
                                    {"key": 102, "sum_cost": {"value": 50.0}}
                                ]
                            }
                        },
                        {
                            "key": "2026-04-02",
                            "by_campaign": {
                                "buckets": [
                                    {"key": 101, "sum_cost": {"value": 100.0}},
                                    {"key": 102, "sum_cost": {"value": 100.0}}
                                ]
                            }
                        }
                    ]
                }
            }
        }

    @pytest.fixture
    def mock_entity_table_response(self) -> Dict[str, Any]:
        """Mock entity table response"""
        return {
            "aggregations": {
                "by_campaign": {
                    "buckets": [
                        {
                            "key": 101,
                            "sum_cost": {"value": 100.0},
                            "sum_clicks": {"value": 50},
                            "ctr": {"value": 0.10}
                        },
                        {
                            "key": 102,
                            "sum_cost": {"value": 200.0},
                            "sum_clicks": {"value": 100},
                            "ctr": {"value": 0.05}
                        }
                    ]
                }
            }
        }

    @pytest.fixture
    def mock_summary_response(self) -> Dict[str, Any]:
        """Mock summary metric response"""
        return {
            "aggregations": {
                "sum_cost": {"value": 1000.0},
                "sum_clicks": {"value": 500},
                "ctr": {"value": 0.08}
            }
        }

    @pytest.fixture
    def mock_comparison_response(self) -> Dict[str, Any]:
        """Mock period comparison response"""
        return {
            "aggregations": {
                "current_period": {
                    "sum_cost": {"value": 1000.0},
                    "sum_clicks": {"value": 500}
                },
                "compare_period": {
                    "sum_cost": {"value": 800.0},
                    "sum_clicks": {"value": 400}
                }
            }
        }

    @pytest.fixture
    def mock_audience_response(self) -> Dict[str, Any]:
        """Mock audience distribution response"""
        return {
            "aggregations": {
                "by_audience": {
                    "buckets": [
                        {"key": "male", "metric_sum": {"value": 600.0}},
                        {"key": "female", "metric_sum": {"value": 400.0}}
                    ]
                }
            }
        }

    @pytest.fixture
    def mock_detail_response(self) -> Dict[str, Any]:
        """Mock detail list response"""
        return {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "advertiser_id": "6",
                            "campaign_id": 101,
                            "data_date": "2026-04-01",
                            "data_value": 50.0,
                            "data_type": 3
                        }
                    },
                    {
                        "_source": {
                            "advertiser_id": "6",
                            "campaign_id": 102,
                            "data_date": "2026-04-01",
                            "data_value": 100.0,
                            "data_type": 3
                        }
                    }
                ]
            }
        }

    def test_extract_entity_ids(self, mock_entity_buckets_response):
        entity_ids = extract_entity_ids(mock_entity_buckets_response, "by_campaign")
        assert entity_ids == [101, 102, 103]

    def test_extract_entity_ids_invalid_path(self, mock_entity_buckets_response):
        entity_ids = extract_entity_ids(mock_entity_buckets_response, "invalid_path")
        assert entity_ids == []

    def test_extract_single_series_trend(self, mock_single_series_trend_response):
        trend_data = extract_trend_data(mock_single_series_trend_response)
        assert len(trend_data) == 2
        assert trend_data["2026-04-01"] == 100.0
        assert trend_data["2026-04-02"] == 200.0

    def test_extract_multi_series_trend(self, mock_multi_series_trend_response):
        trend_data = extract_trend_data(mock_multi_series_trend_response, series_level="campaign")
        assert len(trend_data) == 2
        assert trend_data["2026-04-01"] == {101: 50.0, 102: 50.0}
        assert trend_data["2026-04-02"] == {101: 100.0, 102: 100.0}

    def test_extract_entity_table_data(self, mock_entity_table_response):
        table_data = extract_entity_table_data(mock_entity_table_response, "campaign")
        assert len(table_data) == 2
        assert table_data[101]["cost"] == 100.0
        assert table_data[101]["clicks"] == 50
        assert table_data[101]["ctr"] == 0.10
        assert table_data[102]["cost"] == 200.0
        assert table_data[102]["ctr"] == 0.05

    def test_extract_summary_data(self, mock_summary_response):
        summary_data = extract_summary_data(mock_summary_response, ["cost", "clicks", "ctr"])
        assert summary_data["cost"] == 1000.0
        assert summary_data["clicks"] == 500
        assert summary_data["ctr"] == 0.08

    def test_extract_comparison_data(self, mock_comparison_response):
        comparison_data = extract_comparison_data(mock_comparison_response, ["cost", "clicks"])
        assert comparison_data["current_period"]["cost"] == 1000.0
        assert comparison_data["current_period"]["clicks"] == 500
        assert comparison_data["compare_period"]["cost"] == 800.0
        assert comparison_data["compare_period"]["clicks"] == 400

    def test_extract_audience_data(self, mock_audience_response):
        audience_data = extract_audience_data(mock_audience_response)
        assert audience_data["male"] == 600.0
        assert audience_data["female"] == 400.0

    def test_extract_detail_data_all_fields(self, mock_detail_response):
        details = extract_detail_data(mock_detail_response)
        assert len(details) == 2
        assert details[0]["advertiser_id"] == "6"
        assert details[0]["campaign_id"] == 101

    def test_extract_detail_data_selected_fields(self, mock_detail_response):
        details = extract_detail_data(mock_detail_response, source_fields=["data_date", "data_value"])
        assert len(details) == 2
        assert "advertiser_id" not in details[0]
        assert details[0]["data_date"] == "2026-04-01"
        assert details[0]["data_value"] == 50.0