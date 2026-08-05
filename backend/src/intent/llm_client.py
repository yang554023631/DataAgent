import logging
import asyncio
from typing import Optional, Literal
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from src.rag.agents import get_llm

logger = logging.getLogger(__name__)

# 单例缓存
_intent_llm_instance: Optional["IntentLLMClient"] = None


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
    ) -> str:
        """
        调用 LLM，支持重试

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入提示词
            json_mode: 是否期望 JSON 输出（仅用于日志和提示，不强制结构化输出）

        Returns:
            LLM 响应文本（已strip）

        Raises:
            Exception: 所有重试都失败时抛出最后一次异常
        """
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", user_prompt),
                ])
                chain = prompt | self.llm
                response = await chain.ainvoke({})
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
    """获取意图识别 LLM 客户端单例"""
    global _intent_llm_instance
    if _intent_llm_instance is None:
        _intent_llm_instance = IntentLLMClient()
    return _intent_llm_instance
