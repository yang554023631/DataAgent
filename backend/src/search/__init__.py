"""
Elasticsearch 访问层
- elasticsearch.py: 原有直连（保留，可回滚）
- elasticsearch_mcp.py: MCP 客户端（新）
"""
from src.mcp.config import mcp_config
from src.main import mcp_manager

if mcp_config.use_mcp and mcp_manager is not None:
    from .elasticsearch_mcp import ElasticsearchMCPClient, get_elasticsearch_mcp_client
    es_client = get_elasticsearch_mcp_client(mcp_manager)
else:
    # 回退到原有直连
    from elasticsearch import Elasticsearch
    es_client = Elasticsearch(["http://localhost:9200"])
