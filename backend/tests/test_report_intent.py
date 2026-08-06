import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.intent.report_intent import ReportIntentAnalyzer
from src.intent.models import ReportIntentResult, ReportTimeRange


def _make_mock_client(response_dict: dict):
    mock = MagicMock()
    mock.call = AsyncMock(return_value=json.dumps(response_dict))
    return mock


class TestLLMExtraction:
    """LLM 提取测试（mock LLM）"""

    @pytest.mark.asyncio
    async def test_full_extraction(self):
        """完整提取所有字段"""
        mock_client = _make_mock_client({
            "advertiser_ids": ["123"],
            "time_range": {
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
                "unit": "day",
                "is_lifetime": False
            },
            "metrics": ["impressions", "clicks", "cost"],
            "ad_level": "campaign",
            "group_by": ["data_date"],
            "filters": [],
            "is_comparison": False,
            "compare_time_range": None,
            "top_n": None,
            "chart_type": None,
            "confidence": 0.95,
            "alias_mappings": {"曝光": "impressions", "点击": "clicks"}
        })
        analyzer = ReportIntentAnalyzer(llm_client=mock_client)
        result = await analyzer._llm_extract("上个月的曝光点击消耗，按天展示")
        assert isinstance(result, ReportIntentResult)
        assert result.metrics == ["impressions", "clicks", "cost"]
        assert result.ad_level == "campaign"
        assert result.time_range.start_date == "2026-07-01"
        assert "曝光" in result.alias_mappings

    @pytest.mark.asyncio
    async def test_empty_fields(self):
        """用户没说的字段留空"""
        mock_client = _make_mock_client({
            "advertiser_ids": [],
            "time_range": None,
            "metrics": [],
            "ad_level": None,
            "group_by": [],
            "filters": [],
            "is_comparison": False,
            "compare_time_range": None,
            "top_n": None,
            "chart_type": None,
            "confidence": 0.4,
            "alias_mappings": {}
        })
        analyzer = ReportIntentAnalyzer(llm_client=mock_client)
        result = await analyzer._llm_extract("帮我看看数据")
        assert result.advertiser_ids == []
        assert result.time_range is None
        assert result.metrics == []
        assert result.ad_level is None


class TestRequiredFieldsCheck:
    """必填字段检查测试"""

    def setup_method(self):
        self.analyzer = ReportIntentAnalyzer(llm_client=None)

    def test_all_present(self):
        """所有必填字段都有 → 不需要澄清"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions"],
            ad_level="campaign",
        )
        ok, clarification = self.analyzer.check_required_fields(result)
        assert ok is True
        assert clarification is None

    def test_missing_advertiser(self):
        """缺广告主 → 触发澄清"""
        result = ReportIntentResult(
            advertiser_ids=[],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions"],
            ad_level="campaign",
        )
        ok, clarification = self.analyzer.check_required_fields(result)
        assert ok is False
        assert clarification.type == "missing_advertiser"
        assert "广告主" in clarification.question

    def test_missing_time_range(self):
        """缺时间 → 触发澄清"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=None,
            metrics=["impressions"],
            ad_level="campaign",
        )
        ok, clarification = self.analyzer.check_required_fields(result)
        assert ok is False
        assert clarification.type == "missing_time_range"

    def test_missing_metrics(self):
        """缺指标 → 触发澄清"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=[],
            ad_level="campaign",
        )
        ok, clarification = self.analyzer.check_required_fields(result)
        assert ok is False
        assert clarification.type == "missing_metrics"
        # 选项里应该有指标名称
        assert len(clarification.options) > 0

    def test_missing_ad_level(self):
        """缺广告层级 → 默认使用 campaign，不触发澄清"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions"],
            ad_level=None,
        )
        ok, clarification = self.analyzer.check_required_fields(result)
        assert ok is True
        assert clarification is None
        assert result.ad_level == "campaign"  # 默认设置为 campaign

    def test_multiple_missing(self):
        """多个字段缺失 → 选第一个最关键的发起澄清"""
        result = ReportIntentResult(
            advertiser_ids=[],
            time_range=None,
            metrics=[],
            ad_level=None,
        )
        ok, clarification = self.analyzer.check_required_fields(result)
        assert ok is False
        # 应该返回第一个缺失项的澄清
        assert clarification is not None


class TestCapabilityCheck:
    """能力校验测试"""

    def setup_method(self):
        self.analyzer = ReportIntentAnalyzer(llm_client=None)

    def test_all_supported(self):
        """全部支持 → 通过"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions", "clicks", "ctr"],
            ad_level="campaign",
            group_by=["data_date", "audience_gender"],
        )
        ok, clarification = self.analyzer.check_capabilities(result)
        assert ok is True
        assert clarification is None

    def test_unsupported_metric(self):
        """不支持的指标 → 触发澄清"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions", "留存率"],
            ad_level="campaign",
        )
        ok, clarification = self.analyzer.check_capabilities(result)
        assert ok is False
        assert clarification.type == "unsupported_metric"
        assert "留存率" in clarification.question

    def test_unsupported_dimension(self):
        """不支持的维度 → 触发澄清"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions"],
            ad_level="campaign",
            group_by=["血型"],
        )
        ok, clarification = self.analyzer.check_capabilities(result)
        assert ok is False
        assert clarification.type == "unsupported_dimension"


class TestContextInheritance:
    """上下文继承测试"""

    def setup_method(self):
        self.analyzer = ReportIntentAnalyzer(llm_client=None)

    def test_inherit_advertiser(self):
        """新输入没广告主但上下文有 → 继承"""
        result = ReportIntentResult(
            advertiser_ids=[],  # LLM 没提取到
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions"],
            ad_level="campaign",
        )
        self.analyzer._apply_context_inheritance(result, existing_advertiser_ids=["456"])
        assert result.advertiser_ids == ["456"]

    def test_dont_override_new_advertiser(self):
        """新输入有广告主 → 不用继承"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions"],
            ad_level="campaign",
        )
        self.analyzer._apply_context_inheritance(result, existing_advertiser_ids=["456"])
        assert result.advertiser_ids == ["123"]


