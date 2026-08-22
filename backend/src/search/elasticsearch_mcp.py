"""
Elasticsearch MCP 客户端适配器
通过 MCP Client 调用远程 ES MCP Server 执行查询，接口兼容原有直连版本
"""
from typing import List, Dict, Any, Optional
from src.mcp.client import MCPClientManager
from src.utils.logger import logger
from mcp.types import CallToolResult

class ElasticsearchMCPClient:
    """Elasticsearch MCP 客户端，通过 MCP 协议执行只读搜索"""

    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp_manager = mcp_manager
        self.server_name = "elasticsearch"

    async def search(self, index: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """执行搜索/聚合查询

        Args:
            index: 索引名称
            body: ES 查询 DSL

        Returns:
            ES 原始响应 dict
        """
        result = await self.mcp_manager.call_tool(
            server=self.server_name,
            tool_name="search",
            arguments={
                "index": index,
                "body": body
            }
        )

        return self._parse_json_result(result)

    async def list_indices(self) -> List[str]:
        """列出所有索引"""
        result = await self.mcp_manager.call_tool(
            server=self.server_name,
            tool_name="list_indices",
            arguments={}
        )

        parsed = self._parse_json_result(result)
        if isinstance(parsed, list):
            return parsed
        return []

    async def get_mapping(self, index: str) -> Dict[str, Any]:
        """获取索引 mapping"""
        result = await self.mcp_manager.call_tool(
            server=self.server_name,
            tool_name="get_mapping",
            arguments={"index": index}
        )

        return self._parse_json_result(result)

    def _extract_text(self, result: CallToolResult) -> str:
        """从 MCP CallToolResult 提取文本内容"""
        if not result.content:
            return ""

        for content in result.content:
            if content.type == "text":
                return content.text

        return ""

    def _parse_json_result(self, result: CallToolResult) -> Any:
        """解析 JSON 返回结果"""
        text = self._extract_text(result)
        if not text:
            return None

        import json
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse MCP ES result as JSON: {e}, text={text[:200]}")
            return {"raw": text}


# 全局单例，由应用启动时初始化
_es_mcp_instance: ElasticsearchMCPClient | None = None

def get_elasticsearch_mcp_client(mcp_manager: MCPClientManager) -> ElasticsearchMCPClient:
    """获取 Elasticsearch MCP 客户端单例"""
    global _es_mcp_instance
    if _es_mcp_instance is None:
        _es_mcp_instance = ElasticsearchMCPClient(mcp_manager)
    return _es_mcp_instance
