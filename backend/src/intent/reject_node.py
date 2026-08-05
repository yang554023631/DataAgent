"""
拒答节点 — 当用户问题超出广告领域时，返回礼貌的拒绝话术
"""
import logging

logger = logging.getLogger(__name__)

# 拒答话术模板
REJECT_MESSAGES = {
    "top_level": (
        "抱歉，我只能回答广告相关的问题（包括广告数据查询和广告知识问答）。"
        "其他领域的问题我暂时回答不了。"
    ),
    "knowledge_scope": (
        "抱歉，这个问题我回答不了。请在广告相关的范围内提问。"
    ),
}


def build_reject_response(reason: str = "top_level") -> dict:
    """
    构建拒答的 final_report

    Args:
        reason: 拒答原因类型（top_level / knowledge_scope）

    Returns:
        final_report 格式的 dict
    """
    message = REJECT_MESSAGES.get(reason, REJECT_MESSAGES["top_level"])

    # 给一些引导建议
    suggestions = [
        "查看广告数据报表（曝光、点击、消耗、转化等）",
        "了解广告指标概念（什么是 CTR / CPA / ROI）",
        "咨询广告优化策略（冷启动、素材优化、出价调整）",
    ]

    highlights = [
        {"type": "info", "text": message},
        {"type": "info", "text": "💡 我可以帮你："},
    ]
    for s in suggestions:
        highlights.append({"type": "info", "text": f"  • {s}"})

    return {
        "title": "抱歉，这个问题我回答不了",
        "time_range": {"start": "", "end": ""},
        "metrics": [],
        "highlights": highlights,
        "data_table": {"columns": [], "rows": []},
        "next_queries": [
            "昨天的曝光点击消耗",
            "什么是 CTR",
            "冷启动跑不动怎么办",
        ],
    }


async def reject_node(state: dict) -> dict:
    """
    LangGraph 拒答节点

    从 state 中读取拒答原因，生成拒答响应并写入 final_report
    """
    reject_reason = state.get("reject_reason", "top_level")
    user_input = state.get("user_input", "")

    logger.info(f"拒答: 原因={reject_reason}, 用户输入='{user_input[:50]}'")

    final_report = build_reject_response(reject_reason)

    return {
        "final_report": final_report,
        "error": None,
    }

__all__ = ["build_reject_response", "reject_node"]