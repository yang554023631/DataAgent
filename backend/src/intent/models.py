"""
意图识别相关 Pydantic 模型
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ==================== 顶层分类 ====================

class TopClassificationResult(BaseModel):
    """顶层意图分类结果"""
    category: str = Field(description="report / knowledge / out_of_domain")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度 0.0~1.0")
    reason: str = Field(default="", description="判断依据，用于日志")
    source: str = Field(default="llm", description="rule_fastpath / llm")


# ==================== 报表意图 ====================

class ReportTimeRange(BaseModel):
    """时间范围"""
    start_date: str = Field(description="YYYY-MM-DD")
    end_date: str = Field(description="YYYY-MM-DD")
    unit: str = Field(default="day", description="day / week / month")
    is_lifetime: bool = Field(default=False, description="是否为广告生命周期")


class ReportIntentResult(BaseModel):
    """报表意图识别结果"""
    # 必填字段
    advertiser_ids: List[str] = Field(default_factory=list)
    time_range: Optional[ReportTimeRange] = None
    metrics: List[str] = Field(default_factory=list)
    ad_level: Optional[str] = Field(default=None, description="campaign / ad_group / creative")

    # 可选字段
    group_by: List[str] = Field(default_factory=list)
    filters: List[Dict[str, Any]] = Field(default_factory=list)
    is_comparison: bool = False
    compare_time_range: Optional[ReportTimeRange] = None
    top_n: Optional[int] = None
    chart_type: Optional[str] = None

    # 元信息
    confidence: float = Field(default=1.0, description="整体置信度")
    alias_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="别名映射记录，{用户原文: 标准名}"
    )


# ==================== 澄清信息 ====================

class ClarificationInfo(BaseModel):
    """澄清信息"""
    type: str = Field(description=(
        "澄清类型: intent_confirm / missing_advertiser / missing_time_range / "
        "missing_metrics / missing_ad_level / unsupported_metric / "
        "unsupported_dimension / alias_confirm / knowledge_scope_guide / "
        "knowledge_clarify"
    ))
    question: str = Field(description="向用户展示的问题")
    options: List[Dict[str, str]] = Field(
        default_factory=list,
        description="选项列表，每项 {value, label}"
    )
    allow_custom_input: bool = Field(
        default=True,
        description="是否允许用户自由输入"
    )
    missing_fields: List[str] = Field(
        default_factory=list,
        description="缺失的字段列表，用于层内恢复"
    )


# ==================== 知识意图（占位，Phase 2 实现） ====================

class KnowledgeIntentResult(BaseModel):
    """知识问答意图识别结果（Phase 2 实现）"""
    question_type: str = Field(default="general")
    core_topics: List[str] = Field(default_factory=list)
    query_rewrite: str = Field(default="")
    confidence: float = Field(default=1.0)