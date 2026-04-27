"""洞察模块集成测试"""
import pytest
import asyncio
from src.agents.insight_agent import insight_agent, insights_to_highlights
from src.models.insight import InsightResult, InsightType


class TestInsightIntegration:
    """洞察模块集成测试类"""

    def test_insight_agent_basic_workflow(self):
        """测试洞察Agent完整工作流"""
        # 准备测试数据 - 受众定位偏差场景
        # P01 规则要求: CTR 在 1%-3% 区间，且 CVR < 0.5%
        query_result = {
            "summary": {
                "avg_ctr": 0.02,  # 2% CTR (在1%-3%区间内)
            },
            "data": [
                {"ctr": 0.02, "cvr": 0.003},  # 2% CTR, 0.3% CVR - 触发P01
                {"ctr": 0.018, "cvr": 0.002},
            ]
        }
        query_context = {}

        # 调用异步函数
        result = asyncio.run(insight_agent(query_result, query_context))

        # 验证返回类型正确
        assert isinstance(result, InsightResult)

        # 验证有问题洞察（P01 受众定位偏差）
        assert len(result.problems) > 0
        problem_ids = [p.id for p in result.problems]
        assert "P01" in problem_ids

        # 验证summary字段已填充
        assert result.summary is not None
        assert isinstance(result.summary, str)

        # 验证 LLM insights 为空（默认不启用）
        assert len(result.llm_insights) == 0

        # 单独测试亮点场景（A01）
        highlight_query_result = {
            "summary": {
                "avg_ctr": 0.06,  # 6% CTR - 触发亮点A01
            },
            "data": []
        }
        highlight_context = {"baseline_ctr": 0.015}

        result2 = asyncio.run(insight_agent(highlight_query_result, highlight_context))
        assert len(result2.highlights) > 0
        highlight_ids = [h.id for h in result2.highlights]
        assert "A01" in highlight_ids

    def test_insights_to_highlights_conversion(self):
        """测试到前端 highlights 格式转换"""
        # 准备包含问题和亮点的 InsightResult
        query_result = {
            "summary": {
                "avg_ctr": 0.06,
                "avg_cvr": 0.003,
            },
            "data": [
                {"ctr": 0.06, "cvr": 0.003},
            ]
        }
        query_context = {
            "baseline_ctr": 0.015,
            "baseline_cvr": 0.03,
        }

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
        """使用真实场景数据测试"""
        # 场景1: 典型的创意疲劳 + 高 CTR 亮点
        scenario1_query_result = {
            "summary": {
                "avg_ctr": 0.07,  # 7% CTR - 亮点A01
                "avg_cvr": 0.04,  # 4% CVR - 正常
            },
            "data": [
                {"date": "2024-01-01", "ctr": 0.09, "cvr": 0.05},
                {"date": "2024-01-02", "ctr": 0.07, "cvr": 0.045},
                {"date": "2024-01-03", "ctr": 0.05, "cvr": 0.04},  # 连续下降 - 问题P02
            ]
        }
        scenario1_context = {"baseline_ctr": 0.015}

        result1 = asyncio.run(insight_agent(scenario1_query_result, scenario1_context))
        assert isinstance(result1, InsightResult)

        # 应该检测到创意疲劳问题
        p02_found = any(p.id == "P02" for p in result1.problems)
        assert p02_found, "应该检测到创意疲劳问题P02"

        # 应该检测到 CTR 亮点
        a01_found = any(h.id == "A01" for h in result1.highlights)
        assert a01_found, "应该检测到CTR亮点A01"

        # 场景2: 时段投放浪费问题
        scenario2_query_result = {
            "summary": {
                "avg_cpa": 80,
            },
            "data": [
                {"hour": "0-2", "cost": 2000, "cpa": 300},  # 凌晨成本过高 - 问题P03
                {"hour": "8-10", "cost": 500, "cpa": 60},
                {"hour": "12-14", "cost": 600, "cpa": 70},
            ]
        }

        result2 = asyncio.run(insight_agent(scenario2_query_result, {}))
        assert isinstance(result2, InsightResult)

        p03_found = any(p.id == "P03" for p in result2.problems)
        assert p03_found, "应该检测到时点投放浪费问题P03"

        # 场景3: 流量作弊嫌疑
        scenario3_query_result = {
            "data": [
                {"ctr": 0.18, "bounce_rate": 0.96},  # 高CTR + 高跳出率 - 问题P05
                {"ctr": 0.15, "bounce_rate": 0.94},
            ]
        }

        result3 = asyncio.run(insight_agent(scenario3_query_result, {}))
        assert isinstance(result3, InsightResult)

        p05_found = any(p.id == "P05" for p in result3.problems)
        assert p05_found, "应该检测到流量作弊嫌疑P05"

        # 场景4: 多亮点组合
        scenario4_query_result = {
            "summary": {
                "avg_ctr": 0.08,  # 亮点A01
                "avg_cvr": 0.15,  # 15% CVR - 亮点A02
                "avg_cpc": 0.5,   # 0.5元 CPC - 亮点A03
                "avg_frequency": 2.0,  # 亮点A05
            },
            "breakdowns": {
                "time_slot": [
                    {"name": "0-2", "cvr": 0.03},
                    {"name": "8-10", "cvr": 0.20},  # 时段亮点A07
                ]
            }
        }
        scenario4_context = {
            "baseline_ctr": 0.015,
            "baseline_cvr": 0.03,
            "baseline_cpc": 2.0,
        }

        result4 = asyncio.run(insight_agent(scenario4_query_result, scenario4_context))
        assert isinstance(result4, InsightResult)
        assert len(result4.highlights) >= 4, "应该检测到多个亮点"

    def test_empty_data_handled_gracefully(self):
        """空数据处理测试"""
        # 测试1: 完全空的数据
        empty_result1 = asyncio.run(insight_agent({}, {}))
        assert isinstance(empty_result1, InsightResult)
        assert len(empty_result1.problems) == 0
        assert len(empty_result1.highlights) == 0
        assert len(empty_result1.llm_insights) == 0

        # 转换为 highlights 应该给出平稳提示
        highlights1 = insights_to_highlights(empty_result1)
        assert len(highlights1) == 1
        assert highlights1[0]["type"] == "info"
        assert "平稳" in highlights1[0]["text"]

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
