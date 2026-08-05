import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_openai import ChatOpenAI
from openai import APIError, APITimeoutError, RateLimitError
from typing import Any, Optional

from ..rag.config import OPENAI_API_KEY, ARK_BASE_URL, ARK_API_KEY, ARK_LLM_MODEL

logger = logging.getLogger(__name__)

# 单例缓存
_intent_llm_instance: 'IntentLLMClient' = None


class IntentLLMClient:
    """意图识别用 LLM 客户端，带重试逻辑"""

    def __init__(self):
        self.llm = self._create_llm()

    def _create_llm(self) -> ChatOpenAI:
        """创建 LLM 实例，优先使用火山引擎 Ark"""
        if ARK_LLM_MODEL and ARK_API_KEY:
            logger.info("创建火山引擎 Ark LLM 实例")
            return ChatOpenAI(
                model=ARK_LLM_MODEL,
                api_key=ARK_API_KEY,
                base_url=ARK_BASE_URL,
                temperature=0,
            )
        else:
            logger.info("创建默认 GPT-3.5-turbo LLM 实例")
            return ChatOpenAI(
                model="gpt-3.5-turbo",
                api_key=OPENAI_API_KEY,
                temperature=0,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((APIError, APITimeoutError, RateLimitError)),
    )
    def invoke(self, *args, **kwargs) -> Any:
        """调用 LLM，带重试机制"""
        logger.info("调用 LLM 客户端")
        return self.llm.invoke(*args, **kwargs)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((APIError, APITimeoutError, RateLimitError)),
    )
    async def ainvoke(self, *args, **kwargs) -> Any:
        """异步调用 LLM 客户端，带重试机制"""
        logger.info("异步调用 LLM 客户端")
        return await self.llm.ainvoke(*args, **kwargs)


def get_intent_llm_client() -> IntentLLMClient:
    """获取意图识别 LLM 客户端单例"""
    global _intent_llm_instance
    if _intent_llm_instance is None:
        _intent_llm_instance = IntentLLMClient()
    return _intent_llm_instance