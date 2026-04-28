from pydantic import BaseModel, Field
from typing import Optional, List, Any
from .common import Filter

class ChartConfig(BaseModel):
    type: str = Field(description="line, bar, pie, table")
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    limit: Optional[int] = None

class QueryRequest(BaseModel):
    """最终查询请求，传给CustomReport"""
    index_type: str = Field(default="general", description="general, audience")
    time_range: dict
    metrics: List[str]
    group_by: List[str] = Field(default_factory=list)
    advertiser_ids: List[int] = Field(default_factory=list)
    filters: List[Filter] = Field(default_factory=list)
    chart_config: Optional[ChartConfig] = None

class QueryResult(BaseModel):
    """查询结果"""
    success: bool
    total_rows: int = 0
    data: List[dict] = Field(default_factory=list)
    execution_time_ms: Optional[int] = None
    error_type: Optional[str] = None
    message: Optional[str] = None
    suggestions: List[str] = Field(default_factory=list)
