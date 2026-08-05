import pytest
from src.intent.reject_node import reject_node, build_reject_response


class TestRejectNode:
    def test_build_reject_response_top_level(self):
        """顶层直接拒答"""
        resp = build_reject_response("top_level")
        assert "广告" in resp["highlights"][0]["text"]
        assert "抱歉" in resp["highlights"][0]["text"]

    def test_build_reject_response_knowledge_scope(self):
        """知识问答二次拒答"""
        resp = build_reject_response("knowledge_scope")
        assert "广告" in resp["highlights"][0]["text"]
        assert "回答不了" in resp["highlights"][0]["text"] or "抱歉" in resp["highlights"][0]["text"]

    @pytest.mark.asyncio
    async def test_reject_node_top_level(self):
        """节点函数：顶层拒答"""
        state = {"user_input": "今天天气怎么样", "intent_category": "out_of_domain"}
        result = await reject_node(state)
        assert "final_report" in result
        report = result["final_report"]
        assert "title" in report
        assert "highlights" in report
        assert len(report["highlights"]) > 0