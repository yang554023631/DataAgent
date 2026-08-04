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
        run_id = kwargs.get("run_id", "")
        if not name or not run_id:
            return

        # 提取 LangGraph 节点真实名称：graph.step.nodes.<name> -> <name>
        if name.startswith("graph.step.nodes."):
            name = name.split(".")[-1]

        # 过滤掉 graph 本身的顶层调用，只记录节点
        if name in ("LangGraph", "StateGraph"):
            return

        try:
            self._node_start_times[run_id] = (name, time.time())
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
        run_id = kwargs.get("run_id", "")
        if not run_id:
            return

        try:
            # Get node name and start time from run_id
            name, start_time = self._node_start_times.pop(run_id, (None, None))
            if name and start_time is not None:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(f"离开节点: {name}, 耗时={duration_ms}ms")
        except Exception:
            pass

    def on_chain_error(
        self,
        error: BaseException,
        **kwargs: Any
    ) -> None:
        """链/节点异常时调用"""
        run_id = kwargs.get("run_id", "")
        name = kwargs.get("name", "unknown")

        # If we have a run_id, check if we tracked it
        if run_id:
            tracked_name, _ = self._node_start_times.pop(run_id, (None, None))
            if tracked_name:
                name = tracked_name

        # Extract node name if it's a LangGraph node
        if name.startswith("graph.step.nodes."):
            name = name.split(".")[-1]

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
