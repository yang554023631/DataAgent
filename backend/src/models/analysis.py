from pydantic import BaseModel, Field
from typing import Optional, List

class Anomaly(BaseModel):
    type: str = Field(description="sudden_change, outlier, trend")
    metric: str
    dimension_key: Optional[str] = None
    dimension_value: Optional[str] = None
    current_value: float
    change_percent: Optional[float] = None
    z_score: Optional[float] = None
    severity: str = Field(description="low, medium, high")

class AnalysisResult(BaseModel):
    """数据分析结果"""
    summary: str
    anomalies: List[Anomaly] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
