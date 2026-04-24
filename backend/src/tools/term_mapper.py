from typing import List, Dict
from langchain_core.tools import tool

METRIC_MAPPING = {
    "曝光": "impressions",
    "展示": "impressions",
    "展示量": "impressions",
    "impression": "impressions",
    "点击": "clicks",
    "点击量": "clicks",
    "click": "clicks",
    "花费": "cost",
    "消耗": "cost",
    "消费": "cost",
    "成本": "cost",
    "转化": "conversions",
    "转化数": "conversions",
    "转化量": "conversions",
    "conversion": "conversions",
    "点击率": "ctr",
    "CTR": "ctr",
    "转化率": "cvr",
    "CVR": "cvr",
    "投产比": "roi",
    "ROI": "roi",
}

DIMENSION_MAPPING = {
    "日期": "data_date",
    "按天": "data_date",
    "每天": "data_date",
    "小时": "data_hour",
    "分时": "data_hour",
    "时段": "data_hour",
    "月份": "data_month",
    "按月": "data_month",
    "每月": "data_month",
    "周": "data_week",
    "按周": "data_week",
    "每周": "data_week",
    "渠道": "campaign_id",
    "广告活动": "campaign_id",
    "活动": "campaign_id",
    "广告组": "adgroup_id",
    "组": "adgroup_id",
    "创意": "creative_id",
    "素材": "creative_id",
    "性别": "audience_gender",
    "按性别": "audience_gender",
    "年龄段": "audience_age",
    "年龄": "audience_age",
    "按年龄": "audience_age",
    "系统": "audience_os",
    "平台": "audience_os",
    "操作系统": "audience_os",
    "按平台": "audience_os",
    "按系统": "audience_os",
    "OS": "audience_os",
    "兴趣": "audience_interest",
    "兴趣标签": "audience_interest",
    "按兴趣": "audience_interest",
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
        # 支持中英文关键词匹配
        if term.lower() in text.lower() and standard not in result:
            result.append(standard)
    # 如果没有识别到任何指标，默认返回曝光和点击
    return result if result else ["impressions", "clicks"]

@tool
def map_dimensions(text: str) -> List[str]:
    """将自然语言维度名称映射为标准维度名"""
    result = []
    for term, standard in DIMENSION_MAPPING.items():
        if term in text and standard not in result:
            result.append(standard)
    return result
