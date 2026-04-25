import pytest
from src.tools.clarification_generator import generate_clarification_options

def test_generate_clarification_metric():
    result = generate_clarification_options.invoke(
        {"ambiguity_type": "metric", "context": {}}
    )
    assert "指标" in result.question
    assert len(result.options) == 3

def test_generate_clarification_time():
    result = generate_clarification_options.invoke(
        {"ambiguity_type": "time", "context": {}}
    )
    assert "时间范围" in result.question

def test_generate_clarification_query_too_large():
    result = generate_clarification_options.invoke(
        {"ambiguity_type": "query_too_large", "context": {"estimated_rows": 2000}}
    )
    assert "2000" in result.question
    assert result.allow_custom_input == False

@pytest.mark.asyncio
async def test_hitl_node_basic():
    from src.graph.nodes import hitl_node
    state = {
        "user_feedback": {"selected_value": "impressions,clicks"},
        "clarification_count": 0
    }
    result = await hitl_node(state)
    assert result["clarification_count"] == 1
    assert result["user_feedback"] is not None
