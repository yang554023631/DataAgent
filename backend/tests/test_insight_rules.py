"""规则引擎单元测试"""
import pytest
from src.tools.insight_rules import rule_engine
from src.models.insight import InsightType, Severity


class TestRuleEngine:
    """规则引擎基础测试"""

    def test_rule_engine_initialized(self):
        """测试规则引擎正确初始化"""
        assert rule_engine is not None
        assert len(rule_engine._rules) > 0

    def test_empty_data_returns_no_insights(self):
        """测试空数据不返回任何洞察"""
        query_result = {}
        query_context = {}
        insights = rule_engine.analyze(query_result, query_context)
        assert len(insights) == 0

    def test_none_data_handles_gracefully(self):
        """测试None数据不崩溃"""
        query_result = {"data": None, "summary": None}
        query_context = {}
        insights = rule_engine.analyze(query_result, query_context)
        assert isinstance(insights, list)


class TestProblemRules:
    """问题识别规则测试"""

    def test_p01_audience_mismatch_triggered(self):
        """P01: 受众定位偏差 - CTR正常但CVR极低"""
        query_result = {
            "data": [
                {"ctr": 0.015, "cvr": 0.003},  # CTR 1.5%, CVR 0.3%
                {"ctr": 0.020, "cvr": 0.004},
                {"ctr": 0.018, "cvr": 0.002},
            ]
        }
        insights = rule_engine.analyze(query_result, {})

        p01_insights = [i for i in insights if i.id == "P01"]
        assert len(p01_insights) == 1
        assert p01_insights[0].type == InsightType.PROBLEM
        assert p01_insights[0].severity == Severity.HIGH

    def test_p01_audience_mismatch_not_triggered_normal_data(self):
        """P01: 正常数据不应触发受众定位偏差"""
        query_result = {
            "data": [
                {"ctr": 0.015, "cvr": 0.02},  # CVR 2% 正常
                {"ctr": 0.020, "cvr": 0.025},
            ]
        }
        insights = rule_engine.analyze(query_result, {})
        p01_insights = [i for i in insights if i.id == "P01"]
        assert len(p01_insights) == 0

    def test_p02_creative_fatigue_triggered(self):
        """P02: 创意疲劳衰减 - 连续多日CTR下降"""
        query_result = {
            "data": [
                {"date": "2024-01-01", "ctr": 0.05},  # 第一天 5%
                {"date": "2024-01-02", "ctr": 0.04},  # 第二天 4%
                {"date": "2024-01-03", "ctr": 0.03},  # 第三天 3%
            ]
        }
        insights = rule_engine.analyze(query_result, {})

        p02_insights = [i for i in insights if i.id == "P02"]
        assert len(p02_insights) == 1
        assert p02_insights[0].type == InsightType.PROBLEM
        assert p02_insights[0].severity == Severity.MEDIUM

    def test_p02_creative_fatigue_not_triggered_insufficient_days(self):
        """P02: 数据不足3天不触发创意疲劳"""
        query_result = {
            "data": [
                {"date": "2024-01-01", "ctr": 0.05},
                {"date": "2024-01-02", "ctr": 0.03},
            ]
        }
        insights = rule_engine.analyze(query_result, {})
        p02_insights = [i for i in insights if i.id == "P02"]
        assert len(p02_insights) == 0

    def test_p03_time_waste_triggered(self):
        """P03: 时段投放浪费"""
        query_result = {
            "data": [
                {"hour": "0-2", "cost": 1000, "cpa": 200},
                {"hour": "8-10", "cost": 200, "cpa": 50},
                {"hour": "12-14", "cost": 200, "cpa": 60},
            ]
        }
        insights = rule_engine.analyze(query_result, {})

        p03_insights = [i for i in insights if i.id == "P03"]
        assert len(p03_insights) == 1
        assert p03_insights[0].type == InsightType.PROBLEM
        assert p03_insights[0].severity == Severity.HIGH
        assert p03_insights[0].dimension_value == "0-2"

    def test_p03_time_waste_not_triggered_balanced_cpa(self):
        """P03: CPA均衡不触发放心浪费"""
        query_result = {
            "data": [
                {"hour": "0-2", "cost": 1000, "cpa": 60},
                {"hour": "8-10", "cost": 200, "cpa": 50},
                {"hour": "12-14", "cost": 200, "cpa": 55},
            ]
        }
        insights = rule_engine.analyze(query_result, {})
        p03_insights = [i for i in insights if i.id == "P03"]
        assert len(p03_insights) == 0

    def test_p05_fraud_suspicion_triggered(self):
        """P05: 流量作弊嫌疑"""
        query_result = {
            "data": [
                {"ctr": 0.15, "bounce_rate": 0.95},  # CTR 15%, 跳出率 95%
                {"ctr": 0.12, "bounce_rate": 0.92},
            ]
        }
        insights = rule_engine.analyze(query_result, {})

        p05_insights = [i for i in insights if i.id == "P05"]
        assert len(p05_insights) == 1
        assert p05_insights[0].type == InsightType.PROBLEM
        assert p05_insights[0].severity == Severity.HIGH

    def test_p05_fraud_suspicion_not_triggered_normal_ctr(self):
        """P05: 正常CTR不触发作弊嫌疑"""
        query_result = {
            "data": [
                {"ctr": 0.05, "bounce_rate": 0.5},  # 正常数据
            ]
        }
        insights = rule_engine.analyze(query_result, {})
        p05_insights = [i for i in insights if i.id == "P05"]
        assert len(p05_insights) == 0


