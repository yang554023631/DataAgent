from langgraph.graph import StateGraph, END
from .state import AdReportState
from .nodes import (
    nlu_node, hitl_node, planner_node, executor_node, insight_node, analyst_node, reporter_node, advertiser_handle_node,
    intent_classifier_node, report_intent_node, clarify_node_entry, reject_node_entry
)
from src.rag.agents import rag_retrieve_node, rag_answer_node

def build_graph():
    """构建完整的 LangGraph 流程图（新意图识别架构）"""
    graph = StateGraph(AdReportState)

    # ========== 添加所有节点 ==========
    # 新意图识别节点
    graph.add_node("intent_classifier", intent_classifier_node)
    graph.add_node("report_intent", report_intent_node)
    graph.add_node("clarify", clarify_node_entry)
    graph.add_node("reject", reject_node_entry)

    # 保留原有的 RAG 和报表下游节点
    graph.add_node("rag_retrieve", rag_retrieve_node)
    graph.add_node("rag_generate_answer", rag_answer_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("insight", insight_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("reporter", reporter_node)

    # 保留旧节点（向后兼容，暂不删除）
    graph.add_node("advertiser_handle", advertiser_handle_node)

    # ========== 设置入口 ==========
    graph.set_entry_point("intent_classifier")

    # ========== 1. 顶层分类后的路由 ==========
    def route_after_intent_classifier(state: dict) -> str:
        """
        intent_classifier 之后的条件路由：
        - report → report_intent
        - knowledge → rag_retrieve
        - out_of_domain → reject
        - needs_clarification → clarify
        """
        if state.get("needs_clarification", False):
            return "clarify"

        category = state.get("intent_category", "report")
        if category == "report":
            return "report_intent"
        elif category == "knowledge":
            return "rag_retrieve"
        else:  # out_of_domain
            return "reject"

    graph.add_conditional_edges(
        "intent_classifier",
        route_after_intent_classifier,
        {
            "report_intent": "report_intent",
            "rag_retrieve": "rag_retrieve",
            "reject": "reject",
            "clarify": "clarify",
        }
    )

    # ========== 2. 报表意图后的路由 ==========
    def route_after_report_intent(state: dict) -> str:
        """
        report_intent 之后的条件路由：
        - needs_clarification → clarify
        - 信息完整 → planner
        """
        if state.get("needs_clarification", False):
            return "clarify"
        return "planner"

    graph.add_conditional_edges(
        "report_intent",
        route_after_report_intent,
        {
            "clarify": "clarify",
            "planner": "planner",
        }
    )

    # ========== 3. 澄清后的路由 ==========
    def route_after_clarify(state: dict) -> str:
        """
        clarify 之后的条件路由：
        - reentry_top → intent_classifier
        - continue_report → report_intent
        - continue_knowledge → rag_retrieve
        - max_reentry_exceeded → reject（重置）
        """
        clarify_next = state.get("clarify_next", "reentry_top")

        if clarify_next == "reentry_top":
            return "intent_classifier"
        elif clarify_next == "continue_report":
            return "report_intent"
        elif clarify_next == "continue_knowledge":
            return "rag_retrieve"
        else:  # max_reentry_exceeded
            # 重置 reject_reason
            state["reject_reason"] = "top_level"
            return "reject"

    graph.add_conditional_edges(
        "clarify",
        route_after_clarify,
        {
            "intent_classifier": "intent_classifier",
            "report_intent": "report_intent",
            "rag_retrieve": "rag_retrieve",
            "reject": "reject",
        }
    )

    # ========== 4. RAG 流程 ==========
    graph.add_edge("rag_retrieve", "rag_generate_answer")
    graph.add_edge("rag_generate_answer", END)

    # ========== 5. 报表下游流程（保持不变） ==========
    # Planner -> Executor -> Insight -> Analyst -> Reporter
    graph.add_edge("planner", "executor")
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

    graph.add_edge("reporter", END)

    # ========== 6. 拒答流程 ==========
    graph.add_edge("reject", END)

    # ========== 编译（interrupt_before 改为 clarify） ==========
    return graph.compile(interrupt_before=["clarify"])

# 导出编译好的 Graph
app = build_graph()
