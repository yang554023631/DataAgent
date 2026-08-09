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