class TestHighlightRules:
    """亮点规则测试"""

    def test_a01_high_ctr_triggered(self):
        """A01: CTR表现优异"""
        query_result = {
            "summary": {"avg_ctr": 0.06}  # 6% CTR, 基准1.5%, >3倍
        }
        query_context = {"baseline_ctr": 0.015}
        insights = rule_engine.analyze(query_result, query_context)

        a01_insights = [i for i in insights if i.id == "A01"]
        assert len(a01_insights) == 1
        assert a01_insights[0].type == InsightType.HIGHLIGHT
        assert a01_insights[0].severity == Severity.HIGH
        assert a01_insights[0].current_value == 6.0

    def test_a01_high_ctr_not_triggered_normal(self):
        """A01: 正常CTR不触发"""
        query_result = {
            "summary": {"avg_ctr": 0.02}  # 2% CTR, 不足3倍基准
        }
        query_context = {"baseline_ctr": 0.015}
        insights = rule_engine.analyze(query_result, query_context)
        a01_insights = [i for i in insights if i.id == "A01"]
        assert len(a01_insights) == 0

    def test_a02_high_cvr_triggered(self):
        """A02: CVR表现优异"""
        query_result = {
            "summary": {"avg_cvr": 0.12}  # 12% CVR, 基准3%, >3倍
        }
        query_context = {"baseline_cvr": 0.03}
        insights = rule_engine.analyze(query_result, query_context)

        a02_insights = [i for i in insights if i.id == "A02"]
        assert len(a02_insights) == 1
        assert a02_insights[0].type == InsightType.HIGHLIGHT
        assert a02_insights[0].severity == Severity.HIGH

    def test_a02_high_cvr_not_triggered_normal(self):
        """A02: 正常CVR不触发"""
        query_result = {
            "summary": {"avg_cvr": 0.04}  # 4% CVR, 不足3倍基准
        }
        query_context = {"baseline_cvr": 0.03}
        insights = rule_engine.analyze(query_result, query_context)
        a02_insights = [i for i in insights if i.id == "A02"]
        assert len(a02_insights) == 0

    def test_a03_low_cpc_triggered(self):
        """A03: CPC成本优势"""
        query_result = {
            "summary": {"avg_cpc": 0.8}  # 0.8元, 基准2元, <50%
        }
        query_context = {"baseline_cpc": 2.0}
        insights = rule_engine.analyze(query_result, query_context)

        a03_insights = [i for i in insights if i.id == "A03"]
        assert len(a03_insights) == 1
        assert a03_insights[0].type == InsightType.HIGHLIGHT
        assert a03_insights[0].severity == Severity.HIGH

    def test_a03_low_cpc_not_triggered_normal(self):
        """A03: 正常CPC不触发"""
        query_result = {
            "summary": {"avg_cpc": 1.5}  # 1.5元, >50%基准
        }
        query_context = {"baseline_cpc": 2.0}
        insights = rule_engine.analyze(query_result, query_context)
        a03_insights = [i for i in insights if i.id == "A03"]
        assert len(a03_insights) == 0

    def test_a05_good_frequency_control_triggered(self):
        """A05: 频次控制良好"""
        query_result = {
            "summary": {"avg_frequency": 2.0}  # 在1.5-2.5区间内
        }
        insights = rule_engine.analyze(query_result, {})

        a05_insights = [i for i in insights if i.id == "A05"]
        assert len(a05_insights) == 1
        assert a05_insights[0].type == InsightType.HIGHLIGHT
        assert a05_insights[0].severity == Severity.MEDIUM

    def test_a05_good_frequency_control_not_triggered_too_high(self):
        """A05: 频次过高不触发"""
        query_result = {
            "summary": {"avg_frequency": 5.0}  # 过高
        }
        insights = rule_engine.analyze(query_result, {})
        a05_insights = [i for i in insights if i.id == "A05"]
        assert len(a05_insights) == 0

    def test_a07_time_slot_cvr_contrast_triggered(self):
        """A07: 分时段反差亮点"""
        query_result = {
            "summary": {"avg_cvr": 0.03},  # 整体3%
            "breakdowns": {
                "time_slot": [
                    {"name": "0-2", "cvr": 0.02},
                    {"name": "8-10", "cvr": 0.10},  # 10% > 3倍整体
                    {"name": "12-14", "cvr": 0.03},
                ]
            }
        }
        insights = rule_engine.analyze(query_result, {})

        a07_insights = [i for i in insights if i.id == "A07"]
        assert len(a07_insights) == 1
        assert a07_insights[0].type == InsightType.HIGHLIGHT
        assert a07_insights[0].severity == Severity.HIGH
        assert a07_insights[0].dimension_value == "8-10"

    def test_a07_time_slot_cvr_contrast_not_triggered_normal(self):
        """A07: 正常分时段数据不触发"""
        query_result = {
            "summary": {"avg_cvr": 0.03},
            "breakdowns": {
                "time_slot": [
                    {"name": "0-2", "cvr": 0.02},
                    {"name": "8-10", "cvr": 0.04},  # 不足3倍
                    {"name": "12-14", "cvr": 0.03},
                ]
            }
        }
        insights = rule_engine.analyze(query_result, {})
        a07_insights = [i for i in insights if i.id == "A07"]
        assert len(a07_insights) == 0


