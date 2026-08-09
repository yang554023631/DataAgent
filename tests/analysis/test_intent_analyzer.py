"""
IntentAnalyzer 测试文件

测试轻量级字段提取和场景识别功能。
"""
import pytest
from datetime import date, timedelta
from src.analysis.intent_analyzer import IntentAnalyzer, IntentAnalysisResult
from src.analysis.models import FieldContext, AnalysisType, FilterType


class TestIntentAnalyzer:
    """IntentAnalyzer 测试类"""

    @pytest.fixture
    def analyzer(self):
        """创建 IntentAnalyzer 实例"""
        return IntentAnalyzer()

    @pytest.fixture
    def today(self):
        """获取今天的日期"""
        return date.today()

    @pytest.fixture
    def yesterday(self, today):
        """获取昨天的日期"""
        return today - timedelta(days=1)

    def test_analyze_basic_query(self, analyzer, today):
        """测试基本查询的字段提取"""
        user_input = "昨天的曝光点击消耗"

        result = analyzer.analyze(user_input)

        assert isinstance(result, IntentAnalysisResult)
        assert isinstance(result.field_context, FieldContext)

        # 检查时间范围
        assert result.field_context.time_range is not None
        assert result.field_context.time_range.start_date == str(today - timedelta(days=1))
        assert result.field_context.time_range.end_date == str(today - timedelta(days=1))

        # 检查指标
        assert result.field_context.metrics is not None
        assert "impressions" in result.field_context.metrics
        assert "clicks" in result.field_context.metrics
        assert "cost" in result.field_context.metrics

        # 检查场景识别
        assert result.analysis_type_hint == AnalysisType.TIME_TREND or result.analysis_type_hint == AnalysisType.SUMMARY

    def test_analyze_time_trend_query(self, analyzer):
        """测试时间趋势查询的场景识别"""
        user_input = "近7天的曝光变化趋势"

        result = analyzer.analyze(user_input)

        assert result.analysis_type_hint == AnalysisType.TIME_TREND
        assert "impressions" in result.field_context.metrics

    def test_analyze_comparison_query(self, analyzer):
        """测试对比查询的场景识别"""
        user_input = "本周和上周的消耗对比"

        result = analyzer.analyze(user_input)

        assert result.analysis_type_hint == AnalysisType.PERIOD_COMPARISON
        assert "cost" in result.field_context.metrics

    def test_analyze_distribution_query(self, analyzer):
        """测试分布查询的场景识别"""
        user_input = "按性别看的曝光分布"

        result = analyzer.analyze(user_input)

        assert result.analysis_type_hint == AnalysisType.AUDIENCE_DISTRIBUTION
        assert "impressions" in result.field_context.metrics
        assert result.field_context.audience_dimension == "audience_gender"

    def test_analyze_entity_table_query(self, analyzer):
        """测试实体列表查询的场景识别"""
        user_input = "消耗最高的计划列表"

        result = analyzer.analyze(user_input)

        assert result.analysis_type_hint == AnalysisType.ENTITY_TABLE
        assert result.field_context.target_level == "campaign"
        assert "cost" in result.field_context.metrics

    def test_analyze_with_advertiser_context(self, analyzer):
        """测试带广告主上下文的分析"""
        user_input = "昨天的数据"
        conversation_history = [
            {"role": "user", "content": "查看广告主 123 的数据"},
            {"role": "assistant", "content": "好的，请问想看什么数据？"}
        ]

        result = analyzer.analyze(user_input, conversation_history)

        assert result.field_context.advertiser_ids == [123]

    def test_analyze_missing_fields(self, analyzer):
        """测试缺失字段识别"""
        user_input = "看看数据"

        result = analyzer.analyze(user_input)

        assert len(result.missing_fields) > 0
        # 应该缺少指标或时间范围
        assert any(f in result.missing_fields for f in ["metrics", "time_range"])

    def test_extract_advertiser_ids_explicit(self, analyzer):
        """测试显式提取广告主 ID"""
        user_input = "广告主 123 的数据"

        result = analyzer.analyze(user_input)

        assert 123 in result.field_context.advertiser_ids

    def test_extract_metrics_multiple(self, analyzer):
        """测试提取多个指标"""
        user_input = "曝光、点击、消耗、CTR、ROI"

        result = analyzer.analyze(user_input)

        metrics = result.field_context.metrics
        assert "impressions" in metrics
        assert "clicks" in metrics
        assert "cost" in metrics
        assert "ctr" in metrics
        assert "roi" in metrics

    def test_extract_target_level(self, analyzer):
        """测试提取目标层级"""
        test_cases = [
            ("计划的数据", "campaign"),
            ("广告组的消耗", "ad_group"),
            ("素材的表现", "creative"),
        ]

        for user_input, expected_level in test_cases:
            result = analyzer.analyze(user_input)
            assert result.field_context.target_level == expected_level

    def test_extract_relative_time_ranges(self, analyzer, today):
        """测试提取相对时间范围"""
        test_cases = [
            ("今天", today, today),
            ("昨天", today - timedelta(days=1), today - timedelta(days=1)),
            ("近7天", today - timedelta(days=6), today),
        ]

        for user_input, expected_start, expected_end in test_cases:
            result = analyzer.analyze(user_input)
            assert result.field_context.time_range is not None
            assert result.field_context.time_range.start_date == str(expected_start)
            assert result.field_context.time_range.end_date == str(expected_end)

    def test_extract_filter_conditions(self, analyzer):
        """测试粗略提取筛选条件"""
        user_input = "消耗大于 1000 的计划"

        result = analyzer.analyze(user_input)

        assert result.filter_type_hint == FilterType.HAVING or result.filter_type_hint == FilterType.MIXED
        # 应该能识别到有筛选条件

    def test_confidence_scores(self, analyzer):
        """测试置信度分数"""
        # 清晰的查询应该有高置信度
        clear_input = "广告主 123 昨天的曝光点击消耗，按天看趋势"
        clear_result = analyzer.analyze(clear_input)
        assert clear_result.confidence >= 0.7

        # 模糊的查询应该有低置信度
        vague_input = "看看数据"
        vague_result = analyzer.analyze(vague_input)
        assert vague_result.confidence < 0.7

    def test_empty_query(self, analyzer):
        """测试空查询处理"""
        result = analyzer.analyze("")

        assert result.confidence < 0.3
        assert len(result.missing_fields) > 0

    def test_rule_based_fallback(self, analyzer, monkeypatch):
        """测试规则提取作为主要方法（不需要 LLM）"""
        # IntentAnalyzer 应该主要使用规则提取，LLM 只是辅助
        user_input = "昨天的曝光点击消耗"

        result = analyzer.analyze(user_input)

        # 即使没有 LLM，规则也应该能提取到基本信息
        assert result.field_context.time_range is not None
        assert len(result.field_context.metrics) > 0
