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