class TestEdgeCases:
    """边界情况测试"""

    def test_normal_data_no_insights(self):
        """正常数据不应触发任何洞察"""
        query_result = {
            "summary": {
                "avg_ctr": 0.02,  # 2% - 正常
                "avg_cvr": 0.03,  # 3% - 正常
                "avg_cpc": 2.0,   # 2元 - 正常
                "avg_frequency": 3.0,  # 超出理想区间但不算问题
            },
            "data": [
                {"ctr": 0.02, "cvr": 0.03, "cost": 500, "cpa": 60},
            ]
        }
        insights = rule_engine.analyze(query_result, {})

        # 正常数据不应该触发问题洞察
        problem_insights = [i for i in insights if i.type == InsightType.PROBLEM]
        assert len(problem_insights) == 0

    def test_zero_values_handled(self):
        """零值数据不崩溃"""
        query_result = {
            "summary": {
                "avg_ctr": 0,
                "avg_cvr": 0,
                "cpc": 0,
            },
            "data": []
        }
        insights = rule_engine.analyze(query_result, {})
        assert isinstance(insights, list)

    def test_missing_fields_handled(self):
        """缺失字段数据不崩溃"""
        query_result = {
            "summary": {},  # 空summary
            "data": [{}]    # 空数据行
        }
        insights = rule_engine.analyze(query_result, {})
        assert isinstance(insights, list)

    def test_insight_id_format_correct(self):
        """验证洞察ID格式正确"""
        # 测试A类洞察ID
        query_result = {
            "summary": {"avg_ctr": 0.06}
        }
        insights = rule_engine.analyze(query_result, {"baseline_ctr": 0.015})

        for insight in insights:
            if insight.id.startswith("A"):
                assert insight.type == InsightType.HIGHLIGHT
            elif insight.id.startswith("P"):
                assert insight.type == InsightType.PROBLEM
