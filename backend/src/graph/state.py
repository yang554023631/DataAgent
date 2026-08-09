from typing import TypedDict, Optional, List, Dict, Annotated, Any
from datetime import datetime
from langgraph.graph import add_messages
from src.models.insight import InsightResult

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

    # ========== 新意图识别架构字段 ==========
    # 顶层分类结果
    intent_category: Optional[str]       # report / knowledge / out_of_domain
    intent_confidence: float             # 0.0 ~ 1.0
    intent_classify_source: str          # rule_fastpath / llm
    intent_reason: str                   # 判断依据

    # 回退计数
    reentry_count: int                   # 回退到第一层的次数，默认 0

    # 澄清相关
    needs_clarification: bool            # 是否需要澄清（触发 interrupt）
    clarification: Optional[Dict]        # {type, question, options, allow_custom_input, missing_fields}
    clarify_next: Optional[str]          # 澄清后下一步方向
    pending_clarification_input: Optional[str]  # 澄清后的用户输入（待处理）

    # 拒答相关
    reject_reason: Optional[str]         # top_level / knowledge_scope

    # 报表意图（扩展，替代原 query_intent 的部分职责）
    report_intent_result: Optional[Dict]  # ReportIntentResult 的 dict 形式

    # NL→DSL 查询相关
    query_route: Optional[str]           # "structured" / "nl_dsl"
    route_reason: Optional[str]          # 路由判断依据
    analysis_type: Optional[str]         # 分析类型提示
    nl_dsl_result: Optional[Dict]        # NL→DSL 查询结果（中间格式）
    query_context: Optional[Dict]        # 翻页上下文（不返回前端）

    # ========== 旧字段（保持向后兼容） ==========
    # RAG 相关字段
    query_type: Optional[str]  # "report" 或 "knowledge"
    rag_context: List[str]
    rag_answer: Optional[str]

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

    # 洞察分析输出
    insights: Optional[InsightResult]

    # 报告生成输出
    final_report: Optional[Dict]

    # 广告主选择
    advertiser_ids: List[str]
    show_advertiser_list: bool

    # ========== CoT 分析节点字段 ==========
    # CoT 规划结果
    analysis_plan: Optional[Dict]  # AnalysisPlanResult 的 dict 形式
    field_context: Optional[Dict]  # FieldContext 的 dict 形式
    cot_reasoning: Optional[Dict]  # CotReasoning 的 dict 形式

    # 执行结果
    filter_result: Optional[Dict]  # FilterResult 的 dict 形式
    chart_data: Optional[Dict]  # AnalysisResult 的 dict 形式
    quality_result: Optional[Dict]  # QualityResult 的 dict 形式

    # HITL 相关
    hitl_request: Optional[Dict]  # 澄清请求（如果需要 HITL）

    # 执行追踪
    execution_trace: List[Dict]  # 各步骤的执行追踪信息

    # 执行控制
    error: Optional[Dict]
