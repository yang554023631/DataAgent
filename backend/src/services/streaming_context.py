"""
SSE 流式响应上下文

使用 contextvars 存储当前请求的事件队列，让深层节点能够实时推送进度事件。
每个请求有独立的队列，并发安全。
"""
import contextvars
from asyncio import Queue
from typing import Optional, Dict, Any

# 当前请求的 SSE 事件队列
# - None: 当前不是流式请求，不需要实时推送
# - Queue[Dict[str, Any]]: 流式请求，事件推送到此队列
sse_event_queue: contextvars.ContextVar[Optional[Queue[Dict[str, Any]]]] = \
    contextvars.ContextVar("sse_event_queue", default=None)


def get_sse_queue() -> Optional[Queue[Dict[str, Any]]]:
    """获取当前上下文的 SSE 事件队列"""
    return sse_event_queue.get()


def set_sse_queue(queue: Optional[Queue[Dict[str, Any]]]) -> None:
    """设置当前上下文的 SSE 事件队列"""
    sse_event_queue.set(queue)
