"""Schema RAG 同步与检索测试"""
import pytest
from unittest.mock import MagicMock, patch
from src.schema_rag.retriever import SchemaRetriever, get_schema_retriever


class TestSchemaRetriever:
    def test_singleton_returns_same_instance(self):
        r1 = get_schema_retriever()
        r2 = get_schema_retriever()
        assert r1 is r2  # 基本存在性检查

    def test_search_filters_by_schema_doc_type(self):
        """SchemaRetriever.search 内部调用 VectorRetriever 时 doc_type='schema'"""
        with patch('src.schema_rag.retriever.VectorRetriever') as MockVR:
            mock_vr = MagicMock()
            mock_vr.retrieve.return_value = []
            MockVR.return_value = mock_vr

            mock_db = MagicMock()
            sr = SchemaRetriever(top_k=5)
            sr.search("消耗指标", mock_db)

            # 验证调用时 doc_type='schema'
            mock_vr.retrieve.assert_called_once()
            call_kwargs = mock_vr.retrieve.call_args
            assert call_kwargs[1].get('doc_type') == 'schema'
