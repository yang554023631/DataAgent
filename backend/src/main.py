import sys
import os
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

# 初始化日志（在所有模块导入之后、app 创建之前）
setup_logging()

app = FastAPI(title="Ad Report Agent API", version="0.1.0")

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
