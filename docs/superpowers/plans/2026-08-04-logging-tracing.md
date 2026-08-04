# 全链路日志与请求追踪 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为应用建立统一的日志体系和请求追踪机制，每个请求有唯一 request_id，处理全链路可追溯。

**Architecture:** 通过 FastAPI Middleware 生成 request_id 并存入 contextvars，自定义 LogFilter 让所有日志自动携带 ID；LangGraph 回调统一打节点生命周期日志；业务代码在关键节点埋点打 INFO 日志；日志输出到文件（按天滚动）+ 控制台，error.log 单独收集错误。

**Tech Stack:** Python logging, contextvars, FastAPI Middleware, LangGraph callbacks, TimedRotatingFileHandler

## Global Constraints

- 日志格式：`%(asctime)s [%(levelname)s] [%(request_id)s] [%(session_id)s] [%(name)s] %(message)s`
- 日志目录：`backend/logs/`（相对 backend 目录）
- 滚动策略：按天滚动，保留 30 天
- 日志级别：仅使用 INFO 和 ERROR（WARNING 仅用于 error.log 过滤）
- 截断长度：LLM 和 ES 的大文本截断 1000 字符，其余全量打印
- 响应 header：`X-Request-ID`
- 日志文件：`app.log`（全量 INFO+）+ `error.log`（WARNING+）

---

### Task 1: 上下文变量模块 + 截断工具

**Files:**
- Create: `backend/src/config/context.py`
- Test: `backend/tests/test_context.py`

**Interfaces:**
- Produces:
  - `request_id_var: ContextVar[str]` — 请求 ID 上下文变量
  - `session_id_var: ContextVar[str]` — 会话 ID 上下文变量
  - `get_request_id() -> str` — 获取当前 request_id，无则返回 `-`
  - `set_request_id(rid: str) -> Token` — 设置 request_id
  - `get_session_id() -> str` — 获取当前 session_id，无则返回 `-`
  - `set_session_id(sid: str) -> Token` — 设置 session_id
  - `truncate_log(text: str, max_len: int = 1000) -> str` — 日志截断工具

- [ ] **Step 1: Write failing tests**

```python
import pytest
from src.config.context import (
    get_request_id, set_request_id,
    get_session_id, set_session_id,
    truncate_log,
)


def test_truncate_log_short_text():
    """短文本不截断"""
    assert truncate_log("hello", 100) == "hello"


def test_truncate_log_exact_length():
    """正好等于max_len不截断"""
    text = "a" * 50
    assert truncate_log(text, 50) == text


def test_truncate_log_long_text():
    """长文本截断并标注总长度"""
    text = "a" * 2000
    result = truncate_log(text, 1000)
    assert len(result) > 1000  # 1000 + 后缀
    assert result.startswith("a" * 1000)
    assert "共2000字" in result


def test_truncate_log_chinese():
    """中文按字符数截断"""
    text = "你好" * 600  # 1200字
    result = truncate_log(text, 1000)
    assert result.endswith("... (共1200字)")
    assert len(result.replace("... (共1200字)", "")) == 1000


def test_truncate_log_empty():
    """空字符串"""
    assert truncate_log("", 100) == ""


def test_truncate_log_none_default_max_len():
    """默认max_len=1000"""
    text = "a" * 1500
    result = truncate_log(text)
    assert "共1500字" in result
    assert len(result.replace("... (共1500字)", "")) == 1000


def test_get_request_id_default():
    """默认返回 -"""
    assert get_request_id() == "-"


def test_set_and_get_request_id():
    """设置后可以读到"""
    token = set_request_id("test-req-123")
    assert get_request_id() == "test-req-123"
    # 重置
    import contextvars
    from src.config.context import request_id_var
    request_id_var.reset(token)
    assert get_request_id() == "-"


def test_get_session_id_default():
    """默认返回 -"""
    assert get_session_id() == "-"


def test_set_and_get_session_id():
    """设置后可以读到"""
    token = set_session_id("sess-abc")
    assert get_session_id() == "sess-abc"
    # 重置
    from src.config.context import session_id_var
    session_id_var.reset(token)
    assert get_session_id() == "-"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_context.py -v`
Expected: FAIL with "module not found"

- [ ] **Step 3: Implement context module**

