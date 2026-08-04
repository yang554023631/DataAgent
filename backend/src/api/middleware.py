"""请求追踪中间件

为每个请求生成唯一 request_id，写入 contextvars，
记录请求开始/结束日志，并在响应 header 中注入 X-Request-ID。
"""
import re
import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.config.context import set_request_id, set_session_id
from src.config.context import request_id_var, session_id_var

logger = logging.getLogger(__name__)

# 匹配 session_id 的路径模式
SESSION_PATH_PATTERN = re.compile(r"/api/sessions/([^/]+)")


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """请求追踪中间件"""

    async def dispatch(self, request: Request, call_next):
        # 生成 request_id
        request_id = str(uuid.uuid4())
        req_token = set_request_id(request_id)

        # 从路径提取 session_id
        session_id = self._extract_session_id(request.url.path)
        sess_token = set_session_id(session_id) if session_id else None

        start_time = time.time()
        method = request.method
        path = request.url.path

        # 读取 body 用于日志（但要放回去，不影响后续读取）
        body_bytes = await request.body()
        body_preview = self._get_body_preview(body_bytes, path)

        logger.info(f"请求开始: {method} {path}, session_id={session_id}, 用户输入={body_preview}")

        try:
            # 重建 request（因为 body 已经读过了）
            # FastAPI/Starlette 的 request.body() 是可重读的，这里不需要特殊处理
            response = await call_next(request)

            duration_ms = int((time.time() - start_time) * 1000)
            status_code = response.status_code

            # 结果摘要（从 response 中不好直接拿 body，就打状态码和耗时就行）
            logger.info(f"请求完成: 状态={status_code}, 耗时={duration_ms}ms")

            # 注入响应 header
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"请求异常: error={e}, 耗时={duration_ms}ms")
            # 异常也要注入 header 再抛出
            # 注意：FastAPI 会把未捕获异常转成 500，这里我们直接抛出
            raise
        finally:
            # 重置 contextvars
            request_id_var.reset(req_token)
            if sess_token is not None:
                session_id_var.reset(sess_token)

    def _extract_session_id(self, path: str) -> str:
        """从 URL 路径中提取 session_id"""
        match = SESSION_PATH_PATTERN.search(path)
        if match:
            return match.group(1)
        return "-"

    def _get_body_preview(self, body_bytes: bytes, path: str) -> str:
        """获取请求 body 的摘要用于日志"""
        if not body_bytes:
            return '""'

        try:
            body_str = body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return "<binary>"

        # 只截取前 500 字
        if len(body_str) > 500:
            body_str = body_str[:500] + "..."

        # 简单转义，避免日志注入
        body_str = body_str.replace("\n", " ").replace("\r", "")
        return f'"{body_str}"'
