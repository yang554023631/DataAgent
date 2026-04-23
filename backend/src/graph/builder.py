from langgraph.graph import StateGraph, END
from .state import AdReportState
from .nodes import nlu_node, hitl_node, planner_node, executor_node, analyst_node, reporter_node

def build_graph():
    """构建完整的 LangGraph 流程图"""
    graph = StateGraph(AdReportState)

    # 添加节点
    graph.add_node("nlu", nlu_node)
    graph.add_node("hitl", hitl_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("reporter", reporter_node)

    # 设置入口
    graph.set_entry_point("nlu")

    # NLU -> 条件判断
    def need_clarification_after_nlu(state: dict) -> str:
        ambiguity = state.get("ambiguity", {})
        if ambiguity and ambiguity.get("has_ambiguity", False):
            return "hitl"
        return "planner"

    graph.add_conditional_edges(
        "nlu",
        need_clarification_after_nlu,
        {"hitl": "hitl", "planner": "planner"}
    )

    # HITL -> 回到 NLU 重新理解
    graph.add_edge("hitl", "nlu")

    # Planner -> 条件判断（可能也需要确认）
    def need_confirm_after_planner(state: dict) -> str:
        warnings = state.get("query_warnings", [])
        # 如果有需要用户确认的警告，去HITL
        for warning in warnings:
            if "need_confirm" in warning:
                return "hitl"
        return "executor"

    graph.add_conditional_edges(
        "planner",
        need_confirm_after_planner,
        {"hitl": "hitl", "executor": "executor"}
    )

    # Executor -> Analyst
    graph.add_edge("executor", "analyst")

    # Analyst -> 条件判断（是否需要下钻）
    def need_drill_down(state: dict) -> str:
        if state.get("needs_drill_down", False):
            return "planner"
        return "reporter"

    graph.add_conditional_edges(
        "analyst",
        need_drill_down,
        {"planner": "planner", "reporter": "reporter"}
    )

    # Reporter -> 结束
    graph.add_edge("reporter", END)

    return graph.compile()

# 导出编译好的Graph
app = build_graph()
