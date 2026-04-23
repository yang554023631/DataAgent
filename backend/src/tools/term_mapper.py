from typing import List, Dict
from langchain_core.tools import tool

METRIC_MAPPING = {
    "曝光": "impressions",
    "展示": "impressions",
    "展示量": "impressions",
    "点击": "clicks",
    "点击量": "clicks",
    "花费": "cost",
    "消耗": "cost",
    "点击率": "ctr",
    "CTR": "ctr",
    "转化率": "cvr",
    "CVR": "cvr",
    "投产比": "roi",
    "ROI": "roi",
}

DIMENSION_MAPPING = {
    "日期": "data_date",
    "渠道": "campaign_id",
    "广告组": "adgroup_id",
    "创意": "creative_id",
    "性别": "audience_gender",
    "年龄段": "audience_age",
    "年龄": "audience_age",
    "系统": "audience_os",
    "平台": "audience_os",
    "OS": "audience_os",
    "兴趣": "audience_interest",
}

FILTER_VALUE_MAPPING = {
    "安卓": {"field": "audience_os", "value": 2},
    "Android": {"field": "audience_os", "value": 2},
    "苹果": {"field": "audience_os", "value": 1},
    "iOS": {"field": "audience_os", "value": 1},
    "男性": {"field": "audience_gender", "value": 1},
    "女性": {"field": "audience_gender", "value": 2},
}

@tool
def map_metrics(text: str) -> List[str]:
    """将自然语言指标名称映射为标准指标名"""
    result = []
    for term, standard in METRIC_MAPPING.items():
        if term in text and standard not in result:
            result.append(standard)
    return result if result else ["impressions", "clicks"]

@tool
def map_dimensions(text: str) -> List[str]:
    """将自然语言维度名称映射为标准维度名"""
    result = []
    for term, standard in DIMENSION_MAPPING.items():
        if term in text and standard not in result:
            result.append(standard)
    return result
