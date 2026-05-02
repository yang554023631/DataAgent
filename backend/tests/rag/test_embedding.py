import os
import pytest
import numpy as np
from unittest.mock import Mock, patch

from src.rag.embedding import get_embedding_provider, OpenAIEmbeddingProvider, ArkEmbeddingProvider, EmbeddingProvider


def test_embedding_provider_abc():
    """测试 EmbeddingProvider 抽象基类"""
    assert EmbeddingProvider.__abstractmethods__ == {"embed", "embed_batch"}


def test_embedding_provider_factory():
    """测试 embedding provider 工厂函数"""
    with patch("src.rag.embedding.OpenAIEmbeddings"), patch("src.rag.embedding.OPENAI_API_KEY", "test-key"):
        provider = get_embedding_provider()
        assert provider is not None
        assert isinstance(provider, OpenAIEmbeddingProvider)


def test_openai_provider_initialization():
    """测试 OpenAI provider 初始化"""
    with patch("src.rag.embedding.OpenAIEmbeddings") as mock_embeddings, patch("src.rag.embedding.OPENAI_API_KEY", "test-key"):
        provider = OpenAIEmbeddingProvider()
        mock_embeddings.assert_called_once()
        call_kwargs = mock_embeddings.call_args[1]
        assert call_kwargs["api_key"] == "test-key"


def test_embedding_dimensions():
    """测试向量维度返回（使用mock）"""
    with patch("src.rag.embedding.OpenAIEmbeddings") as mock_embeddings_class, patch("src.rag.embedding.OPENAI_API_KEY", "test-key"):
        mock_instance = Mock()
        mock_instance.embed_query.return_value = [0.1] * 1536
        mock_embeddings_class.return_value = mock_instance

        provider = get_embedding_provider()
        text = "这是一个测试文本"
        embedding = provider.embed(text)

        assert embedding is not None
        assert len(embedding) == 1536
        assert isinstance(embedding, list)
        assert all(isinstance(x, float) for x in embedding)


def test_batch_embedding():
    """测试批量生成向量（使用mock）"""
    with patch("src.rag.embedding.OpenAIEmbeddings") as mock_embeddings_class, patch("src.rag.embedding.OPENAI_API_KEY", "test-key"):
        mock_instance = Mock()
        mock_instance.embed_documents.return_value = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
        mock_embeddings_class.return_value = mock_instance

        provider = get_embedding_provider()
        texts = ["文本1", "文本2", "文本3"]
        embeddings = provider.embed_batch(texts)

        assert len(embeddings) == 3
        assert all(len(e) == 1536 for e in embeddings)


def test_embedding_consistency():
    """测试相同输入生成相同向量（使用mock）"""
    with patch("src.rag.embedding.OpenAIEmbeddings") as mock_embeddings_class, patch("src.rag.embedding.OPENAI_API_KEY", "test-key"):
        mock_instance = Mock()
        mock_instance.embed_query.return_value = [0.12345] * 1536
        mock_embeddings_class.return_value = mock_instance

        provider = get_embedding_provider()
        text = "相同的输入"
        e1 = provider.embed(text)
        e2 = provider.embed(text)

        assert np.allclose(np.array(e1), np.array(e2), atol=1e-6)


def test_missing_api_key():
    """测试未设置 API key 时抛出错误"""
    with patch("src.rag.embedding.OPENAI_API_KEY", ""):
        with pytest.raises(ValueError, match="OPENAI_API_KEY 未设置"):
            OpenAIEmbeddingProvider()


def test_ark_provider_factory():
    """测试 Ark embedding provider 工厂函数"""
    with patch("src.rag.embedding.OpenAIEmbeddings"), \
         patch("src.rag.embedding.ARK_API_KEY", "test-ark-key"), \
         patch("src.rag.embedding.EMBEDDING_PROVIDER", "ark"):
        provider = get_embedding_provider()
        assert provider is not None
        assert isinstance(provider, ArkEmbeddingProvider)


def test_ark_provider_initialization():
    """测试 Ark provider 初始化 - 复用 ANTHROPIC 配置"""
    with patch("src.rag.embedding.OpenAIEmbeddings") as mock_embeddings, \
         patch("src.rag.embedding.ARK_API_KEY", "test-ark-key"), \
         patch("src.rag.embedding.ARK_BASE_URL", "https://ark.test.com/api/v3"), \
         patch("src.rag.embedding.ARK_EMBEDDING_MODEL", "doubao-embedding-v1"):
        provider = ArkEmbeddingProvider()
        mock_embeddings.assert_called_once()
        call_kwargs = mock_embeddings.call_args[1]
        assert call_kwargs["api_key"] == "test-ark-key"
        assert call_kwargs["base_url"] == "https://ark.test.com/api/v3"
        assert call_kwargs["model"] == "doubao-embedding-v1"


def test_ark_missing_api_key():
    """测试 Ark 未设置 API key 时抛出错误"""
    with patch("src.rag.embedding.ARK_API_KEY", ""):
        with pytest.raises(ValueError, match="ANTHROPIC_AUTH_TOKEN 或 ANTHROPIC_API_KEY 未设置"):
            ArkEmbeddingProvider()


def test_ark_embedding_dimensions():
    """测试 Ark 向量维度返回（使用mock）"""
    with patch("src.rag.embedding.OpenAIEmbeddings") as mock_embeddings_class, \
         patch("src.rag.embedding.ARK_API_KEY", "test-ark-key"):
        mock_instance = Mock()
        mock_instance.embed_query.return_value = [0.1] * 2048  # doubao 模型是 2048 维
        mock_embeddings_class.return_value = mock_instance

        provider = ArkEmbeddingProvider()
        text = "这是一个测试文本"
        embedding = provider.embed(text)

        assert embedding is not None
        assert len(embedding) == 2048
        assert isinstance(embedding, list)


def test_invalid_provider():
    """测试无效 provider 抛出错误"""
    with patch("src.rag.embedding.EMBEDDING_PROVIDER", "invalid"):
        with pytest.raises(ValueError, match="不支持的 embedding provider: invalid"):
            get_embedding_provider()
