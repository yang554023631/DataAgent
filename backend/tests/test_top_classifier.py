import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.intent.top_classifier import IntentTopClassifier
from src.intent.models import TopClassificationResult


class TestRuleFastpath:
    """规则快筛测试（不需要 LLM）"""

    def setup_method(self):
        self.classifier = IntentTopClassifier(llm_client=None)

    def test_time_plus_metric_fastpath(self):
        """时间词 + 指标词 → 快筛命中 report"""
        result = self.classifier._rule_fastpath("昨天的曝光点击消耗")
        assert result is not None
        assert result.category == "report"
        assert result.source == "rule_fastpath"
        assert result.confidence == 1.0

    def test_action_plus_metric_fastpath(self):
        """查询动作 + 指标 → 快筛命中"""
        result = self.classifier._rule_fastpath("查看 CTR 和 ROI 数据")
        assert result is not None
        assert result.category == "report"

    def test_comparison_pattern_fastpath(self):
        """对比模式 → 快筛命中"""
        result = self.classifier._rule_fastpath("3月和4月的消耗对比")
        assert result is not None
        assert result.category == "report"

    def test_knowledge_not_fastpath(self):
        """知识类问题 → 快筛不命中（交给 LLM）"""
        result = self.classifier._rule_fastpath("什么是 CTR")
        assert result is None

    def test_out_of_domain_not_fastpath(self):
        """领域外 → 快筛不命中（交给 LLM）"""
        result = self.classifier._rule_fastpath("今天天气怎么样")
        assert result is None

    def test_short_ambiguous_not_fastpath(self):
        """太短太模糊 → 快筛不命中"""
        result = self.classifier._rule_fastpath("帮我看看")
        assert result is None


class TestLLMClassification:
    """LLM 分类测试（mock LLM 客户端）"""

    def _make_mock_client(self, response_json: dict):
        """创建 mock LLM 客户端"""
        mock_client = MagicMock()
        import json
        mock_client.call = AsyncMock(return_value=json.dumps(response_json))
        return mock_client

    @pytest.mark.asyncio
    async def test_classify_report_via_llm(self):
        """LLM 返回 report 分类"""
        mock_client = self._make_mock_client({
            "category": "report",
            "confidence": 0.92,
            "reason": "用户提到了消耗和上周，属于数据查询"
        })
        classifier = IntentTopClassifier(llm_client=mock_client)
        # 用一个不会走快筛的输入
        result = await classifier.classify("分析一下投放效果怎么样")
        assert isinstance(result, TopClassificationResult)
        assert result.category == "report"
        assert result.confidence == 0.92
        assert result.source == "llm"

    @pytest.mark.asyncio
    async def test_classify_knowledge(self):
        mock_client = self._make_mock_client({
            "category": "knowledge",
            "confidence": 0.85,
            "reason": "用户询问冷启动策略，属于知识问答"
        })
        classifier = IntentTopClassifier(llm_client=mock_client)
        result = await classifier.classify("冷启动跑不动怎么办")
        assert result.category == "knowledge"

    @pytest.mark.asyncio
    async def test_classify_out_of_domain(self):
        mock_client = self._make_mock_client({
            "category": "out_of_domain",
            "confidence": 0.95,
            "reason": "天气与广告无关"
        })
        classifier = IntentTopClassifier(llm_client=mock_client)
        result = await classifier.classify("今天天气怎么样")
        assert result.category == "out_of_domain"

    @pytest.mark.asyncio
    async def test_low_confidence(self):
        """低置信度结果保持原值，由调用方判断阈值"""
        mock_client = self._make_mock_client({
            "category": "report",
            "confidence": 0.5,
            "reason": "用户输入太模糊"
        })
        classifier = IntentTopClassifier(llm_client=mock_client)
        result = await classifier.classify("帮我看看")
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_fastpath_skips_llm(self):
        """快筛命中时不调用 LLM"""
        mock_client = self._make_mock_client({"category": "report", "confidence": 0.9})
        classifier = IntentTopClassifier(llm_client=mock_client)
        result = await classifier.classify("昨天的曝光和点击")
        assert result.source == "rule_fastpath"
        # LLM 不应该被调用
        assert mock_client.call.await_count == 0

    @pytest.mark.asyncio
    async def test_llm_invalid_json_fallback(self):
        """LLM 返回无效 JSON 时的降级处理"""
        mock_client = MagicMock()
        mock_client.call = AsyncMock(return_value="invalid json response")
        classifier = IntentTopClassifier(llm_client=mock_client)
        # 失败时默认返回 knowledge（最安全的降级）
        result = await classifier.classify("一些模糊的输入")
        assert result.category in ["knowledge", "report"]
        assert result.confidence < 0.7
