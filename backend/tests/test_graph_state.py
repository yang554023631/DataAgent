import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.graph.state import AdReportState

def test_state_initialization():
    state: AdReportState = {
        "session_id": "test-123",
        "user_id": "user-456",
        "user_input": "看上周的曝光",
        "conversation_history": [],
        "query_intent": None,
        "ambiguity": None,
        "user_feedback": None,
        "clarification_count": 0,
        "query_request": None,
        "query_warnings": [],
        "query_result": None,
        "execution_time_ms": None,
        "analysis_result": None,
        "drill_down_level": 0,
        "needs_drill_down": False,
        "final_report": None,
        "error": None
    }
    assert state["session_id"] == "test-123"
    assert state["user_input"] == "看上周的曝光"

def test_append_history_reducer():
    from src.graph.state import append_history

    left = [{"role": "user", "content": "hello"}]
    right = [{"role": "assistant", "content": "hi"}]
    result = append_history(left, right)

    assert len(result) == 2
    assert result[0]["content"] == "hello"
    assert result[1]["content"] == "hi"
