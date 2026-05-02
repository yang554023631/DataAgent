"""
RAG 工作流集成模块

使用方法：
1. 将此模块中的节点和路由函数集成到主工作流
2. 在 State 中添加 query_type, rag_context, rag_answer 字段
"""
from typing import TypedDict, List, Literal
from langgraph.graph import StateGraph, END

from .agents import intent_router_node, rag_retrieve_node, rag_answer_node


# 建议扩展的 State 定义
class RAGEnabledState(TypedDict, total=False):
    """支持 RAG 的工作流 State 扩展"""
    # 原有字段保持...
    user_input: str

    # 新增 RAG 字段
    query_type: Literal["report", "knowledge"]
    rag_context: List[str]
    rag_answer: str


def route_based_on_intent(state: dict) -> str:
    """根据意图类型路由"""
    query_type = state.get("query_type", "report")
    if query_type == "knowledge":
        return "rag_retrieve"
    # 报表查询走原有流程
    return "intent_classification"


def build_rag_enabled_workflow(base_workflow_builder=None):
    """
    构建支持 RAG 的工作流

    示例用法：
    builder = build_rag_enabled_workflow(existing_builder)
    app = builder.compile()
    """
    builder = base_workflow_builder or StateGraph(RAGEnabledState)

    # 添加 RAG 节点
    builder.add_node("intent_router", intent_router_node)
    builder.add_node("rag_retrieve", rag_retrieve_node)
    builder.add_node("rag_answer", rag_answer_node)

    # 设置入口点为意图路由
    builder.set_entry_point("intent_router")

    # 添加条件分支
    builder.add_conditional_edges(
        "intent_router",
        route_based_on_intent,
        {
            "rag_retrieve": "rag_retrieve",
            "intent_classification": "intent_classification",
        },
    )

    # RAG 流程
    builder.add_edge("rag_retrieve", "rag_answer")
    builder.add_edge("rag_answer", END)

    return builder
