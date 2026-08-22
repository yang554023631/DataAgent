"""
数据库访问层
- postgres.py: 原有直连（保留，可回滚）
- postgres_mcp.py: MCP 客户端（新）
"""
from src.mcp.config import mcp_config
from src.main import mcp_manager

if mcp_config.use_mcp and mcp_manager is not None:
    from .postgres_mcp import PostgresMCPClient, get_postgres_mcp_client
    pg_client = get_postgres_mcp_client(mcp_manager)
else:
    # 回退到直连
    # 如果你有直连实现，这里导入替换
    pg_client = None
