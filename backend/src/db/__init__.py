"""
数据库访问层

Public interface (seam):
- PostgresClient  : Protocol, 定义数据库访问接口
- create_postgres_client(mcp_manager) : 工厂函数，创建 Postgres 客户端

Adapter (实现):
- PostgresMCPClient : 通过 MCP 协议访问 PostgreSQL

调用方应该通过构造参数接收 PostgresClient，而不是 import 全局单例。
"""
from __future__ import annotations

from typing import Protocol, Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.mcp_client.client import MCPClientManager


class PostgresClient(Protocol):
    """PostgreSQL 客户端接口 (seam)

    所有 Postgres 适配器都必须实现这个接口。
    调用方只依赖这个 Protocol，不依赖具体实现。
    """

    async def query(self, sql: str) -> List[Dict[str, Any]]:
        """执行只读 SQL 查询，返回结果列表

        Args:
            sql: SQL 查询语句

        Returns:
            查询结果，每行是一个字典，key 是列名，value 是值
        """
        ...

    async def list_tables(self) -> List[str]:
        """列出所有表"""
        ...

    async def describe_table(self, table_name: str) -> Dict[str, Any]:
        """获取表结构"""
        ...


def create_postgres_client(mcp_manager: MCPClientManager | None = None) -> PostgresClient:
    """创建 Postgres 客户端 (工厂函数)

    Args:
        mcp_manager: MCP 客户端管理器，为 None 时后续可扩展直连模式

    Returns:
        实现了 PostgresClient 接口的客户端实例
    """
    from .postgres_mcp import PostgresMCPClient

    if mcp_manager is not None:
        return PostgresMCPClient(mcp_manager)

    # TODO: 直连模式的 fallback
    raise RuntimeError("Postgres client requires mcp_manager")


__all__ = [
    "PostgresClient",
    "create_postgres_client",
]
