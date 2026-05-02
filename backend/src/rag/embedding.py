from abc import ABC, abstractmethod
from typing import List
from langchain_openai import OpenAIEmbeddings

from .config import (
    EMBEDDING_PROVIDER,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    OPENAI_API_KEY,
)


class EmbeddingProvider(ABC):
    """向量生成抽象基类"""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """生成单个文本的向量"""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成向量"""
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI Embedding 实现"""

    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY 未设置")
        self.client = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY,
            dimensions=EMBEDDING_DIMENSIONS,
        )

    def embed(self, text: str) -> List[float]:
        return self.client.embed_query(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return self.client.embed_documents(texts)


def get_embedding_provider() -> EmbeddingProvider:
    """获取 embedding provider 实例"""
    if EMBEDDING_PROVIDER == "openai":
        return OpenAIEmbeddingProvider()
    raise ValueError(f"不支持的 embedding provider: {EMBEDDING_PROVIDER}")