```python
"""上下文变量与日志工具函数"""
import contextvars
from typing import Optional

# 请求 ID 上下文变量（异步安全）
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

# 会话 ID 上下文变量
session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "session_id", default="-"
)


def get_request_id() -> str:
    """获取当前请求 ID，无则返回 '-' """
    return request_id_var.get() or "-"


def set_request_id(request_id: str):
    """设置当前请求 ID，返回 token 用于 reset"""
    return request_id_var.set(request_id)


def get_session_id() -> str:
    """获取当前会话 ID，无则返回 '-' """
    return session_id_var.get() or "-"


def set_session_id(session_id: str):
    """设置当前会话 ID，返回 token 用于 reset"""
    return session_id_var.set(session_id)


def truncate_log(text: str, max_len: int = 1000) -> str:
    """截断长文本用于日志输出

    Args:
        text: 原始文本
        max_len: 最大字符数，默认 1000

    Returns:
        截断后的文本，超过时格式为 "前max_len字... (共N字)"
    """
    if not text:
        return ""

    text_len = len(text)
    if text_len <= max_len:
        return text

    return f"{text[:max_len]}... (共{text_len}字)"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_context.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/config/context.py backend/tests/test_context.py
git commit -m "feat: 添加上下文变量模块和日志截断工具"
```

---

### Task 2: 日志配置模块

**Files:**
- Create: `backend/src/config/logging_config.py`
- Modify: `backend/src/config/settings.py` — 新增日志配置项
- Test: `backend/tests/test_logging_config.py`

**Interfaces:**
- Consumes:
  - `get_request_id()` from `src.config.context`
  - `get_session_id()` from `src.config.context`
  - `settings` from `src.config.settings`
- Produces:
  - `setup_logging()` — 初始化日志系统（幂等，可重复调用）
  - `ContextFilter` — 自定义日志过滤器，注入 request_id/session_id

- [ ] **Step 1: Add logging config to settings.py**

在 `Settings` 类中新增：

```python
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    LOG_BACKUP_DAYS: int = 30
    LOG_TRUNCATE_LEN: int = 1000
```

- [ ] **Step 2: Write failing tests for logging config**

```python
import os
import logging
import tempfile
import pytest
from src.config.logging_config import setup_logging, ContextFilter
from src.config.context import set_request_id, set_session_id, request_id_var, session_id_var


def test_context_filter_injects_ids():
    """ContextFilter 正确注入 request_id 和 session_id"""
    # 设置上下文
    req_token = set_request_id("req-123")
    sess_token = set_session_id("sess-456")

    try:
        log_filter = ContextFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="test message", args=(), exc_info=None
        )
        result = log_filter.filter(record)
        assert result is True
        assert record.request_id == "req-123"
        assert record.session_id == "sess-456"
    finally:
        request_id_var.reset(req_token)
        session_id_var.reset(sess_token)


def test_context_filter_no_context():
    """无上下文时返回 -"""
    log_filter = ContextFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO,
        pathname="test.py", lineno=1,
        msg="test", args=(), exc_info=None
    )
    result = log_filter.filter(record)
    assert result is True
    assert record.request_id == "-"
    assert record.session_id == "-"


def test_setup_logging_creates_files(tmp_path, monkeypatch):
    """setup_logging 创建日志目录和文件"""
    # 临时修改配置
    from src.config import settings as s

    monkeypatch.setattr(s.settings, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(s.settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(s.settings, "LOG_BACKUP_DAYS", 30)

    setup_logging()

    log_dir = tmp_path / "logs"
    assert log_dir.exists()
    assert (log_dir / "app.log").exists()
    assert (log_dir / "error.log").exists()


def test_setup_logging_idempotent(tmp_path, monkeypatch):
    """重复调用 setup_logging 不会重复添加 handler"""
    from src.config import settings as s

    monkeypatch.setattr(s.settings, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(s.settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(s.settings, "LOG_BACKUP_DAYS", 30)

    setup_logging()
    handler_count_before = len(logging.getLogger().handlers)

    setup_logging()
    handler_count_after = len(logging.getLogger().handlers)

    assert handler_count_before == handler_count_after
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_logging_config.py -v`
Expected: FAIL with "module not found"

- [ ] **Step 4: Implement logging config**

