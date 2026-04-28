"""规则引擎单元测试（固定阈值版本）
所有阈值来自配置文件，基于ES全量数据百分位计算得出
"""
import pytest
from src.tools.insight_rules import rule_engine
from src.tools.insight_config import insight_config
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


class TestHighlightRules:
    """亮点规则测试（固定阈值版本）"""

    def test_a01_high_ctr_triggered_with_sufficient_data(self):
        """A01: CTR在P80~P97区间内时触发"""
        lower_threshold = insight_config.get('highlight_rules.A01_high_ctr.threshold', 0.0233)
        upper_threshold = insight_config.get('highlight_rules.A01_high_ctr.upper_threshold', 0.0275)

        data = []
        # 5个低于下限的素材
        for i in range(5):
            data.append({
                "name": f"普通创意{i+1}",
                "id": f"c{i+1}",
                "impressions": 1000,
                "clicks": 20,  # 2% CTR
                "cost": 10,
                "conversions": 1
            })
        # 3个在区间内的素材（P80~P97之间）
        mid_ctr = (lower_threshold + upper_threshold) / 2
        mid_clicks = int(1000 * mid_ctr)
        for i in range(3):
            data.append({
                "name": f"优质创意{i+1}",
                "id": f"h{i+1}",
                "impressions": 1000,
                "clicks": mid_clicks,
                "cost": 20,
                "conversions": 2
            })
        # 2个超过上限的素材（应该触发P05异常，不触发A01）
        extreme_clicks = int(1000 * (upper_threshold + 0.005))
        for i in range(2):
            data.append({
                "name": f"异常创意{i+1}",
                "id": f"e{i+1}",
                "impressions": 1000,
                "clicks": extreme_clicks,
                "cost": 20,
                "conversions": 2
            })

        insights = rule_engine.analyze({"data": data}, {})
        a01_insights = [i for i in insights if i.id == "A01"]

        assert len(a01_insights) == 1
        assert a01_insights[0].type == InsightType.HIGHLIGHT
        assert a01_insights[0].severity == Severity.HIGH
        assert "ID:" in a01_insights[0].evidence
        assert "优质创意" in a01_insights[0].evidence
        # 证据中不应包含超过上限的素材
        assert "异常创意" not in a01_insights[0].evidence

    def test_a01_high_ctr_not_triggered_without_good_creatives(self):
        """A01: 低于下限或高于上限时都不触发"""
        lower_threshold = insight_config.get('highlight_rules.A01_high_ctr.threshold', 0.0233)
        upper_threshold = insight_config.get('highlight_rules.A01_high_ctr.upper_threshold', 0.0275)

        data = []
        # 5个低于下限
        for i in range(5):
            data.append({
                "name": f"低效创意{i+1}",
                "impressions": 1000,
                "clicks": int(1000 * (lower_threshold - 0.005)),
                "cost": 10,
                "conversions": 1
            })
        # 5个高于上限
        for i in range(5):
            data.append({
                "name": f"异常创意{i+1}",
                "impressions": 1000,
                "clicks": int(1000 * (upper_threshold + 0.005)),
                "cost": 10,
                "conversions": 1
            })

        insights = rule_engine.analyze({"data": data}, {})
        a01_insights = [i for i in insights if i.id == "A01"]
        assert len(a01_insights) == 0

    def test_a02_high_cvr_triggered_with_sufficient_data(self):
        """A02: CVR超过阈值时触发（默认阈值8%）"""
        threshold = insight_config.get('highlight_rules.A02_high_cvr.threshold', 0.08)

        data = []
        # 普通素材
        for i in range(5):
            data.append({
                "name": f"普通创意{i+1}",
                "impressions": 1000,
                "clicks": 50,
                "cost": 25,
                "conversions": 1  # 2% CVR
            })
        # 高CVR素材
        high_conv = int(50 * (threshold + 0.02))  # 超阈值2%
        for i in range(3):
            data.append({
                "name": f"高转化创意{i+1}",
                "id": f"h{i+1}",
                "impressions": 1000,
                "clicks": 50,
                "cost": 25,
                "conversions": high_conv
            })

        insights = rule_engine.analyze({"data": data}, {})
        a02_insights = [i for i in insights if i.id == "A02"]

        assert len(a02_insights) == 1
        assert "高转化创意" in a02_insights[0].evidence

    def test_a03_low_cpc_triggered_with_sufficient_data(self):
        """A03: CPC低于阈值时触发（默认阈值0.045元）"""
        threshold = insight_config.get('highlight_rules.A03_low_cpc.threshold', 0.045)

        data = []
        # 高CPC素材
        for i in range(5):
            data.append({
                "name": f"普通创意{i+1}",
                "impressions": 1000,
                "clicks": 20,
                "cost": 2,  # 0.1元 CPC (>0.045阈值)
                "conversions": 1
            })
        # 低CPC素材 (<=0.045元)
        for i in range(3):
            data.append({
                "name": f"低成本创意{i+1}",
                "id": f"l{i+1}",
                "impressions": 1000,
                "clicks": 50,
                "cost": 2,  # 0.04元 CPC (<=0.045阈值)
                "conversions": 1
            })

        insights = rule_engine.analyze({"data": data}, {})
        a03_insights = [i for i in insights if i.id == "A03"]

        assert len(a03_insights) == 1
        assert "低成本创意" in a03_insights[0].evidence


