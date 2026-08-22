"""
PostgreSQL MCP 客户端适配器
通过 MCP Client 调用远程 PG MCP Server 执行查询，接口兼容原有直连版本
"""
from typing import List, Dict, Any
from src.mcp.client import MCPClientManager
from src.utils.logger import logger
from mcp.types import CallToolResult

class PostgresMCPClient:
    """PostgreSQL MCP 客户端，通过 MCP 协议执行只读查询"""

    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp_manager = mcp_manager
        self.server_name = "postgres"

    async def query(self, sql: str) -> List[Dict[str, Any]]:
        """执行只读 SQL 查询，返回结果列表

        Args:
            sql: SQL 查询语句

        Returns:
            查询结果，每行是一个字典，key 是列名，value 是值
        """
        result = await self.mcp_manager.call_tool(
            server=self.server_name,
            tool_name="query",
            arguments={"sql": sql}
        )

        return self._parse_result(result)

    async def list_tables(self) -> List[str]:
        """列出所有表"""
        result = await self.mcp_manager.call_tool(
            server=self.server_name,
            tool_name="list_tables",
            arguments={}
        )
        # 官方返回格式是表格列表
        content = self._extract_text(result)
        # 解析返回内容，实际官方返回 JSON 格式
        import json
        try:
            tables = json.loads(content)
            return tables
        except:
            # 如果是纯文本列表，逐行解析
            return [line.strip() for line in content.splitlines() if line.strip()]

    async def describe_table(self, table_name: str) -> Dict[str, Any]:
        """获取表结构"""
        result = await self.mcp_manager.call_tool(
            server=self.server_name,
            tool_name="describe_table",
            arguments={"table_name": table_name}
        )
        content = self._extract_text(result)
        import json
        try:
            return json.loads(content)
        except:
            return {"description": content}

    def _extract_text(self, result: CallToolResult) -> str:
        """从 MCP CallToolResult 提取文本内容"""
        if not result.content:
            return ""

        # 官方服务器返回 text 内容
        for content in result.content:
            if content.type == "text":
                return content.text

        return ""

    def _parse_result(self, result: CallToolResult) -> List[Dict[str, Any]]:
        """解析查询结果

        官方 postgres MCP server 返回格式：
        [
          {"column1": "value1", "column2": "value2"},
          ...
        ]
        """
        text = self._extract_text(result)
        if not text:
            return []

        import json
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse MCP result as JSON: {e}, text={text[:200]}")
            # 返回原始文本包装
            return [{"raw": text}]


# 全局单例，由应用启动时初始化
_postgres_mcp_instance: PostgresMCPClient | None = None

def get_postgres_mcp_client(mcp_manager: MCPClientManager) -> PostgresMCPClient:
    """获取 Postgres MCP 客户端单例"""
    global _postgres_mcp_instance
    if _postgres_mcp_instance is None:
        _postgres_mcp_instance = PostgresMCPClient(mcp_manager)
    return _postgres_mcp_instance
