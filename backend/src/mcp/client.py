"""
MCP Client 连接管理
统一管理所有 MCP Servers 的连接，支持 stdio 和 sse 两种传输方式
"""
import asyncio
import json
import logging
import time
from typing import Dict, Optional
from mcp.client.stdio import StdioClientTransport
from mcp.client.sse import SseClientTransport
from mcp.client.session import ClientSession
from mcp.types import CallToolResult
from src.mcp.config import MCPConfig, MCPServerConfig
from src.utils.logger import logger

# 专门的 MCP 日志
mcp_logger = logging.getLogger("mcp_client")

class MCPClientManager:
    """MCP 客户端连接管理器，管理多个 MCP Server 连接"""

    def __init__(self, config: MCPConfig):
        self.config = config
        self.sessions: Dict[str, ClientSession] = {}
        self._initialized: Dict[str, bool] = {}

    async def connect_all(self) -> None:
        """连接所有配置的 MCP Servers

        如果任何一个连接失败，直接抛出异常，应用启动失败（尽早失败原则）
        """
        for server_name, server_config in self.config.servers.items():
            logger.info(f"Connecting to MCP server: {server_name} ({server_config.type})")
            await self.connect(server_name, server_config)
        logger.info(f"All MCP servers connected: {list(self.sessions.keys())}")

    async def connect(self, server_name: str, server_config: MCPServerConfig) -> None:
        """连接单个 MCP Server"""
        if server_config.type == "stdio":
            transport = self._create_stdio_transport(server_config)
        elif server_config.type == "sse":
            transport = await self._create_sse_transport(server_config)
        else:
            raise ValueError(f"Unknown transport type: {server_config.type}")

        session = ClientSession(transport)
        try:
            await session.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize MCP server {server_name}: {e}")
            await transport.close()
            raise

        self.sessions[server_name] = session
        self._initialized[server_name] = True
        logger.info(f"MCP server '{server_name}' connected successfully")

    def _create_stdio_transport(self, config: MCPServerConfig) -> StdioClientTransport:
        """创建 stdio 传输（本地子进程）"""
        if not config.command or not config.args:
            raise ValueError("stdio transport requires 'command' and 'args'")
        return StdioClientTransport(
            command=config.command,
            args=config.args,
            env=None,  # 使用当前环境
        )

    async def _create_sse_transport(self, config: MCPServerConfig) -> SseClientTransport:
        """创建 SSE 传输（远程HTTP）"""
        if not config.url:
            raise ValueError("sse transport requires 'url'")

        headers = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        transport = SseClientTransport(
            url=config.url,
            headers=headers if headers else None,
        )
        return transport

    async def call_tool(
        self,
        server: str,
        tool_name: str,
        arguments: dict,
        timeout: float = 30.0,
    ) -> CallToolResult:
        """调用远程工具

        Args:
            server: 服务器名称
            tool_name: 工具名称
            arguments: 参数
            timeout: 超时时间（秒）

        Returns:
            工具调用结果

        Raises:
            Exception: 调用失败或超时
        """
        if server not in self.sessions:
            raise RuntimeError(f"MCP server '{server}' not connected")

        session = self.sessions[server]
        start_time = time.time()

        try:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=timeout
            )

            elapsed_ms = int((time.time() - start_time) * 1000)
            is_error = getattr(result, 'isError', False)

            if is_error:
                mcp_logger.info(
                    json.dumps({
                        "event": "mcp_call",
                        "server": server,
                        "tool": tool_name,
                        "elapsed_ms": elapsed_ms,
                        "is_error": True,
                        "error": str(result.content),
                    }, ensure_ascii=False)
                )
            else:
                mcp_logger.info(
                    json.dumps({
                        "event": "mcp_call",
                        "server": server,
                        "tool": tool_name,
                        "elapsed_ms": elapsed_ms,
                        "is_error": False,
                    }, ensure_ascii=False)
                )

            return result

        except asyncio.TimeoutError:
            elapsed_ms = int((time.time() - start_time) * 1000)
            mcp_logger.error(
                json.dumps({
                    "event": "mcp_call_timeout",
                    "server": server,
                    "tool": tool_name,
                    "elapsed_ms": elapsed_ms,
                }, ensure_ascii=False)
            )
            raise RuntimeError(f"MCP call timeout: {server}/{tool_name} after {timeout}s")

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            mcp_logger.error(
                json.dumps({
                    "event": "mcp_call_error",
                    "server": server,
                    "tool": tool_name,
                    "elapsed_ms": elapsed_ms,
                    "error": str(e),
                }, ensure_ascii=False)
            )
            raise

    async def close_all(self) -> None:
        """关闭所有连接"""
        close_errors = []
        for server_name, session in self.sessions.items():
            try:
                await session.close()
                logger.info(f"MCP server '{server_name}' closed")
            except Exception as e:
                close_errors.append((server_name, e))
                logger.warning(f"Error closing MCP server '{server_name}': {e}")

        self.sessions.clear()
        self._initialized.clear()

        if close_errors:
            logger.warning(f"Some MCP servers had errors on close: {close_errors}")

    def is_connected(self, server: str) -> bool:
        """检查服务器是否已连接"""
        return server in self.sessions and self._initialized.get(server, False)