class TestProblemRules:
    """问题识别规则测试（固定阈值版本）"""

    def test_p01_low_cvr_triggered_with_sufficient_data(self):
        """P01: CVR低于阈值时触发（默认阈值2.85%）"""
        threshold = insight_config.get('problem_rules.P01_low_cvr.threshold', 0.0285)

        data = []
        # 正常素材 (3% CVR，高于阈值)
        for i in range(5):
            data.append({
                "name": f"正常创意{i+1}",
                "impressions": 1000,
                "clicks": 100,
                "cost": 50,
                "conversions": 3  # 3% CVR
            })
        # 低CVR素材 (2% CVR，低于2.85%阈值)
        for i in range(3):
            data.append({
                "name": f"低效创意{i+1}",
                "id": f"l{i+1}",
                "impressions": 1000,
                "clicks": 100,  # 确保点击量足够
                "cost": 50,
                "conversions": 2  # 2% CVR，低于阈值
            })

        insights = rule_engine.analyze({"data": data}, {})
        p01_insights = [i for i in insights if i.id == "P01"]

        assert len(p01_insights) == 1
        assert p01_insights[0].type == InsightType.PROBLEM
        assert "低效创意" in p01_insights[0].evidence

    def test_p03_high_cpa_triggered(self):
        """P03: CPA超过阈值时触发（默认阈值1.65元）"""
        threshold = insight_config.get('problem_rules.P03_high_cpa.threshold', 1.65)

        data = []
        # 正常素材
        for i in range(5):
            data.append({
                "name": f"正常创意{i+1}",
                "impressions": 1000,
                "clicks": 50,
                "cost": 50,  # 10元 / 5转化 = 1元 CPA
                "conversions": 50
            })
        # 高CPA素材 (>1.65元)
        for i in range(3):
            data.append({
                "name": f"高成本创意{i+1}",
                "id": f"h{i+1}",
                "impressions": 1000,
                "clicks": 50,
                "cost": 100,  # 100元 / 50转化 = 2元 CPA (>1.65)
                "conversions": 50
            })

        insights = rule_engine.analyze({"data": data}, {})
        p03_insights = [i for i in insights if i.id == "P03"]

        assert len(p03_insights) == 1
        assert "高成本创意" in p03_insights[0].evidence

    def test_p05_ctr_anomaly_triggered(self):
        """P05: CTR异常波动检测（低于~2.11%或高于~2.41%）"""
        low_threshold = insight_config.get('problem_rules.P05_ctr_anomaly.low_threshold', 0.0211)
        high_threshold = insight_config.get('problem_rules.P05_ctr_anomaly.high_threshold', 0.0241)

        data = []
        # 18个正常素材 (2.20% - 2.37% CTR，在正常区间内)
        for i in range(18):
            ctr = 0.0220 + i * 0.0001  # 2.20% ~ 2.37%，都在(2.11%, 2.41%)之间
            data.append({
                "name": f"创意{i+1}",
                "id": f"c{i+1}",
                "impressions": 10000,  # 增加曝光，避免int取整问题
                "clicks": int(10000 * ctr),
                "cost": 10,
                "conversions": 1
            })
        # 1个异常低CTR素材 (2.0% < 2.11%)
        data.append({
            "name": "异常素材1",
            "id": "a1",
            "impressions": 10000,
            "clicks": 200,  # 2.0% CTR
            "cost": 1,
            "conversions": 0
        })
        # 1个异常高CTR素材 (2.5% > 2.41%)
        data.append({
            "name": "异常素材2",
            "id": "a2",
            "impressions": 10000,
            "clicks": 250,  # 2.5% CTR
            "cost": 50,
            "conversions": 5
        })

        insights = rule_engine.analyze({"data": data}, {})
        p05_insights = [i for i in insights if i.id == "P05"]

        assert len(p05_insights) == 1
        assert p05_insights[0].type == InsightType.PROBLEM
        assert "异常素材" in p05_insights[0].evidence
        assert "ID:" in p05_insights[0].evidence

    def test_p02_creative_fatigue_triggered(self):
        """P02: 创意疲劳衰减 - 连续多日CTR下降"""
        data = [
            {"date": "2024-01-01", "name": "D1", "impressions": 1000, "clicks": 50},  # 5% CTR
            {"date": "2024-01-02", "name": "D2", "impressions": 1000, "clicks": 40},  # 4% CTR
            {"date": "2024-01-03", "name": "D3", "impressions": 1000, "clicks": 30},  # 3% CTR
        ]

        insights = rule_engine.analyze({"data": data}, {})
        p02_insights = [i for i in insights if i.id == "P02"]

        assert len(p02_insights) == 1
        assert p02_insights[0].type == InsightType.PROBLEM


