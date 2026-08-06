"""DSL 安全校验器测试"""
import pytest
from src.nl_dsl.dsl_validator import DslValidator, ValidationResult


class TestDslValidator:
    def test_valid_simple_query_passes(self):
        """合法的简单查询应该通过"""
        validator = DslValidator(allowed_indices={"ad_stat_data"})
        dsl = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"advertiser_id": 6}},
                        {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
                        {"term": {"data_type": 3}},
                    ]
                }
            },
            "size": 10,
        }
        result = validator.validate(dsl, "ad_stat_data")
        assert result.ok is True
        assert result.errors == []

    def test_missing_advertiser_filter_fails(self):
        """缺少 advertiser_id 过滤应该失败"""
        validator = DslValidator(allowed_indices={"ad_stat_data"})
        dsl = {
            "query": {
                "bool": {
                    "must": [
                        {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
                    ]
                }
            },
            "size": 10,
        }
        result = validator.validate(dsl, "ad_stat_data")
        assert result.ok is False
        assert any("advertiser_id" in e for e in result.errors)

    def test_missing_date_filter_fails(self):
        """缺少时间范围过滤应该失败"""
        validator = DslValidator(allowed_indices={"ad_stat_data"})
        dsl = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"advertiser_id": 6}},
                    ]
                }
            },
            "size": 10,
        }
        result = validator.validate(dsl, "ad_stat_data")
        assert result.ok is False
        assert any("时间" in e or "date" in e.lower() for e in result.errors)

    def test_index_not_in_whitelist_fails(self):
        """索引不在白名单中应该失败"""
        validator = DslValidator(allowed_indices={"ad_stat_data"})
        dsl = {
            "query": {"bool": {"must": [
                {"term": {"advertiser_id": 6}},
                {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
            ]}},
            "size": 10,
        }
        result = validator.validate(dsl, "unknown_index")
        assert result.ok is False
        assert any("白名单" in e or "whitelist" in e.lower() for e in result.errors)

    def test_script_field_fails(self):
        """包含 script_fields 应该失败"""
        validator = DslValidator(allowed_indices={"ad_stat_data"})
        dsl = {
            "query": {"bool": {"must": [
                {"term": {"advertiser_id": 6}},
                {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
            ]}},
            "script_fields": {"calc": {"script": {"source": "doc['data_value'].value * 2"}}},
            "size": 10,
        }
        result = validator.validate(dsl, "ad_stat_data")
        assert result.ok is False
        assert any("script" in e.lower() for e in result.errors)

    def test_size_exceeds_limit_gets_warning(self):
        """size 超过上限应该有警告（自动截断）"""
        validator = DslValidator(allowed_indices={"ad_stat_data"}, max_size=1000)
        dsl = {
            "query": {"bool": {"must": [
                {"term": {"advertiser_id": 6}},
                {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
            ]}},
            "size": 5000,
        }
        result = validator.validate(dsl, "ad_stat_data")
        # size超限是warning不是error（校验器只报告，执行器会截断）
        assert any("size" in w.lower() for w in result.warnings)

    def test_invalid_json_fails(self):
        """非 dict 结构应该失败"""
        validator = DslValidator(allowed_indices={"ad_stat_data"})
        result = validator.validate("not a dict", "ad_stat_data")
        assert result.ok is False

    def test_nested_agg_size_check(self):
        """聚合 size 超限应该有警告"""
        validator = DslValidator(allowed_indices={"ad_stat_data"}, max_agg_size=500)
        dsl = {
            "query": {"bool": {"must": [
                {"term": {"advertiser_id": 6}},
                {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
            ]}},
            "aggs": {
                "by_campaign": {
                    "terms": {"field": "campaign_id", "size": 2000},
                    "aggs": {"total": {"sum": {"field": "data_value"}}},
                }
            },
            "size": 0,
        }
        result = validator.validate(dsl, "ad_stat_data")
        assert any("agg" in w.lower() or "size" in w.lower() for w in result.warnings)