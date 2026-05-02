from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy.orm import Session

from .config import RETRIEVE_TOP_K, RERANKER_MODEL, RERANKER_TOP_N
from .embedding import get_embedding_provider
from .models import RagChunk, RagDocument

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
        results = q.order_by(RagChunk.embedding.cosine_distance(query_embedding)) \
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
        if not HAS_SENTENCE_TRANSFORMERS:
            raise ImportError(
                "sentence-transformers is required for Reranker. "
                "Install with: pip install sentence-transformers"
            )
        self.model_name = model_name or RERANKER_MODEL
        self.top_n = top_n or RERANKER_TOP_N
        self.model = CrossEncoder(self.model_name)

    def rerank(self, query: str, documents: List[str]) -> List[str]:
        """
        对检索结果进行重排序

        Args:
            query: 查询问题
            documents: 待排序的文档列表

        Returns:
            重排序后的文档列表（前 top_n 个）
        """
        if not documents:
            return []

        # 构造 (query, document) 对
        pairs = [[query, doc] for doc in documents]

        # 计算相关性分数
        scores = self.model.predict(pairs)

        # 按分数降序排序，取 top_n
        scored_docs = list(zip(documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        # 返回排序后的文档内容
        return [doc for doc, score in scored_docs[:self.top_n]]


class RagRetriever:
    """RAG 检索器 - 向量检索 + 重排序完整流程"""

    def __init__(self, retrieve_top_k: int = None, rerank_top_n: int = None):
        self.vector_retriever = VectorRetriever(top_k=retrieve_top_k)
        self.reranker = Reranker(top_n=rerank_top_n)

    def search(
        self,
        query: str,
        db_session: Session,
        doc_type: Optional[str] = None,
    ) -> List[RetrievalResult]:
        """
        完整检索流程：向量召回 + 重排序

        Args:
            query: 查询问题
            db_session: 数据库会话
            doc_type: 可选，按文档类型过滤

        Returns:
            重排序后的检索结果
        """
        # 第一步：向量召回
        initial_results = self.vector_retriever.retrieve(query, db_session, doc_type)

        if not initial_results:
            return []

        # 第二步：重排序
        contents = [r.content for r in initial_results]
        reranked_contents = self.reranker.rerank(query, contents)

        # 根据重排序结果重新排列
        content_to_result = {r.content: r for r in initial_results}
        reranked_results = []
        for content in reranked_contents:
            if content in content_to_result:
                reranked_results.append(content_to_result[content])

        return reranked_results