class TestFullAnalyze:
    """完整 analyze 流程测试"""

    @pytest.mark.asyncio
    async def test_successful_analysis(self):
        """信息齐全 → 返回 (result, None, None, route_info)"""
        mock_client = _make_mock_client({
            "advertiser_ids": ["123"],
            "time_range": {
                "start_date": "2026-07-01", "end_date": "2026-07-31",
                "unit": "day", "is_lifetime": False
            },
            "metrics": ["impressions", "clicks"],
            "ad_level": "campaign",
            "group_by": [], "filters": [],
            "is_comparison": False, "compare_time_range": None,
            "top_n": None, "chart_type": None,
            "confidence": 0.9,
            "alias_mappings": {}
        })
        analyzer = ReportIntentAnalyzer(llm_client=mock_client)
        result, clarification, final_report, route_info = await analyzer.analyze(
            "查看广告主123上个月的曝光点击"
        )
        assert result is not None
        assert clarification is None
        assert final_report is None
        assert route_info is not None
        assert len(result.metrics) == 2

    @pytest.mark.asyncio
    async def test_analysis_with_clarification(self):
        """缺字段 → 返回 (result, clarification, None, None)"""
        mock_client = _make_mock_client({
            "advertiser_ids": [],
            "time_range": {
                "start_date": "2026-07-01", "end_date": "2026-07-31",
                "unit": "day", "is_lifetime": False
            },
            "metrics": ["impressions"],
            "ad_level": "campaign",
            "group_by": [], "filters": [],
            "is_comparison": False, "compare_time_range": None,
            "top_n": None, "chart_type": None,
            "confidence": 0.8,
            "alias_mappings": {}
        })
        analyzer = ReportIntentAnalyzer(llm_client=mock_client)
        result, clarification, final_report, route_info = await analyzer.analyze(
            "上个月的曝光数据"
        )
        assert result is not None
        assert clarification is not None
        assert final_report is None
        assert route_info is None
        assert clarification.type == "missing_advertiser"


class TestQueryRouting:
    """路由判断测试"""

    def setup_method(self):
        self.analyzer = ReportIntentAnalyzer(llm_client=None)

    def test_structured_route_default(self):
        """标准查询 → structured 路由"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(start_date="2026-07-01", end_date="2026-07-31"),
            metrics=["impressions", "clicks"],
            ad_level="campaign",
            group_by=["data_date"],
            filters=[],
        )
        route, reason, analysis_type = self.analyzer._determine_query_route(
            result, "查看广告主123上个月的曝光和点击按天统计"
        )
        assert route == "structured"
        assert analysis_type == "standard_report"

    def test_nl_dsl_route_keyword_list(self):
        """关键词 '列表' → nl_dsl 路由"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(start_date="2026-07-01", end_date="2026-07-31"),
            metrics=["impressions"],
            ad_level="campaign",
        )
        route, reason, analysis_type = self.analyzer._determine_query_route(
            result, "有哪些广告计划"
        )
        assert route == "nl_dsl"
        assert "命中关键词" in reason
        assert analysis_type == "exploratory_query"

    def test_nl_dsl_route_keyword_top(self):
        """关键词 'top' → nl_dsl 路由"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(start_date="2026-07-01", end_date="2026-07-31"),
            metrics=["impressions"],
            ad_level="campaign",
        )
        route, reason, analysis_type = self.analyzer._determine_query_route(
            result, "top 10 曝光最高的广告"
        )
        assert route == "nl_dsl"
        assert "命中关键词" in reason

    def test_nl_dsl_route_keyword_greater(self):
        """关键词 '大于' → nl_dsl 路由"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(start_date="2026-07-01", end_date="2026-07-31"),
            metrics=["impressions"],
            ad_level="campaign",
        )
        route, reason, analysis_type = self.analyzer._determine_query_route(
            result, "曝光大于 10000 的广告"
        )
        assert route == "nl_dsl"

    def test_nl_dsl_route_many_filters(self):
        """过滤条件较多（>3） → nl_dsl 路由"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(start_date="2026-07-01", end_date="2026-07-31"),
            metrics=["impressions"],
            ad_level="campaign",
            filters=[{"field": "a"}, {"field": "b"}, {"field": "c"}, {"field": "d"}],
        )
        route, reason, analysis_type = self.analyzer._determine_query_route(
            result, "复杂条件查询"
        )
        assert route == "nl_dsl"
        assert "过滤条件较多" in reason

    @pytest.mark.asyncio
    async def test_analyze_with_route_info(self):
        """完整 analyze 流程应该返回 route_info"""
        mock_client = _make_mock_client({
            "advertiser_ids": ["123"],
            "time_range": {
                "start_date": "2026-07-01", "end_date": "2026-07-31",
                "unit": "day", "is_lifetime": False
            },
            "metrics": ["impressions", "clicks"],
            "ad_level": "campaign",
            "group_by": [], "filters": [],
            "is_comparison": False, "compare_time_range": None,
            "top_n": None, "chart_type": None,
            "confidence": 0.9,
            "alias_mappings": {}
        })
        analyzer = ReportIntentAnalyzer(llm_client=mock_client)
        result, clarification, final_report, route_info = await analyzer.analyze(
            "查看广告主123上个月的曝光点击"
        )
        assert result is not None
        assert clarification is None
        assert final_report is None
        assert route_info is not None
        assert "route" in route_info
        assert "reason" in route_info
        assert "analysis_type" in route_info
