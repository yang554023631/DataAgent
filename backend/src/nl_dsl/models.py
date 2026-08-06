"""NL→DSL 数据模型"""
from typing import List, Optional, Dict, Any
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
