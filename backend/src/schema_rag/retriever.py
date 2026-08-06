"""Schema RAG 检索器
复用现有 VectorRetriever，固定 doc_type='schema'
"""
import logging
from src.rag.retriever import VectorRetriever, RetrievalResult

logger = logging.getLogger(__name__)

_schema_retriever_instance = None


class SchemaRetriever:
    """Schema 元数据检索器

    在 VectorRetriever 基础上封装，固定检索 doc_type='schema' 的文档。
    支持三级检索：索引级 / 字段级 / 查询示例级。
    """

    def __init__(self, top_k: int = 10):
        self._retriever = VectorRetriever(top_k=top_k)

    def search(self, query: str, db_session=None) -> list:
        """语义检索相关的 schema 文档

        Args:
            query: 用户问题或检索关键词
            db_session: 数据库会话（若为 None 则内部创建）

        Returns:
            List[RetrievalResult]: 按相似度排序的检索结果
        """
        if db_session is None:
            from src.rag.database import get_db
            db_session = next(get_db())
            close_after = True
        else:
            close_after = False

        try:
            results = self._retriever.retrieve(
                query=query,
                db_session=db_session,
                doc_type="schema",
            )
            logger.info(f"Schema RAG检索: query='{query[:50]}', 命中={len(results)}条")
            return results
        finally:
            if close_after:
                db_session.close()

    def search_by_index(self, query: str, index_name: str, db_session=None) -> list:
        """检索指定索引下的 schema 文档（字段级 + 示例级）

        在 query 前拼接索引名作为上下文，提升检索精准度。
        """
        enhanced_query = f"在{index_name}索引中，{query}"
        return self.search(enhanced_query, db_session)


def get_schema_retriever() -> SchemaRetriever:
    """获取 SchemaRetriever 单例"""
    global _schema_retriever_instance
    if _schema_retriever_instance is None:
        _schema_retriever_instance = SchemaRetriever()
    return _schema_retriever_instance