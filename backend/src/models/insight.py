from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Dict, Any, List


class InsightType(str, Enum):
    PROBLEM = "problem"
    HIGHLIGHT = "highlight"
    INFO = "info"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class InsightSource(str, Enum):
    RULE_ENGINE = "rule_engine"
    LLM = "llm"


class Insight(BaseModel):
    id: str = Field(description="洞察唯一标识")
    type: InsightType = Field(description="洞察类型: problem/highlight/info")
    name: str = Field(description="洞察名称")
    severity: Severity = Field(description="严重程度: high/medium/low")
    confidence: float = Field(ge=0, le=1, description="置信度 0-1")
    source: InsightSource = Field(description="来源: rule_engine/llm")
    metric: str = Field(description="关联指标")
    dimension_key: Optional[str] = Field(default=None, description="维度键")
    dimension_value: Optional[str] = Field(default=None, description="维度值")
    current_value: Optional[float] = Field(default=None, description="当前值")
    baseline_value: Optional[float] = Field(default=None, description="基线值")
    evidence: str = Field(description="证据描述")
    suggestion: Optional[str] = Field(default=None, description="建议")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class InsightResult(BaseModel):
    problems: List[Insight] = Field(default_factory=list, description="问题列表")
    highlights: List[Insight] = Field(default_factory=list, description="亮点列表")
    summary: Optional[str] = Field(default=None, description="洞察摘要")
    llm_insights: List[Insight] = Field(default_factory=list, description="LLM 生成的洞察")
    meta: Dict[str, Any] = Field(default_factory=dict, description="元数据（无数据标记等）")

    def has_insights(self) -> bool:
        """检查是否有任何洞察"""
        return len(self.problems) > 0 or len(self.highlights) > 0 or len(self.llm_insights) > 0
