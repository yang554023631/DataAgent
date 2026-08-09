"""CoT Analysis Planner 数据模型"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


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
