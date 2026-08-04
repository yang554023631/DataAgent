import pytest
from langgraph.graph import StateGraph, END

from src.graph.callbacks import LoggingHandler


def test_logging_handler_node_start_end(caplog):
    """节点进入和离开时打日志"""
    # 构建一个简单的 graph
    def node_a(state):
        return {"value": state.get("value", 0) + 1}

    graph = StateGraph(dict)
    graph.add_node("a", node_a)
    graph.set_entry_point("a")
    graph.add_edge("a", END)

    app = graph.compile()

    handler = LoggingHandler()

    with caplog.at_level("INFO"):
        result = app.invoke({"value": 0}, config={"callbacks": [handler]})

    assert result["value"] == 1

    # 检查日志中包含节点进入和离开
    messages = [r.message for r in caplog.records]
    assert any("进入节点: a" in m for m in messages)
    assert any("离开节点: a" in m for m in messages)
    # 离开日志包含耗时
    assert any("耗时" in m and "ms" in m for m in messages if "离开节点" in m)


def test_logging_handler_node_error(caplog):
    """节点异常时打 ERROR 日志"""
    def bad_node(state):
        raise ValueError("something went wrong")

    graph = StateGraph(dict)
    graph.add_node("bad", bad_node)
    graph.set_entry_point("bad")
    graph.add_edge("bad", END)

    app = graph.compile()
    handler = LoggingHandler()

    with caplog.at_level("ERROR"):
        with pytest.raises(ValueError, match="something went wrong"):
            app.invoke({}, config={"callbacks": [handler]})

    messages = [r.message for r in caplog.records]
    assert any("节点异常" in m and "bad" in m for m in messages)


def test_logging_handler_does_not_affect_flow():
    """回调异常不影响主流程"""
    call_count = {"n": 0}

    def node_a(state):
        call_count["n"] += 1
        return {"ok": True}

    graph = StateGraph(dict)
    graph.add_node("a", node_a)
    graph.set_entry_point("a")
    graph.add_edge("a", END)

    app = graph.compile()

    # 正常 handler
    handler = LoggingHandler()
    result = app.invoke({}, config={"callbacks": [handler]})
    assert result["ok"] is True
    assert call_count["n"] == 1