```python
"""日志配置模块

提供统一的日志初始化，包含：
- 自定义格式（带 request_id / session_id）
- 文件输出（按天滚动）
- 控制台输出
- 错误日志单独文件
"""
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from src.config.settings import settings
from src.config.context import get_request_id, get_session_id


class ContextFilter(logging.Filter):
    """日志过滤器：从 contextvars 注入 request_id 和 session_id"""

    def filter(self, record):
        record.request_id = get_request_id()
        record.session_id = get_session_id()
        return True


# 标记是否已初始化，防止重复添加 handler
_initialized = False

LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(request_id)s] [%(session_id)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging():
    """初始化日志系统（幂等）"""
    global _initialized
    if _initialized:
        return

    log_dir = Path(settings.LOG_DIR)
    # 相对路径时，相对于 backend 目录
    if not log_dir.is_absolute():
        log_dir = Path(__file__).parent.parent.parent / settings.LOG_DIR

    log_dir.mkdir(parents=True, exist_ok=True)

    app_log_path = log_dir / "app.log"
    error_log_path = log_dir / "error.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # 清除已有的默认 handler（避免 uvicorn 等重复输出）
    root_logger.handlers.clear()

    # 日志格式
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    context_filter = ContextFilter()

    # --- 控制台 handler ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)
    root_logger.addHandler(console_handler)

    # --- app.log 文件 handler（全量） ---
    file_handler = TimedRotatingFileHandler(
        filename=str(app_log_path),
        when="midnight",
        interval=1,
        backupCount=settings.LOG_BACKUP_DAYS,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)
    root_logger.addHandler(file_handler)

    # --- error.log 文件 handler（仅 WARNING+） ---
    error_handler = TimedRotatingFileHandler(
        filename=str(error_log_path),
        when="midnight",
        interval=1,
        backupCount=settings.LOG_BACKUP_DAYS,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)
    error_handler.addFilter(context_filter)
    root_logger.addHandler(error_handler)

    _initialized = True
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_logging_config.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/config/logging_config.py backend/src/config/settings.py backend/tests/test_logging_config.py
git commit -m "feat: 添加日志配置模块（按天滚动 + context ID 注入）"
```

---

### Task 3: 请求追踪 Middleware

**Files:**
- Create: `backend/src/api/middleware.py`
- Modify: `backend/src/main.py` — 注册 middleware、初始化日志
- Test: `backend/tests/test_request_tracing.py`

**Interfaces:**
- Consumes:
  - `setup_logging()` from `src.config.logging_config`
  - `set_request_id()`, `set_session_id()` from `src.config.context`
  - `request_id_var`, `session_id_var` from `src.config.context`
- Produces:
  - `RequestTracingMiddleware` — FastAPI middleware，生成 request_id、打请求日志、注入响应 header
  - 在 main.py 中注册 middleware 并初始化日志

- [ ] **Step 1: Write failing tests**

```python
import re
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.middleware import RequestTracingMiddleware


@pytest.fixture
def app_with_middleware():
    app = FastAPI()
    app.add_middleware(RequestTracingMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/sessions/{session_id}/messages")
    async def send_message(session_id: str):
        return {"status": "completed"}

    return app


def test_request_id_in_response_header(app_with_middleware):
    """响应 header 中包含 X-Request-ID"""
    client = TestClient(app_with_middleware)
    response = client.get("/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


def test_request_id_is_unique(app_with_middleware):
    """两次请求的 request_id 不同"""
    client = TestClient(app_with_middleware)
    r1 = client.get("/health")
    r2 = client.get("/health")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


def test_request_id_is_valid_uuid(app_with_middleware):
    """request_id 是 UUID 格式"""
    client = TestClient(app_with_middleware)
    response = client.get("/health")
    rid = response.headers["x-request-id"]
    # UUID 格式校验 (8-4-4-4-12)
    uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    assert re.match(uuid_pattern, rid, re.IGNORECASE) is not None


def test_session_id_extracted_from_path(app_with_middleware):
    """session_id 从路径中提取（通过日志间接验证）"""
    # 这里我们通过检查中间件不报错来验证基本功能
    # 更详细的日志内容验证在 integration 测试中做
    client = TestClient(app_with_middleware)
    response = client.post(
        "/api/sessions/test-sess-123/messages",
        json={"content": "hello"}
    )
    assert response.status_code == 200
    assert "x-request-id" in response.headers


def test_health_check_has_request_id(app_with_middleware):
    """health check 也有 request_id"""
    client = TestClient(app_with_middleware)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["x-request-id"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_request_tracing.py -v`
Expected: FAIL with "module not found"

- [ ] **Step 3: Implement middleware**

```python
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
```

