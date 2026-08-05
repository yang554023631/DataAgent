"""
通用澄清节点

职责：
1. 接收用户的澄清反馈
2. 检测用户是否改变了意图类别（触发回退）
3. 设置下一步路由方向（回第一层 / 继续第二层报表 / 继续第二层知识）

注意：
- 此节点之前 graph 会 interrupt（interrupt_before=["clarify"]）
- 用户反馈通过 user_feedback 字段传入
- 此节点不做实际的重新识别，只设置路由方向和合并反馈到 user_input
  重新识别由后续节点完成
"""
import json
import logging
from typing import Optional, Tuple

from src.intent.llm_client import get_intent_llm_client, IntentLLMClient
from src.intent.prompts import REENTRY_DETECT_SYSTEM_PROMPT
from src.intent.models import ClarificationInfo

logger = logging.getLogger(__name__)

# 最大回退次数
MAX_REENTRY_COUNT = 3


def build_clarification_state(clarification: ClarificationInfo) -> dict:
    """
    构建澄清状态（写入 state 供 interrupt 时前端展示）

    由各识别节点在需要澄清时调用，设置 needs_clarification=True
    这样 graph 到 clarify 节点前会中断，等待用户输入
    """
    return {
        "needs_clarification": True,
        "clarification": {
            "type": clarification.type,
            "question": clarification.question,
            "options": clarification.options,
            "allow_custom_input": clarification.allow_custom_input,
            "missing_fields": clarification.missing_fields,
        },
    }


async def detect_intent_change(
    user_feedback: str,
    current_category: str,
    original_input: str,
    llm_client: IntentLLMClient = None,
) -> Tuple[bool, Optional[str]]:
    """
    检测用户澄清反馈是否改变了意图类别

    Args:
        user_feedback: 用户最新的澄清反馈
        current_category: 当前意图类别（report / knowledge）
        original_input: 用户最初的输入
        llm_client: LLM 客户端（测试用）

    Returns:
        (是否改变, 新的类别)
    """
    if llm_client is None:
        llm_client = get_intent_llm_client()

    system_prompt = REENTRY_DETECT_SYSTEM_PROMPT.format(
        current_category=current_category,
        original_input=original_input,
        user_feedback=user_feedback,
    )

    try:
        response = await llm_client.call(
            system_prompt=system_prompt,
            user_prompt="请判断意图是否变化。",
            json_mode=True,
        )
        data = json.loads(response)
        has_changed = data.get("has_changed", False)
        new_category = data.get("new_category")

        if has_changed and new_category in ["report", "knowledge"]:
            logger.info(
                f"意图回退检测: 变化={has_changed}, "
                f"原分类={current_category}, 新分类={new_category}, "
                f"原因={data.get('reason', '')}"
            )
            return True, new_category

        return False, None

    except Exception as e:
        logger.warning(f"意图回退检测失败: {e}，默认不回退")
        return False, None


async def clarify_node(state: dict) -> dict:
    """
    LangGraph 澄清处理节点

    执行逻辑：
    1. 读取用户反馈（user_feedback）
    2. 检测是否触发意图回退
    3. 设置下一步路由方向
    4. 将用户反馈合并到 user_input 中（供后续重新识别使用）

    路由方向通过 clarify_next 字段表示：
    - "reentry_top": 回退到第一层重新分类
    - "continue_report": 继续第二层报表识别
    - "continue_knowledge": 继续第二层知识识别
    - "max_reentry_exceeded": 超过最大回退次数，重置
    """
    user_feedback_dict = state.get("user_feedback", {})
    user_feedback_text = (
        user_feedback_dict.get("selected_value", "")
        if isinstance(user_feedback_dict, dict)
        else str(user_feedback_dict)
    )
    current_category = state.get("intent_category", "report")
    original_input = state.get("user_input", "")
    reentry_count = state.get("reentry_count", 0)
    clarification_count = state.get("clarification_count", 0) + 1
    clarification_type = state.get("clarification", {}).get("type", "")

    logger.info(
        f"澄清处理: 类型={clarification_type}, 反馈='{user_feedback_text[:50]}', "
        f"当前分类={current_category}, 回退次数={reentry_count}"
    )

    result_updates = {
        "clarification_count": clarification_count,
        "needs_clarification": False,
    }

    # 合并用户反馈到 user_input（供后续重新识别使用）
    # 策略：把用户反馈作为新的 user_input，同时保留原始输入在 pending_clarification_input 中
    result_updates["pending_clarification_input"] = user_feedback_text
    # 也更新 user_input，让下游节点直接拿到最新的用户输入
    result_updates["user_input"] = user_feedback_text

    # 检测意图变化（只在非顶层澄清时检测）
    if clarification_type != "intent_confirm" and current_category in ["report", "knowledge"]:
        has_changed, new_category = await detect_intent_change(
            user_feedback_text, current_category, original_input
        )

        if has_changed and new_category:
            # 检查是否超过最大回退次数
            if reentry_count >= MAX_REENTRY_COUNT:
                logger.warning(f"超过最大回退次数({MAX_REENTRY_COUNT})，重置会话")
                result_updates["clarify_next"] = "max_reentry_exceeded"
                return result_updates

            # 触发回退
            result_updates["intent_category"] = new_category
            result_updates["reentry_count"] = reentry_count + 1
            result_updates["clarify_next"] = "reentry_top"
            logger.info(
                f"触发意图回退: {current_category} → {new_category}, "
                f"回退次数={reentry_count + 1}/{MAX_REENTRY_COUNT}"
            )
            return result_updates

    # 没有回退，继续当前层
    if current_category == "report":
        result_updates["clarify_next"] = "continue_report"
    elif current_category == "knowledge":
        result_updates["clarify_next"] = "continue_knowledge"
    else:
        result_updates["clarify_next"] = "reentry_top"

    return result_updates