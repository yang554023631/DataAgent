"""
MCP Client 连接管理
统一管理所有 MCP Servers 的连接，支持 stdio 和 sse 两种传输方式
"""
import asyncio
import builtins
import json
import logging
import time
from typing import Dict, Optional, Tuple
import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp import stdio_client, ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.types import CallToolResult, JSONRPCMessage
from src.mcp_client.config import MCPConfig, MCPServerConfig

anext = getattr(builtins, 'anext', None)
if anext is None:
    async def anext(aiterator):
        return await aiterator.__anext__()


logger = logging.getLogger(__name__)


# 专门的 MCP 日志
mcp_logger = logging.getLogger("mcp_client")

class MCPClientManager:
    """MCP 客户端连接管理器，管理多个 MCP Server 连接

    关键实现点：
    - For stdio: use stdio_client runs a synchronous approach where the I/O tasks
      must be processed in a separate background task that just waits forever
    """

    def __init__(self, config: MCPConfig):
        self.config = config
        self.sessions: Dict[str, ClientSession] = {}
        self._initialized: Dict[str, bool] = {}
        # Keep streams
        self._streams: Dict[str, Tuple[MemoryObjectReceiveStream[JSONRPCMessage | Exception], MemoryObjectSendStream[JSONRPCMessage]]] = {}
        # Keep anyio task groups (for stdio) that contain the background I/O tasks
        self._tg: Dict[str, anyio.abc.TaskGroup] = {}

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
            params = self._create_stdio_transport(server_config)

            # The TRICK that works:
            # - Everything (stdio_client + ClientSession + initialize) runs in a single
            #   asyncio task created with asyncio.create_task() - NOT started via anyio tg.start_soon
            # - We wait for it to finish initializing by waiting on an event
            # - After initialization, the task just blocks forever until we cancel it on close

            # Hold result
            session: ClientSession | None = None
            error: Exception | None = None
            initialized = asyncio.Event()

            async def run_connection():
                nonlocal session, error
                try:
                    async with stdio_client(params) as (read_stream, write_stream):
                        # CRITICAL: ClientSession requires async with context manager
                        # to start its background message pump - this was missing earlier
                        async with ClientSession(read_stream, write_stream) as sess:
                            await sess.initialize()
                            session = sess
                            initialized.set()
                            # Keep everything open until cancelled on shutdown
                            await asyncio.Event().wait()
                except asyncio.CancelledError:
                    # Expected when closing
                    if not initialized.is_set():
                        error = asyncio.CancelledError()
                        initialized.set()
                except Exception as e:
                    error = e
                    initialized.set()

            # Start background connection task
            bg_task = asyncio.create_task(run_connection())

            # Wait for initialization with timeout
            try:
                # Wait up to 30 seconds
                await asyncio.wait_for(initialized.wait(), 30)
            except asyncio.TimeoutError:
                bg_task.cancel()
                try:
                    await bg_task
                except asyncio.CancelledError:
                    pass
                raise RuntimeError(f"Timeout initializing MCP server {server_name} after 30s")

            if error is not None:
                bg_task.cancel()
                try:
                    await bg_task
                except asyncio.CancelledError:
                    pass
                raise error

            if session is None:
                bg_task.cancel()
                try:
                    await bg_task
                except asyncio.CancelledError:
                    pass
                raise RuntimeError("No session created during initialization")

            # Connection successful
            self._tg[server_name] = bg_task
            self.sessions[server_name] = session
            self._initialized[server_name] = True
            logger.info(f"MCP server '{server_name}' connected successfully")

        elif server_config.type == "sse":
            # Direct approach - sse_client already manages its own background tasks internally
            # via anyio.TaskGroup. We just need to keep the async with context open
            # for the entire connection lifetime.
            #
            # We use the same approach as stdio: run the entire connection in a background
            # asyncio task and wait for initialization to complete.
            #
            # Previous approach had a scheduling deadlock because anyio memory object streams
            # with capacity 0 block the sender when the receiver isn't actively receiving.
            # The direct approach here keeps everything on the correct task context.
            session: ClientSession | None = None
            error: Exception | None = None
            initialized = asyncio.Event()

            async def run_connection():
                nonlocal session, error
                try:
                    headers = {}
                    if server_config.api_key:
                        headers["Authorization"] = f"Bearer {server_config.api_key}"

                    logger.info(f"SSE connection starting for {server_name} at {server_config.url}")
                    # sse_client internally creates an anyio.TaskGroup and runs
                    # sse_reader and post_writer as child tasks. The async with context
                    # will stay open as long as we keep it open here. When we exit, the
                    # finally cancels the child scope.
                    async with sse_client(server_config.url, headers=headers if headers else None) as (read_stream, write_stream):
                        logger.info(f"sse_client connected, got streams, creating ClientSession")
                        async with ClientSession(read_stream, write_stream) as sess:
                            logger.info(f"Running initialize...")
                            await sess.initialize()
                            logger.info(f"initialize complete")
                            session = sess
                            initialized.set()
                            # Keep everything open until cancelled on shutdown
                            logger.info(f"Initialization complete, blocking forever to keep connection open")
                            await asyncio.Event().wait()
                except asyncio.CancelledError:
                    logger.info(f"SSE connection cancelled for {server_name}")
                    if not initialized.is_set():
                        error = asyncio.CancelledError()
                        initialized.set()
                except Exception as e:
                    logger.error(f"SSE connection error for {server_name}: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    error = e
                    initialized.set()

            # Start background connection task
            bg_task = asyncio.create_task(run_connection())

            # Wait for initialization with timeout
            try:
                # Wait up to 30 seconds
                await asyncio.wait_for(initialized.wait(), 60)
            except asyncio.TimeoutError:
                logger.error(f"Timeout initializing MCP server {server_name} after 60s")
                bg_task.cancel()
                try:
                    await bg_task
                except asyncio.CancelledError:
                    pass
                raise RuntimeError(f"Timeout initializing MCP server {server_name} after 60s")

            if error is not None:
                bg_task.cancel()
                try:
                    await bg_task
                except asyncio.CancelledError:
                    pass
                raise error

            if session is None:
                bg_task.cancel()
                try:
                    await bg_task
                except asyncio.CancelledError:
                    pass
                raise RuntimeError("No session created during initialization")

            # Connection successful
            self._tg[server_name] = bg_task
            self.sessions[server_name] = session
            self._initialized[server_name] = True
            logger.info(f"✅ MCP server '{server_name}' connected successfully (SSE)")
        else:
            raise ValueError(f"Unknown transport type: {server_config.type}")

    def _create_stdio_transport(self, config: MCPServerConfig) -> StdioServerParameters:
        """创建 stdio 传输（本地子进程）"""
        if not config.command or not config.args:
            raise ValueError("stdio transport requires 'command' and 'args'")
        return StdioServerParameters(
            command=config.command,
            args=config.args,
            env=None,  # 使用当前环境
        )

    async def _create_sse_transport(self, config: MCPServerConfig) -> Tuple[MemoryObjectReceiveStream[JSONRPCMessage | Exception], MemoryObjectSendStream[JSONRPCMessage]]:
        """创建 SSE 传输（远程HTTP）"""
        if not config.url:
            raise ValueError("sse transport requires 'url'")

        headers = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        # sse_client is an async context manager that yields the streams
        async with sse_client(config.url, headers=headers if headers else None) as streams:
            return streams

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

        # Cancel background tasks first - this terminates the subprocess
        # _tg[server_name] can be either:
        #   - asyncio.Task (stdio new approach)
        #   - anyio.TaskGroup (stdio old approach / sse)
        for server_name, entry in self._tg.items():
            try:
                if isinstance(entry, asyncio.Task):
                    # New approach: background asyncio task (stdio)
                    entry.cancel()
                    try:
                        await entry
                    except asyncio.CancelledError:
                        # Expected - suppress
                        pass
                else:
                    # Old approach / SSE: anyio task group
                    if hasattr(entry, 'cancel_scope'):
                        entry.cancel_scope.cancel()
                    try:
                        await entry.__aexit__(None, None, None)
                    except Exception:
                        pass
            except Exception as e:
                close_errors.append((server_name, e))
                logger.warning(f"Error closing background task for MCP server '{server_name}': {e}")

        # Close streams (for SSE only - stdio handled by task exit)
        for server_name, (read_stream, write_stream) in self._streams.items():
            if server_name not in self._tg:  # Only SSE
                try:
                    await read_stream.aclose()
                    await write_stream.aclose()
                except Exception as e:
                    close_errors.append((server_name, e))
                    logger.warning(f"Error closing streams for MCP server '{server_name}': {e}")

        self.sessions.clear()
        self._initialized.clear()
        self._streams.clear()
        self._tg.clear()

        if close_errors:
            logger.warning(f"Some MCP servers had errors on close: {close_errors}")

    def is_connected(self, server: str) -> bool:
        """检查服务器是否已连接"""
        return server in self.sessions and self._initialized.get(server, False)
