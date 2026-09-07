"""
Elasticsearch 搜索访问层

Public interface (seam):
- SearchClient    : Protocol, 定义搜索访问接口
- create_search_client(mcp_manager) : 工厂函数，创建 ES 客户端

Adapter (实现):
- ElasticsearchMCPClient : 通过 MCP 协议访问 Elasticsearch

调用方应该通过构造参数接收 SearchClient，而不是 import 全局单例。
"""
from __future__ import annotations

from typing import Protocol, Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.mcp_client.client import MCPClientManager


class SearchClient(Protocol):
    """Elasticsearch 客户端接口 (seam)

    所有 ES 适配器都必须实现这个接口。
    调用方只依赖这个 Protocol，不依赖具体实现。
    """

    async def search(self, index: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """执行搜索/聚合查询

        Args:
            index: 索引名称
            body: ES 查询 DSL

        Returns:
            ES 原始响应 dict
        """
        ...

    async def list_indices(self) -> List[str]:
        """列出所有索引"""
        ...

    async def get_mapping(self, index: str) -> Dict[str, Any]:
        """获取索引 mapping"""
        ...


def create_search_client(mcp_manager: MCPClientManager | None = None) -> SearchClient:
    """创建 Elasticsearch 客户端 (工厂函数)

    Args:
        mcp_manager: MCP 客户端管理器，为 None 时后续可扩展直连模式

    Returns:
        实现了 SearchClient 接口的客户端实例
    """
    from .elasticsearch_mcp import ElasticsearchMCPClient

    if mcp_manager is not None:
        return ElasticsearchMCPClient(mcp_manager)

    # TODO: 直连模式的 fallback
    raise RuntimeError("Search client requires mcp_manager")


__all__ = [
    "SearchClient",
    "create_search_client",
]
