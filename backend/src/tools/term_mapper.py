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
    "覆盖": "reach",
    "覆盖人数": "reach",
    "覆盖量": "reach",
    "触达": "reach",
    "触达人数": "reach",
    "触达量": "reach",
    "reach": "reach",
    "Reach": "reach",
    "频次": "frequency",
    "曝光频次": "frequency",
    "frequency": "frequency",
    "Frequency": "frequency",
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
    "分天": "data_date",
    "天": "data_date",
    "小时": "data_hour",
    "分时": "data_hour",
    "时段": "data_hour",
    "月份": "data_month",
    "按月": "data_month",
    "每月": "data_month",
    "月": "data_month",
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
    "受众": "audience_gender",  # 默认受众按性别细分
    "分受众": "audience_gender",
    "系统版本": "audience_os_version",
    "操作系统版本": "audience_os_version",
    "版本": "audience_os_version",
    "国家": "audience_country",
    "按国家": "audience_country",
    "国家地区": "audience_country",
    "城市": "audience_city",
    "按城市": "audience_city",
    "地域": "audience_city",
    "行业": "industry",
    "按行业": "industry",
    "行业分类": "industry",
    "地区": "region_id",
    "区域": "region_id",
    "设备": "device_type",
}

FILTER_VALUE_MAPPING = {
    "安卓": {"field": "audience_os", "value": 2},
    "Android": {"field": "audience_os", "value": 2},
    "苹果": {"field": "audience_os", "value": 1},
    "iOS": {"field": "audience_os", "value": 1},
    "男性": {"field": "audience_gender", "value": 1},
    "女性": {"field": "audience_gender", "value": 2},
    "iOS 15": {"field": "audience_os_version", "value": 11},
    "iOS 16": {"field": "audience_os_version", "value": 12},
    "iOS 17": {"field": "audience_os_version", "value": 13},
    "Android 10": {"field": "audience_os_version", "value": 21},
    "Android 11": {"field": "audience_os_version", "value": 22},
    "Android 12": {"field": "audience_os_version", "value": 23},
    "Android 13": {"field": "audience_os_version", "value": 24},
    "Android 14": {"field": "audience_os_version", "value": 25},
    "中国": {"field": "audience_country", "value": 101},
    "美国": {"field": "audience_country", "value": 102},
    "日本": {"field": "audience_country", "value": 103},
    "德国": {"field": "audience_country", "value": 104},
    "英国": {"field": "audience_country", "value": 105},
    "北京": {"field": "audience_city", "value": 2001},
    "上海": {"field": "audience_city", "value": 2002},
    "广州": {"field": "audience_city", "value": 2003},
    "深圳": {"field": "audience_city", "value": 2004},
    "杭州": {"field": "audience_city", "value": 2005},
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

    # 移除空格，方便匹配连续词（如"按 性别"变成"按性别"）
    # 将中文逗号"、"替换为"和"，支持"按性别、月细分"这种写法
    text_no_spaces = text.replace(" ", "").replace("、", "和")

    # 只匹配明确表示维度分组的模式，避免误匹配：
    # 如"三个月"中的"月"不应该匹配，"按月份"、"按月细分"才应该匹配
    dimension_patterns = [
        ("按天", "data_date"), ("按日期", "data_date"), ("分天", "data_date"), ("每天", "data_date"),
        ("按小时", "data_hour"), ("分时", "data_hour"), ("按时段", "data_hour"),
        ("按月", "data_month"), ("按月份", "data_month"), ("分月", "data_month"), ("每月", "data_month"),
        ("按周", "data_week"), ("按星期", "data_week"), ("分周", "data_week"), ("每周", "data_week"),
        ("按渠道", "campaign_id"), ("按活动", "campaign_id"), ("按广告活动", "campaign_id"),
        ("按广告组", "adgroup_id"), ("按组", "adgroup_id"),
        ("按创意", "creative_id"), ("按素材", "creative_id"),
        ("按性别", "audience_gender"), ("分性别", "audience_gender"),
        ("按年龄", "audience_age"), ("按年龄段", "audience_age"), ("分年龄", "audience_age"),
        ("按平台", "audience_os"), ("按系统", "audience_os"), ("按操作系统", "audience_os"),
        ("按系统版本", "audience_os_version"), ("按操作系统版本", "audience_os_version"), ("分版本", "audience_os_version"),
        ("按国家", "audience_country"), ("分国家", "audience_country"),
        ("按城市", "audience_city"), ("分城市", "audience_city"), ("分地域", "audience_city"),
        ("按行业", "industry"), ("分行业", "industry"),
        ("按兴趣", "audience_interest"), ("按兴趣标签", "audience_interest"), ("分兴趣", "audience_interest"),
        ("按受众", "audience_gender"), ("分受众", "audience_gender"),
        ("按地区", "region_id"), ("按区域", "region_id"),
        ("按设备", "device_type"),
        # "X和Y细分" 这种多维度组合模式
        # 规则：每个维度都需要 "X和" (作为第一个维度) 和 "和X" (作为后续维度)
        ("性别和", "audience_gender"), ("和性别", "audience_gender"),
        ("年龄和", "audience_age"), ("和年龄", "audience_age"),
        ("月份和", "data_month"), ("和月份", "data_month"), ("和月", "data_month"),
        ("周和", "data_week"), ("和周", "data_week"),
        ("天和", "data_date"), ("和天", "data_date"), ("日期和", "data_date"), ("和日期", "data_date"),
        ("小时和", "data_hour"), ("和小时", "data_hour"), ("时段和", "data_hour"), ("和时段", "data_hour"),
        ("平台和", "audience_os"), ("和平台", "audience_os"), ("系统和", "audience_os"), ("和系统", "audience_os"),
        ("系统版本和", "audience_os_version"), ("和系统版本", "audience_os_version"),
        ("国家和", "audience_country"), ("和国家", "audience_country"),
        ("城市和", "audience_city"), ("和城市", "audience_city"), ("地域和", "audience_city"), ("和地域", "audience_city"),
        ("行业和", "industry"), ("和行业", "industry"),
        ("兴趣和", "audience_interest"), ("和兴趣", "audience_interest"),
        ("渠道和", "campaign_id"), ("和渠道", "campaign_id"),
        ("广告组和", "adgroup_id"), ("和广告组", "adgroup_id"),
        ("创意和", "creative_id"), ("和创意", "creative_id"),
    ]

    for pattern, standard in dimension_patterns:
        if pattern in text_no_spaces and standard not in result:
            result.append(standard)

    # 处理维度冲突：更细粒度的维度优先
    # audience_os_version (系统版本) 比 audience_os (操作系统) 更细，保留前者
    if 'audience_os_version' in result and 'audience_os' in result:
        result.remove('audience_os')

    return result
