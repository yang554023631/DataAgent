import logging
import asyncio
from typing import Optional, Literal, Type
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from src.rag.agents import get_llm

logger = logging.getLogger(__name__)

# 单例缓存
_intent_llm_instance: Optional["IntentLLMClient"] = None
_dsl_lite_llm_instance: Optional["IntentLLMClient"] = None


def get_fallback_classifier() -> Optional[callable]:
    """获取降级用的纯规则分类器引用，当前返回占位符"""
    return None


class IntentLLMClient:
    """LLM 调用客户端，封装重试逻辑"""

    def __init__(
        self,
        llm: ChatOpenAI = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        self.llm = llm or get_llm()
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
        schema: Optional[Type[BaseModel]] = None,
    ) -> str:
        """
        调用 LLM，支持重试

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入提示词
            json_mode: 是否期望 JSON 输出
            schema: 如果提供，则使用 json_schema 模式强制输出符合该pydantic模型结构，None则：
                - json_mode=True → 用 json_object 模式（只要求合法JSON，不约束结构）
                - json_mode=False → 普通文本输出

        Returns:
            LLM 响应文本（已strip）

        Raises:
            Exception: 所有重试都失败时抛出最后一次异常
        """
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                # 直接调用 LLM，不使用 ChatPromptTemplate 以避免花括号解析问题
                from langchain_core.messages import SystemMessage, HumanMessage
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
                response = await self.llm.ainvoke(messages)
                content = response.content.strip()

                if attempt > 1:
                    logger.info(f"LLM调用成功（第{attempt}次重试）")
                return content

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"LLM调用失败（第{attempt}/{self.max_retries}次）: {e}"
                )
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        # 所有重试都失败
        logger.error(f"LLM调用全部失败（共{self.max_retries}次）: {last_exception}")
        raise last_exception


def get_intent_llm_client() -> "IntentLLMClient":
    """获取意图识别 LLM 客户端单例（主模型，用于意图理解、查询规划等复杂任务）"""
    global _intent_llm_instance
    if _intent_llm_instance is None:
        _intent_llm_instance = IntentLLMClient()
    return _intent_llm_instance


def get_dsl_lite_llm_client() -> "IntentLLMClient":
    """获取 DSL 生成专用的轻量模型客户端单例

    使用 doubao-seed-2.0-lite 等较小模型，专用于 DSL 生成这类格式明确的任务，
    以降低延迟。查询规划等需要强理解能力的任务仍使用主模型。
    """
    global _dsl_lite_llm_instance
    if _dsl_lite_llm_instance is None:
        from langchain_openai import ChatOpenAI
        from src.rag.config import ARK_API_KEY, ARK_BASE_URL, ARK_LITE_MODEL

        if ARK_LITE_MODEL and ARK_API_KEY:
            lite_llm = ChatOpenAI(
                model=ARK_LITE_MODEL,
                api_key=ARK_API_KEY,
                base_url=ARK_BASE_URL,
                temperature=0,
            )
            _dsl_lite_llm_instance = IntentLLMClient(llm=lite_llm)
        else:
            # 降级：没有配置轻量模型就用主模型
            logger.warning("未配置 ARK_LITE_MODEL，降级使用主模型进行 DSL 生成")
            _dsl_lite_llm_instance = get_intent_llm_client()
    return _dsl_lite_llm_instance
