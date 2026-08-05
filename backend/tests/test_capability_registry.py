import pytest
from src.intent.capability_registry import (
    validate_metric,
    validate_ad_level,
    validate_dimension,
    get_all_metric_names,
    get_all_dimension_names,
    get_metric_aliases,
    SUPPORTED_AD_LEVELS,
)


class TestValidateMetric:
    def test_standard_name(self):
        ok, std = validate_metric("impressions")
        assert ok is True
        assert std == "impressions"

    def test_chinese_alias(self):
        ok, std = validate_metric("曝光")
        assert ok is True
        assert std == "impressions"

    def test_ctr_case_insensitive(self):
        ok, std = validate_metric("CTR")
        assert ok is True
        assert std == "ctr"

    def test_unsupported(self):
        ok, std = validate_metric("留存率")
        assert ok is False
        assert std is None

    def test_empty(self):
        ok, std = validate_metric("")
        assert ok is False
        assert std is None


class TestValidateAdLevel:
    @pytest.mark.parametrize("name,expected", [
        ("campaign", (True, "campaign")),
        ("计划", (True, "campaign")),
        ("ad_group", (True, "ad_group")),
        ("广告组", (True, "ad_group")),
        ("creative", (True, "creative")),
        ("素材", (True, "creative")),
        ("创意", (True, "creative")),
        ("账户", (False, None)),
    ])
    def test_ad_level_validation(self, name, expected):
        ok, std = validate_ad_level(name)
        assert (ok, std) == expected


class TestValidateDimension:
    def test_time_dimension(self):
        ok, std = validate_dimension("日期")
        assert ok is True
        assert std == "data_date"

    def test_audience_dimension(self):
        ok, std = validate_dimension("性别")
        assert ok is True
        assert std == "audience_gender"

    def test_business_dimension(self):
        ok, std = validate_dimension("渠道")
        assert ok is True
        assert std == "campaign_id"

    def test_unsupported_dimension(self):
        ok, std = validate_dimension("血型")
        assert ok is False
        assert std is None


class TestLists:
    def test_get_all_metric_names(self):
        names = get_all_metric_names()
        assert "曝光" in names
        assert "点击" in names
        assert "消耗" in names
        assert len(names) >= 9

    def test_get_all_dimension_names(self):
        names = get_all_dimension_names()
        assert "日期" in names
        assert "性别" in names
        assert len(names) >= 10

    def test_get_metric_aliases(self):
        aliases = get_metric_aliases()
        assert "曝光" in aliases
        assert aliases["曝光"] == "impressions"
        assert "ctr" in aliases
        assert aliases["ctr"] == "ctr"

    def test_supported_ad_levels(self):
        assert "campaign" in SUPPORTED_AD_LEVELS
        assert "ad_group" in SUPPORTED_AD_LEVELS
        assert "creative" in SUPPORTED_AD_LEVELS
        assert len(SUPPORTED_AD_LEVELS) == 3