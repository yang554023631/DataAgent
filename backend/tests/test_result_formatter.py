"""结果格式化器测试"""
import pytest
from src.nl_dsl.result_formatter import ResultFormatter


class TestResultFormatter:
    def test_format_simple_hits(self):
        """格式化 _source 命中结果（列表查询）"""
        es_response = {
            "hits": {
                "total": {"value": 3, "relation": "eq"},
                "hits": [
                    {"_source": {"campaign_id": 101, "advertiser_id": 6}},
                    {"_source": {"campaign_id": 102, "advertiser_id": 6}},
                    {"_source": {"campaign_id": 103, "advertiser_id": 6}},
                ],
            }
        }
        result = ResultFormatter.format(es_response, display_type="list")
        assert result["display_type"] == "list"
        assert len(result["rows"]) == 3
        assert "campaign_id" in result["columns"]
        assert result["metadata"]["total_rows"] == 3

    def test_format_date_histogram(self):
        """格式化 date_histogram 聚合结果（趋势分析）"""
        es_response = {
            "aggregations": {
                "by_date": {
                    "buckets": [
                        {"key_as_string": "2026-01-01", "total_cost": {"value": 100}},
                        {"key_as_string": "2026-01-02", "total_cost": {"value": 200}},
                    ]
                }
            },
            "hits": {"total": {"value": 0}, "hits": []},
        }
        result = ResultFormatter.format(es_response, display_type="trend")
        assert result["display_type"] == "trend"
        assert len(result["rows"]) == 2
        assert "日期" in result["columns"] or "date" in result["columns"][0].lower()

    def test_format_terms_aggregation(self):
        """格式化 terms 聚合结果（对比/排名）"""
        es_response = {
            "aggregations": {
                "by_campaign": {
                    "buckets": [
                        {"key": 101, "doc_count": 10, "total_cost": {"value": 500}},
                        {"key": 102, "doc_count": 8, "total_cost": {"value": 300}},
                    ]
                }
            },
            "hits": {"total": {"value": 0}, "hits": []},
        }
        result = ResultFormatter.format(es_response, display_type="comparison")
        assert result["display_type"] == "comparison"
        assert len(result["rows"]) == 2

    def test_format_single_value_qa(self):
        """格式化单值结果（数值问答）"""
        es_response = {
            "aggregations": {
                "total_cost": {"value": 12345.67}
            },
            "hits": {"total": {"value": 0}, "hits": []},
        }
        result = ResultFormatter.format(es_response, display_type="qa")
        assert result["display_type"] == "qa"
        assert len(result["rows"]) >= 1

    def test_empty_result(self):
        """空结果处理"""
        es_response = {
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {},
        }
        result = ResultFormatter.format(es_response, display_type="list")
        assert result["metadata"]["total_rows"] == 0
        assert result["rows"] == []

    def test_auto_detect_display_type_hits(self):
        """自动检测呈现类型 - 命中列表 → list"""
        es_response = {
            "hits": {
                "total": {"value": 5},
                "hits": [{"_source": {"a": 1}} for _ in range(5)],
            }
        }
        result = ResultFormatter.format(es_response)
        assert result["display_type"] == "list"

    def test_auto_detect_date_histogram(self):
        """自动检测呈现类型 - date_histogram → trend"""
        es_response = {
            "aggregations": {
                "by_date": {
                    "buckets": [
                        {"key_as_string": "2026-01-01", "val": {"value": 100}},
                    ]
                }
            },
            "hits": {"total": {"value": 0}, "hits": []},
        }
        result = ResultFormatter.format(es_response)
        assert result["display_type"] == "trend"

    def test_auto_detect_terms_agg(self):
        """自动检测呈现类型 - terms 聚合 → comparison"""
        es_response = {
            "aggregations": {
                "by_entity": {
                    "buckets": [
                        {"key": "a", "val": {"value": 100}},
                        {"key": "b", "val": {"value": 200}},
                    ]
                }
            },
            "hits": {"total": {"value": 0}, "hits": []},
        }
        result = ResultFormatter.format(es_response)
        assert result["display_type"] == "comparison"