class TestEdgeCases:
    """边界情况测试"""

    def test_zero_values_handled(self):
        """零值数据不崩溃"""
        data = [{
            "name": "测试",
            "impressions": 0,
            "clicks": 0,
            "cost": 0,
            "conversions": 0
        }]

        insights = rule_engine.analyze({"data": data}, {})
        assert isinstance(insights, list)

    def test_missing_fields_handled(self):
        """缺失字段数据不崩溃"""
        data = [{}]  # 空数据行
        insights = rule_engine.analyze({"data": data}, {})
        assert isinstance(insights, list)

    def test_summary_row_ignored(self):
        """汇总行（总计）不会误触发规则"""
        data = [{
            "name": "总计",
            "id": 0,
            "impressions": 27542798,
            "clicks": 627537,
            "cost": 100000,
            "conversions": 1000
        }]

        insights = rule_engine.analyze({"data": data}, {})
        # 汇总行应被忽略，不触发任何百分位规则
        insight_ids = [i.id for i in insights]
        assert "A01" not in insight_ids, "总计行不应该触发A01 CTR表现优异"
        assert "P05" not in insight_ids, "总计行不应该触发P05 CTR异常波动"

    def test_insight_id_format_correct(self):
        """验证洞察ID格式正确"""
        data = []
        # 构造一些高CTR素材
        threshold = insight_config.get('highlight_rules.A01_high_ctr.threshold', 0.035)
        high_clicks = int(1000 * (threshold + 0.01))
        for i in range(10):
            data.append({
                "name": f"创意{i+1}",
                "impressions": 1000,
                "clicks": high_clicks + i,
                "cost": 10 + i,
                "conversions": 1 + int(i / 3)
            })

        insights = rule_engine.analyze({"data": data}, {})

        for insight in insights:
            if insight.id.startswith("A"):
                assert insight.type == InsightType.HIGHLIGHT
            elif insight.id.startswith("P"):
                assert insight.type == InsightType.PROBLEM

    def test_insight_contains_required_fields(self):
        """验证洞察对象包含所有必要字段"""
        data = []
        threshold = insight_config.get('highlight_rules.A01_high_ctr.threshold', 0.035)
        high_clicks = int(1000 * (threshold + 0.01))
        for i in range(10):
            data.append({
                "name": f"创意{i+1}",
                "id": f"c{i+1}",
                "impressions": 1000,
                "clicks": high_clicks + i,
                "cost": 10 + i,
                "conversions": 1 + int(i / 3)
            })

        insights = rule_engine.analyze({"data": data}, {})

        for insight in insights:
            assert insight.id is not None
            assert insight.name is not None
            assert insight.type is not None
            assert insight.severity is not None
            assert insight.evidence is not None
            assert insight.suggestion is not None
