from typing import List, Dict, Any
from pydantic import BaseModel
from langchain_core.tools import tool

class ClarificationQuestion(BaseModel):
    question: str
    options: List[Dict[str, str]]
    allow_custom_input: bool = False

@tool
def generate_clarification_options(
    ambiguity_type: str,
    context: Dict[str, Any]
) -> ClarificationQuestion:
    """
    根据歧义类型生成澄清问题和选项

    ambiguity_type: metric, dimension, time, advertiser, query_too_large, empty_data
    """

    if ambiguity_type == "metric":
        return ClarificationQuestion(
            question="您想查看哪些指标？",
            options=[
                {"value": "impressions,clicks", "label": "曝光和点击"},
                {"value": "ctr,cvr", "label": "CTR和CVR"},
                {"value": "cost,roi", "label": "花费和ROI"}
            ],
            allow_custom_input=True
        )

    if ambiguity_type == "time":
        return ClarificationQuestion(
            question="您想查询哪个时间范围的数据？",
            options=[
                {"value": "today", "label": "今天"},
                {"value": "yesterday", "label": "昨天"},
                {"value": "last_7_days", "label": "最近7天"},
                {"value": "last_week", "label": "上周"}
            ],
            allow_custom_input=True
        )

    if ambiguity_type == "query_too_large":
        estimated_rows = context.get("estimated_rows", 1000)
        return ClarificationQuestion(
            question=f"这个查询预计返回约 {estimated_rows} 条数据，可能耗时较长，是否继续？",
            options=[
                {"value": "confirm", "label": "确认查询"},
                {"value": "reduce_to_month", "label": "改成按月汇总"},
                {"value": "narrow_time", "label": "缩小时间范围"}
            ],
            allow_custom_input=False
        )

    # 默认
    custom_options = context.get("options", [])
    if custom_options:
        return ClarificationQuestion(
            question=context.get("question", "请选择以下选项："),
            options=custom_options,
            allow_custom_input=True
        )

    return ClarificationQuestion(
        question="请选择以下选项：",
        options=context.get("options", []),
        allow_custom_input=True
    )
