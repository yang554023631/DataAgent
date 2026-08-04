"""日志配置模块

提供统一的日志初始化，包含：
- 自定义格式（带 request_id / session_id）
- 文件输出（按天滚动）
- 控制台输出
- 错误日志单独文件
"""
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
