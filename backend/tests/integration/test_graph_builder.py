"""
Tests for the graph builder with analysis_node integration.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.graph.builder import build_graph


def test_graph_compiles():
    """Test that the graph compiles successfully with analysis_node."""
    app = build_graph()
    assert app is not None


def test_graph_structure():
    """Simplified test to verify the graph can be built without errors."""
    # The main test is that build_graph() doesn't raise exceptions
    # This verifies all imports work and nodes are registered correctly
    app = build_graph()
    assert app is not None


@pytest.mark.asyncio
async def test_analysis_node_import():
    """Test that analysis_node can be imported and used."""
    from src.graph.nodes import analysis_node
    assert analysis_node is not None
    assert callable(analysis_node)


@pytest.mark.asyncio
async def test_clarify_node_sets_continue_analysis():
    """Test that clarify_node sets clarify_next=continue_analysis for analysis clarifications."""
    from src.intent.clarify_node import clarify_node

    # Test with cot_clarification type
    state = {
        "user_feedback": "test feedback",
        "clarification": {"type": "cot_clarification"},
        "intent_category": "report",
        "user_input": "original input"
    }

    result = await clarify_node(state)
    assert result["clarify_next"] == "continue_analysis"

    # Test with quality_hitl type
    state = {
        "user_feedback": "test feedback",
        "clarification": {"type": "quality_hitl"},
        "intent_category": "report",
        "user_input": "original input"
    }

    result = await clarify_node(state)
    assert result["clarify_next"] == "continue_analysis"
