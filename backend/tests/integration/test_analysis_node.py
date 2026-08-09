"""
测试 analysis_node - CoT 分析节点集成测试
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# 导入节点
from backend.src.graph.nodes import analysis_node


@pytest.mark.asyncio
async def test_analysis_node_import():
    """测试 analysis_node 可以被正确导入"""
    # 这只是一个基本测试，确保模块结构正确
    assert callable(analysis_node)


@pytest.mark.asyncio
async def test_analysis_node_module_not_found():
    """测试 analysis_node 模块未找到时的降级行为"""
    state = {
        "user_input": "查看广告主123近7天的消耗趋势",
        "conversation_history": [],
        "advertiser_ids": ["123"],
        "session_id": "test-session-error"
    }

    # 模拟导入失败
    with patch.dict('sys.modules', {
        'src.analysis': None,
        'src.analysis.intent_analyzer': None,
        'src.nl_dsl': None,
    }):
        result = await analysis_node(state)

        assert "error" in result
        assert "execution_trace" in result
        assert result["error"]["type"] == "analysis_error"


@pytest.mark.asyncio
async def test_analysis_node_state_fields():
    """测试 analysis_node 使用的 state 字段已添加"""
    from backend.src.graph.state import AdReportState

    # 检查 state 是否有我们添加的字段
    # 注意：TypedDict 只是类型提示，我们需要查看定义
    state_def = AdReportState.__annotations__

    # 检查关键字段是否在定义中
    assert "analysis_plan" in state_def
    assert "field_context" in state_def
    assert "cot_reasoning" in state_def
    assert "filter_result" in state_def
    assert "chart_data" in state_def
    assert "quality_result" in state_def
    assert "hitl_request" in state_def
    assert "execution_trace" in state_def
