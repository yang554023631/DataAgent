import sys
import os
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

# Add project root to path for direct running
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config.settings import settings
from src.config.logging_config import setup_logging
from src.api.middleware import RequestTracingMiddleware
from src.api.sessions import router as sessions_router
from src.api.streaming import router as streaming_router
from src.mcp.config import load_mcp_config
from src.mcp.client import MCPClientManager
from src.utils.logger import logger

# 初始化日志（在所有模块导入之后、app 创建之前）
setup_logging()

# MCP 全局实例
mcp_config = load_mcp_config("config/mcp.yaml")
mcp_manager: MCPClientManager | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时连接 MCP，关闭时断开"""
    global mcp_manager
    if mcp_config.use_mcp:
        logger.info("Starting MCP client...")
        mcp_manager = MCPClientManager(mcp_config)
        await mcp_manager.connect_all()
        logger.info("MCP client started successfully")
    else:
        logger.info("MCP is disabled, using direct connection")

    yield

    # 关闭时清理
    if mcp_manager:
        logger.info("Shutting down MCP client...")
        await mcp_manager.close_all()
        logger.info("MCP client shut down")

app = FastAPI(title="Ad Report Agent API", version="0.1.0", lifespan=lifespan)

# 请求追踪中间件（最外层，最先执行）
app.add_middleware(RequestTracingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router)
app.include_router(streaming_router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ad-report-agent"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