- [ ] **Step 4: Update main.py — init logging + register middleware**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_request_tracing.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/middleware.py backend/src/main.py backend/tests/test_request_tracing.py
git commit -m "feat: 添加请求追踪中间件（request_id + 响应header + 日志）"
```

---

### Task 4: LangGraph 节点生命周期回调

**Files:**
- Create: `backend/src/graph/callbacks.py`
- Modify: `backend/src/graph/builder.py` — 注册回调
- Test: `backend/tests/test_graph_callbacks.py`

**Interfaces:**
- Consumes:
  - LangGraph StateGraph / CompiledGraph
- Produces:
  - `get_logging_callbacks()` — 返回 LangGraph 回调 handler 列表
  - 回调打日志：节点进入、节点离开（含耗时）、节点异常

- [ ] **Step 1: Write failing tests**

```python
import pytest
from langgraph.graph import StateGraph, END

from src.graph.callbacks import LoggingHandler


def test_logging_handler_node_start_end(caplog):
    """节点进入和离开时打日志"""
    # 构建一个简单的 graph
    def node_a(state):
        return {"value": state.get("value", 0) + 1}

    graph = StateGraph(dict)
    graph.add_node("a", node_a)
    graph.set_entry_point("a")
    graph.add_edge("a", END)

    app = graph.compile()

    handler = LoggingHandler()

    with caplog.at_level("INFO"):
        result = app.invoke({"value": 0}, config={"callbacks": [handler]})

    assert result["value"] == 1

    # 检查日志中包含节点进入和离开
    messages = [r.message for r in caplog.records]
    assert any("进入节点: a" in m for m in messages)
    assert any("离开节点: a" in m for m in messages)
    # 离开日志包含耗时
    assert any("耗时" in m and "ms" in m for m in messages if "离开节点" in m)


def test_logging_handler_node_error(caplog):
    """节点异常时打 ERROR 日志"""
    def bad_node(state):
        raise ValueError("something went wrong")

    graph = StateGraph(dict)
    graph.add_node("bad", bad_node)
    graph.set_entry_point("bad")
    graph.add_edge("bad", END)

    app = graph.compile()
    handler = LoggingHandler()

    with caplog.at_level("ERROR"):
        with pytest.raises(ValueError, match="something went wrong"):
            app.invoke({}, config={"callbacks": [handler]})

    messages = [r.message for r in caplog.records]
    assert any("节点异常" in m and "bad" in m for m in messages)


def test_logging_handler_does_not_affect_flow():
    """回调异常不影响主流程"""
    call_count = {"n": 0}

    def node_a(state):
        call_count["n"] += 1
        return {"ok": True}

    graph = StateGraph(dict)
    graph.add_node("a", node_a)
    graph.set_entry_point("a")
    graph.add_edge("a", END)

    app = graph.compile()

    # 正常 handler
    handler = LoggingHandler()
    result = app.invoke({}, config={"callbacks": [handler]})
    assert result["ok"] is True
    assert call_count["n"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_graph_callbacks.py -v`
Expected: FAIL with "module not found"

- [ ] **Step 3: Implement callbacks module**

```python
"""LangGraph 日志回调

统一记录节点的进入、离开（含耗时）、异常等生命周期事件。
所有日志自动携带 contextvars 中的 request_id / session_id。
"""
import time
import logging
from typing import Any, Dict, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class LoggingHandler(BaseCallbackHandler):
    """LangGraph 节点生命周期日志回调"""

    def __init__(self):
        super().__init__()
        self._node_start_times: Dict[str, float] = {}

    def on_chain_start(
        self, serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        **kwargs: Any
    ) -> None:
        """链/节点开始时调用"""
        # LangGraph 的节点以 "graph.step.nodes.<name>" 形式出现
        # 也可能是 LangChain 的 chain，我们只记录有意义的节点名
        name = kwargs.get("name", "") or serialized.get("name", "")
        if not name:
            return

        # 过滤掉 graph 本身的顶层调用，只记录节点
        if name in ("LangGraph", "StateGraph"):
            return

        try:
            self._node_start_times[name] = time.time()
            logger.info(f"进入节点: {name}")
        except Exception:
            # 回调本身出错不影响主流程
            pass

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        **kwargs: Any
    ) -> None:
        """链/节点结束时调用"""
        name = kwargs.get("name", "")
        if not name or name in ("LangGraph", "StateGraph"):
            return

        try:
            start_time = self._node_start_times.pop(name, None)
            if start_time is not None:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(f"离开节点: {name}, 耗时={duration_ms}ms")
            else:
                logger.info(f"离开节点: {name}")
        except Exception:
            pass

    def on_chain_error(
        self,
        error: BaseException,
        **kwargs: Any
    ) -> None:
        """链/节点异常时调用"""
        name = kwargs.get("name", "unknown")
        try:
            logger.exception(f"节点异常: {name}, error={error}")
        except Exception:
            pass

    def on_llm_start(
        self, serialized: Dict[str, Any],
        prompts: list,
        **kwargs: Any
    ) -> None:
        """LLM 调用开始 — 这里不打日志，由业务代码自行控制 LLM 日志的详细程度"""
        pass

    def on_llm_end(
        self, response: LLMResult,
        **kwargs: Any
    ) -> None:
        """LLM 调用结束 — 业务代码自行记录"""
        pass

    def on_llm_error(
        self, error: BaseException,
        **kwargs: Any
    ) -> None:
        """LLM 调用异常"""
        try:
            logger.exception(f"LLM调用异常: error={error}")
        except Exception:
            pass


