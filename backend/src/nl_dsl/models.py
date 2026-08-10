"""NL→DSL + CoT Analysis 数据模型（合并版）"""
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class QueryStep(BaseModel):
    """查询步骤"""
    step_id: str
    description: str
    index: str
    output_fields: List[str] = Field(default_factory=list)
    purpose: str = ""
    depends_on: List[str] = Field(default_factory=list)


class QueryPlan(BaseModel):
    """查询计划"""
    steps: List[QueryStep] = Field(default_factory=list)
    final_output: str = "step_1.output"

    def get_step(self, step_id: str) -> Optional[QueryStep]:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None


class RetryInfo(BaseModel):
    """重试信息（用于反思修正）"""
    attempt: int = 1  # 当前是第几次尝试（1=首次，2=第1次重试，3=第2次重试）
    failure_type: str = ""  # validation / execution / empty / abnormal
    error_message: str = ""
    previous_dsl: Optional[Dict[str, Any]] = None
    reflection: str = ""


class NlDslResult(BaseModel):
    """NL→DSL 查询结果"""
    display_type: str = "list"
    columns: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    query_context: Optional[Dict[str, Any]] = None  # 用于翻页


# ========== CoT Analysis Planner 数据模型 ==========

class QualityCheckType(str, Enum):
    """质量检查类型"""
    MAX_SERIES_COUNT = "max_series_count"
    MAX_ROWS = "max_rows"
    MAX_CATEGORIES = "max_categories"
    MIN_DATA_POINTS = "min_data_points"
    ALL_ZERO = "all_zero"
    EMPTY_RESULT = "empty_result"


class QualityAction(str, Enum):
    """质量检查建议动作"""
    HITL = "hitl"  # 人工介入
    TRIM_TOP = "trim_top"  # 截断前N个
    TRIM_OTHERS = "trim_others"  # 保留前N个，其余合并为"其他"
    WARN = "warn"  # 仅警告
    FAIL = "fail"  # 失败


class QualityIssue(BaseModel):
    """质量问题"""
    check_type: QualityCheckType
    severity: str  # "warning" | "error" | "hitl_required"
    message: str
    suggested_action: Optional[QualityAction] = None
    threshold: Optional[Any] = None
    actual: Optional[Any] = None


class QualityResult(BaseModel):
    """质量检查结果"""
    passed: bool
    issues: List[QualityIssue] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    actions: List[QualityAction] = Field(default_factory=list)


class EmptyCheckErrorType(str, Enum):
    """空结果检查错误类型"""
    INVALID_TIME_RANGE = "invalid_time_range"
    INVALID_METRICS = "invalid_metrics"
    NO_ENTITY_IDS = "no_entity_ids"
    NO_DOCUMENTS = "no_documents"
    NO_DATA_VALUES = "no_data_values"


class EmptyCheckResult(BaseModel):
    """空结果检查结果"""
    found_error: bool
    error_type: Optional[EmptyCheckErrorType] = None
    correction: Optional[Dict[str, Any]] = None
    hints: List[str] = Field(default_factory=list)


class FilterCondition(BaseModel):
    """单个过滤条件"""
    field: str                           # 字段名，如 campaign_id、data_value、creative_name
    operator: str                        # = / != / > / < / >= / <= / contains / in / match
    value: Any                           # 条件值
    dimension_slice: Optional[Dict[str, Any]] = None  # 受众维度切片，如 {audience_type: "gender", audience_tag: "male"}
    metric: Optional[str] = None         # 指标名称（for having 筛选）


class FilterStep(BaseModel):
    """单个筛选步骤"""
    step_id: str                         # step_1, step_2 ...
    step_type: str                       # where_filter / having_filter / cross_level_up / cross_level_down
    level: str                           # 本步操作的实体层级：advertiser / campaign / ad_group / creative
    index: str                           # 查询的索引：ad_stat_data / ad_stat_audience / campaign / adgroup / creative
    conditions: List[FilterCondition] = Field(default_factory=list)
    output_field: str                    # 输出的ID字段，如 campaign_id


class FilterPlan(BaseModel):
    """筛选计划"""
    filter_type: str                     # none / where / having / cross_level / mixed
    target_level: str                    # 最终目标实体层级
    steps: List[FilterStep] = Field(default_factory=list)
    entity_ids: Optional[List[Any]] = None  # 预定义的实体ID（用户直接指定时）


class FilterResult(BaseModel):
    """筛选执行结果"""
    entity_ids: List[Any] = Field(default_factory=list)
    entity_level: str
    total_count: int
    trace: List[Dict[str, Any]] = Field(default_factory=list)  # 每步的执行追踪
    truncated: bool = False  # 是否因超过500上限被截断


# ========== Analysis Models ==========

class AnalysisTimeRange(BaseModel):
    """分析时间范围"""
    start_date: str
    end_date: str
    granularity: Optional[str] = "day"  # day / week / month


class AnalysisComparison(BaseModel):
    """时期对比配置"""
    compare_start_date: str
    compare_end_date: str


class AnalysisChartConfig(BaseModel):
    """图表配置"""
    type: str  # line / bar / pie / kpi_card / table
    title: str
    x_axis: Optional[Dict[str, Any]] = None
    y_axis: Optional[Dict[str, Any]] = None
    series_field: Optional[str] = None
    series: Optional[List[Dict[str, Any]]] = None


class AnalysisDataTable(BaseModel):
    """数据表格"""
    columns: List[Dict[str, Any]]
    rows: List[Dict[str, Any]]


class AnalysisResult(BaseModel):
    """分析执行结果"""
    chart_data: Optional[Dict[str, Any]] = None  # {chart_config: ..., data: ...}
    data_table: Optional[AnalysisDataTable] = None
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


class AnalysisStep(BaseModel):
    """单个分析步骤"""
    step_id: str
    analysis_type: str  # entity_table / time_trend / period_comparison / audience_distribution / summary
    metrics: List[str]
    group_by_level: Optional[str] = None
    series_level: Optional[str] = None  # for multi-series trend
    audience_type: Optional[str] = None  # for audience distribution
    order_by: Optional[str] = None
    order_dir: str = "desc"
    limit: int = 100
    comparison: Optional[AnalysisComparison] = None
    chart_config: Optional[AnalysisChartConfig] = None


class AnalysisPlan(BaseModel):
    """分析计划"""
    analysis_type: str  # entity_table / time_trend / period_comparison / audience_distribution / summary
    time_range: AnalysisTimeRange
    metrics: List[str]
    group_by_level: Optional[str] = None  # for entity table
    series_level: Optional[str] = None  # for multi-series trend
    audience_type: Optional[str] = None  # for audience distribution
    order_by: Optional[str] = None
    order_dir: str = "desc"
    limit: int = 100
    comparison: Optional[AnalysisComparison] = None
    chart_config: Optional[AnalysisChartConfig] = None
    steps: List[AnalysisStep] = Field(default_factory=list)  # 支持多步骤分析
