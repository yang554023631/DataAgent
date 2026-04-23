from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from .common import TimeRange, Filter

class Ambiguity(BaseModel):
    has_ambiguity: bool = False
    type: Optional[str] = None
    reason: Optional[str] = None
    options: List[Dict] = Field(default_factory=list)

class QueryIntent(BaseModel):
    """结构化查询意图"""
    time_range: TimeRange
    metrics: List[str]
    group_by: List[str] = Field(default_factory=list)
    filters: List[Filter] = Field(default_factory=list)
    is_incremental: bool = False
    intent_type: str = Field(default="query", description="query / attribution / compare")
    ambiguity: Ambiguity = Field(default_factory=Ambiguity)