def get_logging_callbacks():
    """获取日志回调列表，用于 graph.invoke(config=...)"""
    return [LoggingHandler()]
```

- [ ] **Step 4: Update graph builder to register callbacks**

在 `builder.py` 的 `build_graph()` 函数中，`return graph.compile(...)` 之前不需要改——回调是在 invoke 时通过 config 传入的，不是编译时注册。

需要在调用 graph 的地方（session_service）传入回调。修改 `backend/src/services/session_service.py`：

在 `send_message` 和 `submit_clarification` 方法的 `graph_app.ainvoke()` 调用中，增加 callbacks 配置：

```python
from src.graph.callbacks import get_logging_callbacks

# 在 send_message 中：
result = await graph_app.ainvoke(
    initial_state,
    config={"callbacks": get_logging_callbacks()}
)

# 在 submit_clarification 中：
result = await graph_app.ainvoke(
    state,
    config={"callbacks": get_logging_callbacks()}
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_graph_callbacks.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/graph/callbacks.py backend/src/graph/builder.py backend/src/services/session_service.py backend/tests/test_graph_callbacks.py
git commit -m "feat: 添加LangGraph节点生命周期日志回调"
```

---

### Task 5: 业务日志埋点 - NLU + Executor + Insight

**Files:**
- Modify: `backend/src/graph/nodes.py` — nlu_node、executor_node、insight_node 加日志
- Modify: `backend/src/agents/insight_agent.py` — 规则引擎命中统计日志
- Modify: `backend/src/tools/insight_rules.py` — 规则引擎整体统计日志

**Interfaces:**
- Consumes:
  - `truncate_log()` from `src.config.context`
- Produces:
  - NLU 解析结果 INFO 日志
  - ES 查询摘要 INFO 日志
  - 规则引擎命中统计 INFO 日志

- [ ] **Step 1: Add logging to nlu_node**

在 `nlu_node` 函数中，成功解析后加日志：

```python
import logging
logger = logging.getLogger(__name__)
```

在 `return result` 前（成功分支）加：

```python
        # 日志：NLU 解析结果
        intent_summary = {
            "query_type": query_intent.get("query_type"),
            "metrics": query_intent.get("metrics"),
            "dimensions": query_intent.get("dimensions"),
            "time_range": query_intent.get("time_range"),
            "advertiser_ids": query_intent.get("advertiser_ids"),
            "filters": query_intent.get("filters"),
            "is_comparison": query_intent.get("is_comparison"),
        }
        logger.info(f"NLU解析完成: {intent_summary}")
```

在异常分支加日志：

```python
        logger.error(f"NLU解析失败: {e}")
```

- [ ] **Step 2: Add logging to executor_node**

在 `executor_node` 中，查询成功后加日志：

```python
import logging
logger = logging.getLogger(__name__)
```

在单个查询成功 return 前加：

```python
            # 日志：ES 查询结果
            data_count = len(result.get("data", [])) if result.get("data") else 0
            logger.info(f"ES查询完成: 结果条数={data_count}, 耗时={execution_time}ms")
```

在并行查询成功 return 前加：

```python
            total_data = sum(
                len(r.get("data", [])) if r.get("data") else 0
                for r in results
            )
            logger.info(f"ES查询完成(对比查询): 查询数={len(results)}, 总条数={total_data}, 耗时={execution_time}ms")
```

在异常分支加日志：

```python
        logger.exception(f"ES查询异常: error={e}")
```

- [ ] **Step 3: Add logging to insight_node**

在 `insight_node` 中，成功返回前加日志：

```python
import logging
logger = logging.getLogger(__name__)
```

在 `return` merged result 前加：

```python
        problem_ids = [p.id for p in all_problems]
        highlight_ids = [h.id for h in all_highlights]
        logger.info(
            f"洞察分析完成: 问题命中={problem_ids} ({len(all_problems)}条), "
            f"亮点命中={highlight_ids} ({len(all_highlights)}条)"
        )
```

在异常分支加日志：

```python
        logger.exception(f"洞察分析异常: error={e}")
```

- [ ] **Step 4: Add logging to insight_agent（规则引擎总览）**

在 `insight_agent` 函数返回前加日志，记录各规则命中情况。

找到返回 InsightResult 的位置，在返回前加：

```python
    problem_ids = [p.id for p in result.problems]
    highlight_ids = [h.id for p in result.highlights]
    logger.info(
        f"规则引擎执行完成[{dimension}]: 亮点={highlight_ids} ({len(result.highlights)}条), "
        f"问题={problem_ids} ({len(result.problems)}条)"
    )
```

> 注意：具体位置需要根据 insight_agent 的实际代码调整。如果有多条 return 路径，每条成功路径都要加。

- [ ] **Step 5: Verify existing tests still pass**

Run: `cd backend && python -m pytest tests/test_insight_rules.py tests/test_insight_integration.py tests/test_nlu_agent.py tests/test_executor_node.py -v --tb=short`
Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/graph/nodes.py backend/src/agents/insight_agent.py
git commit -m "feat: NLU/Executor/Insight 节点业务日志埋点"
```

---

### Task 6: 业务日志埋点 - Analyst + Reporter + Planner

**Files:**
- Modify: `backend/src/graph/nodes.py` — planner_node、analyst_node、reporter_node 加日志
- Modify: `backend/src/agents/analyst_agent.py` — LLM 调用摘要日志
- Modify: `backend/src/agents/reporter_agent.py` — 报告生成日志

**Interfaces:**
- Consumes:
  - `truncate_log()` from `src.config.context`
- Produces:
  - Planner 结果 INFO 日志
  - Analyst LLM 调用摘要 INFO 日志（prompt/response 截断 1000 字）
  - Reporter 最终结果 INFO 日志

- [ ] **Step 1: Add logging to planner_node**

在 `planner_node` 成功分支 return 前加：

```python
        logger.info(
            f"查询规划完成: 指标={result['query_request'].get('metrics')}, "
            f"维度={result['query_request'].get('group_by')}, "
            f"警告数={len(result['query_warnings'])}"
        )
```

异常分支加：

```python
        logger.error(f"查询规划失败: {e}")
```

- [ ] **Step 2: Add logging to analyst_agent (LLM 调用摘要)**

在 `analyst_agent.py` 中找到 LLM 调用的地方，在调用后加日志：

```python
import logging
logger = logging.getLogger(__name__)
from src.config.context import truncate_log
```

LLM 调用完成后：

```python
        # 日志：LLM 调用摘要
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = response.usage_metadata.get("input_tokens", 0)
            output_tokens = response.usage_metadata.get("output_tokens", 0)
            total_tokens = response.usage_metadata.get("total_tokens", 0)
            prompt_preview = truncate_log(str(prompt_content), settings.LOG_TRUNCATE_LEN)
            response_preview = truncate_log(str(response_content), settings.LOG_TRUNCATE_LEN)
            logger.info(
                f"LLM调用完成[analyst]: 输入={input_tokens}token, 输出={output_tokens}token, "
                f"总token={total_tokens}\n"
                f"  prompt: {prompt_preview}\n"
                f"  response: {response_preview}"
            )
```

> 注意：具体变量名需要根据 analyst_agent 的实际代码调整。核心是拿到 prompt 内容、response 内容、token 用量，然后用 truncate_log 截断后打 INFO 日志。

- [ ] **Step 3: Add logging to analyst_node**

在 `analyst_node` 成功分支 return 前加：

```python
        logger.info(f"分析完成: needs_drill_down={result.get('needs_drill_down', False)}")
```

异常分支加：

```python
        logger.exception(f"分析异常: error={e}")
```

- [ ] **Step 4: Add logging to reporter_node**

在 `reporter_node` 成功分支 return 前加：

```python
        # 结果摘要
        title = final_report.get("title", "")
        metric_count = len(final_report.get("metrics", []))
        highlight_count = len(final_report.get("highlights", []))
        logger.info(
            f"报告生成完成: 标题='{title}', 指标数={metric_count}, 亮点数={highlight_count}"
        )
```

异常分支加：

```python
        logger.exception(f"报告生成异常: error={e}")
```

- [ ] **Step 5: Verify existing tests still pass**

Run: `cd backend && python -m pytest tests/test_analyst_agent.py tests/test_reporter_agent.py tests/test_planner_agent.py tests/test_full_graph_flow.py -v --tb=short`
Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/graph/nodes.py backend/src/agents/analyst_agent.py backend/src/agents/reporter_agent.py
git commit -m "feat: Planner/Analyst/Reporter 节点业务日志埋点"
```

---

### Task 7: 业务日志埋点 - RAG 模块

**Files:**
- Modify: `backend/src/rag/agents.py` — 意图路由、检索、回答生成日志
- Modify: `backend/src/rag/retriever.py` — 检索结果日志

**Interfaces:**
- Consumes:
  - `truncate_log()` from `src.config.context`
- Produces:
  - 意图路由结果 INFO 日志
  - RAG 检索结果 INFO 日志
  - RAG 回答生成 INFO 日志

- [ ] **Step 1: Add logging to intent router**

在 `rag/agents.py` 的 `IntentRouter.classify()` 方法或其调用处加日志：

```python
import logging
logger = logging.getLogger(__name__)
```

在 `classify` 方法中，返回前加：

```python
        logger.info(f"意图路由: 用户输入='{user_input[:100]}', 结果={result}")
```

- [ ] **Step 2: Add logging to RAG retriever**

在 `rag/retriever.py` 中，检索完成后加日志：

```python
import logging
logger = logging.getLogger(__name__)
```

在 `RagRetriever.retrieve()` 返回前加：

```python
        doc_titles = [doc.get("title", "")[:50] for doc in results[:5]]
        logger.info(f"RAG检索完成: 命中文档数={len(results)}, top5={doc_titles}")
```

- [ ] **Step 3: Add logging to RAG answer generator**

在 `rag/agents.py` 的回答生成处加日志：

```python
        logger.info(f"RAG回答生成: 基于{len(docs)}篇文档生成回答")
```

- [ ] **Step 4: Verify existing tests still pass**

Run: `cd backend && python -m pytest tests/rag/ -v --tb=short`
Expected: All existing RAG tests still PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/rag/agents.py backend/src/rag/retriever.py
git commit -m "feat: RAG模块日志埋点（路由/检索/回答生成）"
```

---

### Task 8: 端到端验证

**Files:**
- Modify: (none — 验证用，不改代码)

**Interfaces:**
- 验证整个链路：请求进来 → 各节点日志 → 响应带 X-Request-ID → 日志文件写入

- [ ] **Step 1: 启动服务验证**

Run: `cd backend && python -m src.main &`
然后用 curl 发一个测试请求：

```bash
# 创建 session
curl -s -X POST http://localhost:8000/api/sessions -H "Content-Type: application/json" -d '{}'

# 发送消息（假设已有数据）
curl -s -i -X POST http://localhost:8000/api/sessions/<session_id>/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "查看所有广告主列表"}'
```

Expected:
- 响应 header 中有 `X-Request-ID`
- `backend/logs/app.log` 中有完整的请求链路日志
- 日志中包含：请求开始、进入各节点、离开各节点、NLU解析完成、ES查询完成、报告生成完成、请求完成
- 每条日志都带有相同的 request_id

- [ ] **Step 2: 验证 error.log**

故意触发一个错误（比如发一个格式不对的请求），然后检查 `backend/logs/error.log` 中有对应的 ERROR 日志和堆栈。

- [ ] **Step 3: 验证日志文件滚动配置**

检查 `logs/` 目录下有 `app.log` 和 `error.log` 两个文件。

- [ ] **Step 4: 停掉后台服务**

```bash
pkill -f "src.main"
```

- [ ] **Step 5: Commit (no code — just a verification commit message if needed, or skip)**

此步骤不需要提交代码，确认功能正常即可。
