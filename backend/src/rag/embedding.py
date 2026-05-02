import os
# 禁用 tokenizers 的并行性，避免 forking 导致的问题
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from abc import ABC, abstractmethod
from typing import List
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

from .config import (
    EMBEDDING_PROVIDER,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    OPENAI_API_KEY,
    ARK_BASE_URL,
    ARK_API_KEY,
    ARK_EMBEDDING_MODEL,
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


class ArkEmbeddingProvider(EmbeddingProvider):
    """火山引擎 Ark Embedding 实现

    复用 ANTHROPIC_AUTH_TOKEN 和 ANTHROPIC_BASE_URL 环境变量
    """

    def __init__(self):
        if not ARK_API_KEY:
            raise ValueError("ANTHROPIC_AUTH_TOKEN 或 ANTHROPIC_API_KEY 未设置")

        # 直接使用 OpenAI SDK 避免 LangChain 的 tokenization 问题
        from openai import OpenAI
        self.client = OpenAI(api_key=ARK_API_KEY, base_url=ARK_BASE_URL)
        self.model = ARK_EMBEDDING_MODEL

    def embed(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(input=text, model=self.model)
        return resp.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        resp = self.client.embeddings.create(input=texts, model=self.model)
        return [r.embedding for r in resp.data]


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """本地 HuggingFace Embedding 实现（离线可用）

    使用 BAAI/bge-small-zh 模型，向量维度 512
    """

    def __init__(self):
        self.client = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-zh",
            model_kwargs={"device": "cpu"},
        )

    def embed(self, text: str) -> List[float]:
        return self.client.embed_query(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return self.client.embed_documents(texts)


# 单例缓存
_embedding_provider_instance: EmbeddingProvider = None


def get_embedding_provider() -> EmbeddingProvider:
    """获取 embedding provider 实例（单例模式，避免重复加载模型）"""
    global _embedding_provider_instance
    if _embedding_provider_instance is None:
        if EMBEDDING_PROVIDER == "openai":
            _embedding_provider_instance = OpenAIEmbeddingProvider()
        elif EMBEDDING_PROVIDER == "ark":
            _embedding_provider_instance = ArkEmbeddingProvider()
        elif EMBEDDING_PROVIDER == "local":
            _embedding_provider_instance = HuggingFaceEmbeddingProvider()
        else:
            raise ValueError(f"不支持的 embedding provider: {EMBEDDING_PROVIDER}")
    return _embedding_provider_instance
