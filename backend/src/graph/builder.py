from langgraph.graph import StateGraph, END
from .state import AdReportState
from .nodes import nlu_node, hitl_node, planner_node, executor_node, insight_node, analyst_node, reporter_node, advertiser_handle_node

def build_graph():
    """构建完整的 LangGraph 流程图"""
    graph = StateGraph(AdReportState)

    # 添加节点
    graph.add_node("nlu", nlu_node)
    graph.add_node("hitl", hitl_node)
    graph.add_node("advertiser_handle", advertiser_handle_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("insight", insight_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("reporter", reporter_node)

    # 设置入口
    graph.set_entry_point("nlu")

    # NLU -> 条件判断：广告主处理 / 澄清 / Planner
    def route_after_nlu(state: dict) -> str:
        ambiguity = state.get("ambiguity", {})
        if ambiguity and ambiguity.get("has_ambiguity", False):
            return "hitl"

        query_intent = state.get("query_intent", {})
        if query_intent.get("show_advertiser_list", False) or query_intent.get("need_advertiser_selection", False):
            return "advertiser_handle"

        return "planner"

    graph.add_conditional_edges(
        "nlu",
        route_after_nlu,
        {"hitl": "hitl", "advertiser_handle": "advertiser_handle", "planner": "planner"}
    )

    # advertiser_handle -> 结束（直接返回列表或提示）
    graph.add_edge("advertiser_handle", END)

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

    # Executor -> Insight -> Analyst
    graph.add_edge("executor", "insight")
    graph.add_edge("insight", "analyst")

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

    return graph.compile(interrupt_before=["hitl"])

# 导出编译好的Graph
app = build_graph()
