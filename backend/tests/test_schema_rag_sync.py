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


class TestSchemaSyncer:
    def test_index_yaml_to_markdown(self):
        """索引级 YAML 转 Markdown 文档"""
        from src.schema_rag.sync import _index_yaml_to_markdown
        yaml_data = {
            "index_name": "ad_stat_data",
            "description": "广告报表事实表",
            "supported_analysis_types": ["trend", "comparison"],
            "hierarchy_fields": [
                {"advertiser_id": "广告主ID"},
                {"campaign_id": "计划ID"},
            ],
            "time_field": "data_date",
            "metric_field": "data_value",
            "metric_type_field": "data_type",
        }
        md = _index_yaml_to_markdown(yaml_data)
        assert "# 索引: ad_stat_data" in md
        assert "广告报表事实表" in md
        assert "trend" in md
        assert "advertiser_id" in md

    def test_field_yaml_to_markdown(self):
        """字段级 YAML 转 Markdown 文档"""
        from src.schema_rag.sync import _field_yaml_to_markdown
        yaml_data = {
            "field_name": "data_type",
            "index": "ad_stat_data",
            "field_type": "integer",
            "description": "指标类型编码",
            "enumeration": [
                {"value": 1, "label": "曝光", "alias": ["曝光量", "impressions"]},
                {"value": 3, "label": "消耗", "alias": ["花费", "cost"], "note": "单位：元"},
            ],
        }
        md = _field_yaml_to_markdown(yaml_data)
        assert "data_type" in md
        assert "指标类型编码" in md
        assert "曝光" in md
        assert "消耗" in md
        assert "单位：元" in md
