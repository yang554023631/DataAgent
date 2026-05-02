import os
# 禁用 tokenizers 的并行性，避免 forking 导致的 LLM API 调用问题
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

# 强制 CrossEncoder 使用 CPU，避免 MPS 显存溢出
os.environ['CUDA_VISIBLE_DEVICES'] = ''

from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .config import RETRIEVE_TOP_K, RERANKER_MODEL, RERANKER_TOP_N
from .embedding import get_embedding_provider
from .models import RagChunk, RagDocument

# CrossEncoder 单例 - 只初始化一次，避免显存泄漏
_reranker_instance = None

def get_reranker_instance(model_name: str = None):
    """获取 CrossEncoder 单例（避免重复初始化导致显存泄漏）"""
    global _reranker_instance
    if _reranker_instance is None:
        if not HAS_SENTENCE_TRANSFORMERS:
            raise ImportError(
                "sentence-transformers is required for Reranker. "
                "Install with: pip install sentence-transformers"
            )
        _reranker_instance = CrossEncoder(
            model_name or RERANKER_MODEL,
            device='cpu'  # 强制使用 CPU，避免 MPS 显存问题
        )
    return _reranker_instance

try:
    from sentence_transformers import CrossEncoder
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


@dataclass
class RetrievalResult:
    """检索结果数据类"""
    chunk_id: str
    doc_id: str
    content: str
    score: float
    title: Optional[str] = None
    doc_type: Optional[str] = None


class VectorRetriever:
    """向量检索器"""

    def __init__(self, top_k: int = None):
        self.top_k = top_k or RETRIEVE_TOP_K
        self.embedding_provider = get_embedding_provider()

    def retrieve(
        self,
        query: str,
        db_session: Session,
        doc_type: Optional[str] = None,
    ) -> List[RetrievalResult]:
        """
        向量检索相关文档分片

        Args:
            query: 查询问题
            db_session: 数据库会话
            doc_type: 可选，按文档类型过滤

        Returns:
            按相似度排序的检索结果列表
        """
        # 生成查询向量
        query_embedding = self.embedding_provider.embed(query)

        # 构建查询 - 使用余弦相似度
        q = db_session.query(
            RagChunk.id,
            RagChunk.doc_id,
            RagChunk.content,
            RagDocument.title,
            RagDocument.doc_type,
            (1 - RagChunk.embedding.cosine_distance(query_embedding)).label("score"),
        ).join(RagDocument, RagChunk.doc_id == RagDocument.id)

        # 可选过滤
        if doc_type:
            q = q.filter(RagDocument.doc_type == doc_type)

        # 按相似度排序，取 top_k
        results = q.order_by(desc("score")) \
                    .limit(self.top_k) \
                    .all()

        # 转换为 RetrievalResult 对象
        return [
            RetrievalResult(
                chunk_id=str(r.id),
                doc_id=str(r.doc_id),
                content=r.content,
                score=r.score,
                title=r.title,
                doc_type=r.doc_type,
            )
            for r in results
        ]


class Reranker:
    """重排序器 - 使用 CrossEncoder 精排"""

    def __init__(self, model_name: str = None, top_n: int = None):
        self.model_name = model_name or RERANKER_MODEL
        self.top_n = top_n or RERANKER_TOP_N
        # 使用单例获取模型，避免重复初始化
        self.model = get_reranker_instance(self.model_name)

    def rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """
        对检索结果进行重排序

        Args:
            query: 查询问题
            results: 待排序的检索结果列表

        Returns:
            重排序后的检索结果列表（前 top_n 个）
        """
        if not results:
            return []

        # 构造 (query, document) 对
        contents = [r.content for r in results]
        pairs = [[query, content] for content in contents]

        # 计算相关性分数
        scores = self.model.predict(pairs)

        # 按分数降序排序，取 top_n
        scored_results = list(zip(results, scores))
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # 返回排序后的完整结果对象
        return [result for result, score in scored_results[:self.top_n]]


class RagRetriever:
    """RAG 检索器 - 向量检索（跳过重排序以优化性能）"""

    def __init__(self, retrieve_top_k: int = None, rerank_top_n: int = None):
        # 默认只取 Top 5，足够回答问题且速度快
        self.vector_retriever = VectorRetriever(top_k=retrieve_top_k or 5)

    def search(
        self,
        query: str,
        db_session: Session,
        doc_type: Optional[str] = None,
    ) -> List[RetrievalResult]:
        """
        向量检索（跳过 CrossEncoder 重排序以优化性能）

        Args:
            query: 查询问题
            db_session: 数据库会话
            doc_type: 可选，按文档类型过滤

        Returns:
            按相似度排序的检索结果
        """
        # 直接向量检索，跳过耗时的 CrossEncoder 重排序
        results = self.vector_retriever.retrieve(query, db_session, doc_type)
        return results
