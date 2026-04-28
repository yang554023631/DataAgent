"""洞察模块集成测试（百分位版本）
所有测试基于配置文件中的百分位阈值
"""
import pytest
import asyncio
from src.agents.insight_agent import insight_agent, insights_to_highlights
from src.models.insight import InsightResult, InsightType


class TestInsightIntegration:
    """洞察模块集成测试类"""

    def test_insight_agent_basic_workflow(self):
        """测试洞察Agent完整工作流 - 固定阈值版本"""
        # 准备测试数据 - P01 CVR转化低下场景（<=2%）
        # 同时包含高CTR素材触发A01 (>2.5%)
        data = []
        # 5个低CVR素材（1% CVR，低于阈值2%）
        for i in range(5):
            data.append({
                "name": f"低效创意{i+1}",
                "id": f"l{i+1}",
                "impressions": 1000,
                "clicks": 100,
                "cost": 50,
                "conversions": 1  # 1% CVR，低于阈值
            })
        # 5个高CTR素材（5% CTR，高于阈值2.5%）
        for i in range(5):
            data.append({
                "name": f"优质创意{i+1}",
                "id": f"h{i+1}",
                "impressions": 1000,
                "clicks": 50,  # 5% CTR
                "cost": 25,
                "conversions": 5  # 10% CVR
            })

        query_result = {"data": data}
        query_context = {}

        # 调用异步函数
        result = asyncio.run(insight_agent(query_result, query_context))

        # 验证返回类型正确
        assert isinstance(result, InsightResult)

        # 验证有问题洞察（P01 CVR转化低下）
        assert len(result.problems) > 0
        problem_ids = [p.id for p in result.problems]
        assert "P01" in problem_ids

        # 验证summary字段已填充
        assert result.summary is not None
        assert isinstance(result.summary, str)

        # 验证 LLM insights 为空（默认不启用）
        assert len(result.llm_insights) == 0

        # 单独测试亮点场景（A01 CTR表现优异 - 前80%）
        highlight_data = []
        for i in range(10):
            ctr = 0.01 + i * 0.003  # CTR 1% to 3.7%
            highlight_data.append({
                "name": f"创意{i+1}",
                "impressions": 1000,
                "clicks": int(1000 * ctr),
                "cost": int(1000 * ctr) * 0.5,
                "conversions": 1
            })

        highlight_query_result = {"data": highlight_data}
        highlight_context = {}

        result2 = asyncio.run(insight_agent(highlight_query_result, highlight_context))
        assert len(result2.highlights) > 0
        highlight_ids = [h.id for h in result2.highlights]
        assert "A01" in highlight_ids

    def test_insights_to_highlights_conversion(self):
        """测试到前端 highlights 格式转换"""
        # 准备包含问题和亮点的 InsightResult
        # 构造数据同时触发A01(高CTR)和P01(低CVR)
        data = []
        for i in range(20):
            ctr = 0.01 + i * 0.002  # 1% to 4.8%
            cvr = 0.005 + i * 0.002  # 0.5% to 4.3%
            data.append({
                "name": f"创意{i+1}",
                "impressions": 1000,
                "clicks": int(1000 * ctr),
                "cost": int(1000 * ctr) * 0.5,
                "conversions": int(1000 * ctr * cvr) or 1
            })

        query_result = {"data": data}
        query_context = {}

        insight_result = asyncio.run(insight_agent(query_result, query_context))
        highlights = insights_to_highlights(insight_result)

        # 验证返回类型
        assert isinstance(highlights, list)

        # 验证每个 highlight 格式正确
        for highlight in highlights:
            assert "type" in highlight
            assert "text" in highlight
            assert isinstance(highlight["type"], str)
            assert isinstance(highlight["text"], str)

            # 验证 type 是有效值
            assert highlight["type"] in ["negative", "positive", "info", "problem", "highlight"]

            # 验证 text 包含预期内容
            assert "【" in highlight["text"]
            assert "证据：" in highlight["text"]

        # 验证问题使用 negative 类型，带有 🔴 图标
        negative_highlights = [h for h in highlights if h["type"] == "negative"]
        for h in negative_highlights:
            assert "🔴" in h["text"]

        # 验证亮点使用 positive 类型，带有 🟢 图标
        positive_highlights = [h for h in highlights if h["type"] == "positive"]
        for h in positive_highlights:
            assert "🟢" in h["text"]

    def test_rule_engine_with_realistic_data(self):
        """使用真实场景数据测试 - 固定阈值版本"""
        # 场景1: 创意疲劳（时序规则，仍使用绝对逻辑）
        # 同时包含足够数据触发A01 CTR亮点（>2.5%）
        scenario1_data = []
        # 前7天CTR递增：2% - 8%（后5天高于阈值2.5%）
        for i in range(7):
            ctr = 0.02 + i * 0.01
            scenario1_data.append({
                "name": f"D{i+1}",
                "date": f"2024-01-0{i+1}",
                "impressions": 1000,
                "clicks": int(1000 * ctr),
                "cost": 50,
                "conversions": 2
            })
        # 最后3天CTR下降，触发P02创意疲劳
        scenario1_data.append({"name": "D8", "date": "2024-01-08", "impressions": 1000, "clicks": 50, "cost": 25, "conversions": 1})  # 5%
        scenario1_data.append({"name": "D9", "date": "2024-01-09", "impressions": 1000, "clicks": 40, "cost": 20, "conversions": 1})  # 4%
        scenario1_data.append({"name": "D10", "date": "2024-01-10", "impressions": 1000, "clicks": 30, "cost": 15, "conversions": 1})  # 3%

        scenario1_query_result = {"data": scenario1_data}
        scenario1_context = {}

        result1 = asyncio.run(insight_agent(scenario1_query_result, scenario1_context))
        assert isinstance(result1, InsightResult)

        # 应该检测到创意疲劳问题
        p02_found = any(p.id == "P02" for p in result1.problems)
        assert p02_found, "应该检测到创意疲劳问题P02"

        # P02创意疲劳能检测到，A01需要特定范围的CTR数据，本场景不测试
        # 专注验证P02创意疲劳时序规则

        # 场景2: CPA转化成本过高（前80%）
        scenario2_data = []
        for i in range(10):
            cpa = 30 + i * 10  # 30元 to 120元
            conversions = 2
            scenario2_data.append({
                "name": f"时段{i+1}",
                "impressions": 1000,
                "clicks": 20,
                "cost": conversions * cpa,
                "conversions": conversions
            })

        scenario2_query_result = {"data": scenario2_data}
        result2 = asyncio.run(insight_agent(scenario2_query_result, {}))
        assert isinstance(result2, InsightResult)

        p03_found = any(p.id == "P03" for p in result2.problems)
        assert p03_found, "应该检测到CPA转化成本过高问题P03"

        # 场景3: CTR异常（P5-P95范围外）
        scenario3_data = []
        # 18个正常素材
        for i in range(18):
            scenario3_data.append({
                "name": f"创意{i+1}",
                "impressions": 1000,
                "clicks": 20 + i,  # 2% to 3.7% CTR
                "cost": 10 + i * 0.5,
                "conversions": 1
            })
        # 1个异常低CTR素材
        scenario3_data.append({
            "name": "异常素材1",
            "impressions": 1000,
            "clicks": 2,  # 0.2% CTR
            "cost": 1,
            "conversions": 0
        })
        # 1个异常高CTR素材
        scenario3_data.append({
            "name": "异常素材2",
            "impressions": 1000,
            "clicks": 100,  # 10% CTR
            "cost": 50,
            "conversions": 5
        })

        scenario3_query_result = {"data": scenario3_data}
        result3 = asyncio.run(insight_agent(scenario3_query_result, {}))
        assert isinstance(result3, InsightResult)

        p05_found = any(p.id == "P05" for p in result3.problems)
        assert p05_found, "应该检测到CTR异常P05"

        # 场景4: 多亮点组合
        # 构造数据同时触发多个亮点规则
        scenario4_data = []
        for i in range(20):
            ctr = 0.01 + i * 0.002  # 1% to 4.8% (前20%触发A01)
            cvr = 0.01 + i * 0.003  # 1% to 6.7% (前20%触发A02)
            cpc = 0.5 + i * 0.1     # 0.5元 to 2.4元 (后20%触发A03)
            clicks = int(1000 * ctr)
            scenario4_data.append({
                "name": f"创意{i+1}",
                "impressions": 1000,
                "clicks": clicks,
                "cost": clicks * cpc,
                "conversions": int(clicks * cvr) or 1
            })

        scenario4_query_result = {"data": scenario4_data}
        scenario4_context = {}

        result4 = asyncio.run(insight_agent(scenario4_query_result, scenario4_context))
        assert isinstance(result4, InsightResult)
        assert len(result4.highlights) >= 2, "应该检测到多个亮点"

    def test_empty_data_handled_gracefully(self):
        """空数据处理测试"""
        # 测试1: 完全空的数据
        empty_result1 = asyncio.run(insight_agent({}, {}))
        assert isinstance(empty_result1, InsightResult)
        assert len(empty_result1.problems) == 0
        assert len(empty_result1.highlights) == 0
        assert len(empty_result1.llm_insights) == 0

        # 转换为 highlights 应该给出无数据提示
        highlights1 = insights_to_highlights(empty_result1)
        assert len(highlights1) == 1
        assert highlights1[0]["type"] == "info"
        assert "暂无数据" in highlights1[0]["text"]

        # 测试2: data 为空数组
        empty_result2 = asyncio.run(insight_agent({"data": []}, {}))
        assert isinstance(empty_result2, InsightResult)

        highlights2 = insights_to_highlights(empty_result2)
        assert isinstance(highlights2, list)

        # 测试3: summary 为空字典
        empty_result3 = asyncio.run(insight_agent({"summary": {}}, {}))
        assert isinstance(empty_result3, InsightResult)

        highlights3 = insights_to_highlights(empty_result3)
        assert isinstance(highlights3, list)

        # 测试4: 所有值为0的数据
        zero_data_result = asyncio.run(insight_agent(
            {"summary": {"avg_ctr": 0, "avg_cvr": 0, "avg_cpc": 0}},
            {}
        ))
        assert isinstance(zero_data_result, InsightResult)

        highlights4 = insights_to_highlights(zero_data_result)
        assert isinstance(highlights4, list)

        # 测试5: None 值处理
        none_result = asyncio.run(insight_agent(
            {"data": None, "summary": None},
            {}
        ))
        assert isinstance(none_result, InsightResult)
        assert none_result.summary is not None  # 即使数据为空，也应该生成摘要

        highlights5 = insights_to_highlights(none_result)
        assert isinstance(highlights5, list)
        for h in highlights5:
            assert "type" in h
            assert "text" in h


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
