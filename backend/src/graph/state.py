from typing import TypedDict, Optional, List, Dict, Annotated
from datetime import datetime
from langgraph.graph import add_messages

def append_history(left: List[Dict], right: List[Dict]) -> List[Dict]:
    """追加历史记录，最多保留20条"""
    result = left.copy()
    result.extend(right)
    if len(result) > 20:
        result = result[-20:]
    return result

class AdReportState(TypedDict):
    """LangGraph 全局状态"""
    # 会话基本信息
    session_id: str
    user_id: Optional[str]

    # 用户输入
    user_input: str
    conversation_history: Annotated[List[Dict], append_history]

    # 意图理解输出
    query_intent: Optional[Dict]

    ambiguity: Optional[Dict]

    # 人机澄清输出
    user_feedback: Optional[Dict]
    clarification_count: int

    # 查询规划输出
    query_request: Optional[Dict]  # 向后兼容：单个查询
    query_requests: List[Dict]     # 支持多个查询（对比查询）
    query_warnings: List[str]

    # 数据执行输出
    query_result: Optional[Dict]    # 向后兼容：单个结果
    query_results: List[Dict]       # 支持多个结果（对比查询）
    execution_time_ms: Optional[int]

    # 数据分析输出
    analysis_result: Optional[Dict]
    drill_down_level: int
    needs_drill_down: bool

    # 报告生成输出
    final_report: Optional[Dict]

    # 广告主选择
    advertiser_ids: List[str]
    show_advertiser_list: bool

    # 执行控制
    error: Optional[Dict]
