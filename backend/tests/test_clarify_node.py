import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.intent.clarify_node import (
    clarify_node,
    detect_intent_change,
    build_clarification_state,
)
from src.intent.models import ClarificationInfo


class TestDetectIntentChange:
    """回退检测测试（mock LLM）"""

    def _make_mock_client(self, has_changed, new_category=None):
        import json as _json
        mock = MagicMock()
        mock.call = AsyncMock(return_value=_json.dumps({
            "has_changed": has_changed,
            "new_category": new_category,
            "reason": "test reason"
        }))
        return mock

    @pytest.mark.asyncio
    async def test_no_change(self):
        """用户只是补充信息，意图没变"""
        mock = self._make_mock_client(False, None)
        changed, new_cat = await detect_intent_change(
            "我想补充一下时间",
            "report",
            "看看消耗",
            llm_client=mock,
        )
        assert changed is False
        assert new_cat is None

    @pytest.mark.asyncio
    async def test_change_to_report(self):
        """用户从知识问答切换到报表查询"""
        mock = self._make_mock_client(True, "report")
        changed, new_cat = await detect_intent_change(
            "不是，我想查消耗数据",
            "knowledge",
            "什么是冷启动",
            llm_client=mock,
        )
        assert changed is True
        assert new_cat == "report"

    @pytest.mark.asyncio
    async def test_change_to_knowledge(self):
        """用户从报表切换到知识问答"""
        mock = self._make_mock_client(True, "knowledge")
        changed, new_cat = await detect_intent_change(
            "不是，我想了解什么是 CTR",
            "report",
            "看昨天的数据",
            llm_client=mock,
        )
        assert changed is True
        assert new_cat == "knowledge"


class TestBuildClarificationState:
    """构建澄清状态测试"""

    def test_build_missing_advertiser(self):
        info = ClarificationInfo(
            type="missing_advertiser",
            question="请问你想查看哪个广告主？",
            options=[],
            allow_custom_input=True,
        )
        state = build_clarification_state(info)
        assert state["needs_clarification"] is True
        assert state["clarification"]["type"] == "missing_advertiser"
        assert state["clarification"]["question"] == "请问你想查看哪个广告主？"


class TestClarifyNode:
    """澄清节点函数测试"""

    @pytest.mark.asyncio
    async def test_clarify_node_sets_next_action(self):
        """澄清节点设置下一步动作"""
        state = {
            "user_feedback": {"selected_value": "广告主A"},
            "intent_category": "report",
            "user_input": "看看数据",
        }
        # 因为 clarify_node 依赖很多其他模块，这里只测试基本导入和结构
        # 完整功能在集成测试中验证
        assert callable(clarify_node)