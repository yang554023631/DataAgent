"""
字段映射与元数据配置

提供 ES 原始字段 → 显示名称 的映射，以及同义词 → 标准字段名 的反向映射。
覆盖维度字段和指标（长表 data_type 模型）。

后续 Schema RAG 完善后可以从 PG 动态加载，这里是内置 fallback。
"""
from typing import Dict, List, Optional


# ==================== 维度字段映射 ====================
# key: ES 字段名, value: { "display_name_cn": str, "display_name_en": str, "synonyms": [str] }
DIMENSION_FIELDS: Dict[str, dict] = {
    "advertiser_id": {
        "display_name_cn": "广告主ID",
        "display_name_en": "Advertiser ID",
        "synonyms": ["广告主", "advertiser", "广告主编号"],
    },
    "campaign_id": {
        "display_name_cn": "计划ID",
        "display_name_en": "Campaign ID",
        "synonyms": ["计划", "campaign", "广告计划", "推广计划"],
    },
    "adgroup_id": {
        "display_name_cn": "广告组ID",
        "display_name_en": "Ad Group ID",
        "synonyms": ["广告组", "adgroup", "ad_group", "单元", "推广单元"],
    },
    "creative_id": {
        "display_name_cn": "创意ID",
        "display_name_en": "Creative ID",
        "synonyms": ["创意", "creative", "广告创意"],
    },
    "data_date": {
        "display_name_cn": "日期",
        "display_name_en": "Date",
        "synonyms": ["日期", "date", "天", "按天"],
    },
    "data_month": {
        "display_name_cn": "月份",
        "display_name_en": "Month",
        "synonyms": ["月份", "month", "按月"],
    },
    "data_week": {
        "display_name_cn": "周",
        "display_name_en": "Week",
        "synonyms": ["周", "week", "按周"],
    },
    "data_hour": {
        "display_name_cn": "小时",
        "display_name_en": "Hour",
        "synonyms": ["小时", "hour", "按时"],
    },
    "channel": {
        "display_name_cn": "渠道",
        "display_name_en": "Channel",
        "synonyms": ["渠道", "channel", "媒体", "流量来源"],
    },
    "industry": {
        "display_name_cn": "行业",
        "display_name_en": "Industry",
        "synonyms": ["行业", "industry", "行业分类"],
    },
    "audience_gender": {
        "display_name_cn": "性别",
        "display_name_en": "Gender",
        "synonyms": ["性别", "gender"],
    },
    "audience_age": {
        "display_name_cn": "年龄段",
        "display_name_en": "Age Group",
        "synonyms": ["年龄", "age", "年龄段"],
    },
    "audience_os": {
        "display_name_cn": "操作系统",
        "display_name_en": "OS",
        "synonyms": ["系统", "os", "操作系统"],
    },
    "audience_city": {
        "display_name_cn": "城市",
        "display_name_en": "City",
        "synonyms": ["城市", "city", "地域"],
    },
    "audience_interest": {
        "display_name_cn": "兴趣标签",
        "display_name_en": "Interest",
        "synonyms": ["兴趣", "interest", "兴趣标签"],
    },
}


# ==================== 指标映射（长表 data_type 模型） ====================
# key: 指标标准英文名, value: { data_type, display_name_cn, display_name_en, synonyms }
METRICS: Dict[str, dict] = {
    "impressions": {
        "data_type": 1,
        "display_name_cn": "曝光量",
        "display_name_en": "Impressions",
        "synonyms": ["曝光", "曝光量", "展示", "展示量", "impression", "impressions", "show"],
    },
    "clicks": {
        "data_type": 2,
        "display_name_cn": "点击量",
        "display_name_en": "Clicks",
        "synonyms": ["点击", "点击量", "click", "clicks", "点击数"],
    },
    "cost": {
        "data_type": 3,
        "display_name_cn": "消耗",
        "display_name_en": "Cost",
        "synonyms": ["消耗", "花费", "成本", "费用", "cost", "spend", "spending", "消费"],
    },
    "conversions": {
        "data_type": 4,
        "display_name_cn": "转化数",
        "display_name_en": "Conversions",
        "synonyms": ["转化", "转化数", "转化量", "conversion", "conversions", "convert"],
    },
    "reach": {
        "data_type": 5,
        "display_name_cn": "触达",
        "display_name_en": "Reach",
        "synonyms": ["触达", "reach", "到达", "到达量"],
    },
    "frequency": {
        "data_type": 6,
        "display_name_cn": "频次",
        "display_name_en": "Frequency",
        "synonyms": ["频次", "frequency", "曝光频次", "平均频次"],
    },
}

# data_type 数值 → 指标标准名的反向映射
DATA_TYPE_TO_METRIC: Dict[int, str] = {
    info["data_type"]: name for name, info in METRICS.items()
}


# ==================== 衍生/计算指标 ====================
DERIVED_METRICS: Dict[str, dict] = {
    "ctr": {
        "display_name_cn": "点击率",
        "display_name_en": "CTR",
        "synonyms": ["点击率", "ctr", "点击通过率"],
    },
    "cpc": {
        "display_name_cn": "单次点击成本",
        "display_name_en": "CPC",
        "synonyms": ["cpc", "单次点击成本", "平均点击成本"],
    },
    "cpm": {
        "display_name_cn": "千次曝光成本",
        "display_name_en": "CPM",
        "synonyms": ["cpm", "千次曝光成本", "千次展示成本"],
    },
    "conversion_rate": {
        "display_name_cn": "转化率",
        "display_name_en": "Conversion Rate",
        "synonyms": ["转化率", "conversion_rate", "cvr"],
    },
    "roi": {
        "display_name_cn": "ROI",
        "display_name_en": "ROI",
        "synonyms": ["roi", "投入产出比", "投资回报率"],
    },
}


# ==================== 工具函数 ====================

def get_dimension_display_name(field_name: str, lang: str = "cn") -> str:
    """获取维度字段的显示名"""
    info = DIMENSION_FIELDS.get(field_name)
    if not info:
        return field_name  # 找不到映射就返回原名
    return info["display_name_cn"] if lang == "cn" else info["display_name_en"]


def get_metric_by_data_type(data_type: int) -> Optional[dict]:
    """根据 data_type 获取指标信息"""
    metric_name = DATA_TYPE_TO_METRIC.get(data_type)
    if not metric_name:
        return None
    return {"name": metric_name, **METRICS[metric_name]}


def get_metric_display_name(metric_name: str, lang: str = "cn") -> str:
    """获取指标的显示名"""
    info = METRICS.get(metric_name) or DERIVED_METRICS.get(metric_name)
    if not info:
        return metric_name
    return info["display_name_cn"] if lang == "cn" else info["display_name_en"]


def extract_data_types_from_dsl(dsl: dict) -> List[int]:
    """
    从 ES DSL 中提取所有 data_type 值。

    递归检查 query.bool.filter / must / should 中的 term / terms data_type。
    返回去重后的 data_type 列表。
    """
    if not dsl or not isinstance(dsl, dict):
        return []

    data_types = []

    def _walk(node):
        if not isinstance(node, dict):
            return
        # term 查询: { "term": { "data_type": 3 } }
        if "term" in node and isinstance(node["term"], dict):
            if "data_type" in node["term"]:
                val = node["term"]["data_type"]
                if isinstance(val, (int, str)):
                    data_types.append(int(val))
        # terms 查询: { "terms": { "data_type": [1, 2, 3] } }
        if "terms" in node and isinstance(node["terms"], dict):
            if "data_type" in node["terms"]:
                vals = node["terms"]["data_type"]
                if isinstance(vals, list):
                    for v in vals:
                        data_types.append(int(v))
                elif isinstance(vals, (int, str)):
                    data_types.append(int(vals))
        # 递归 bool 子句
        for key in ("bool", "filter", "must", "must_not", "should"):
            if key in node:
                val = node[key]
                if isinstance(val, list):
                    for item in val:
                        _walk(item)
                elif isinstance(val, dict):
                    _walk(val)
        # 递归 query 层
        if "query" in node:
            _walk(node["query"])
        # 递归 post_filter
        if "post_filter" in node:
            _walk(node["post_filter"])

    _walk(dsl)
    return list(set(data_types))


def extract_agg_field_mapping(dsl: dict) -> Dict[str, str]:
    """
    从 ES DSL 的 aggs 部分提取「聚合名称 → 实际字段名」的映射。

    支持：
    - terms 聚合: by_campaign → campaign_id
    - sum/avg/min/max 等指标聚合: total_consumption → data_value
    - date_histogram: by_date → data_date

    用于将 ResultFormatter 返回的聚合列名（聚合名）映射回实际 ES 字段名，
    再进一步映射为用户友好的中文名。
    """
    if not dsl or not isinstance(dsl, dict):
        return {}

    mapping = {}

    def _walk_aggs(aggs_node: dict):
        if not isinstance(aggs_node, dict):
            return
        for agg_name, agg_def in aggs_node.items():
            if not isinstance(agg_def, dict):
                continue
            # terms 聚合
            if "terms" in agg_def and isinstance(agg_def["terms"], dict):
                field = agg_def["terms"].get("field")
                if field:
                    mapping[agg_name] = field
            # date_histogram 聚合
            if "date_histogram" in agg_def and isinstance(agg_def["date_histogram"], dict):
                field = agg_def["date_histogram"].get("field")
                if field:
                    mapping[agg_name] = field
            # 单值聚合 (sum/avg/min/max/cardinality 等)
            for agg_type in ("sum", "avg", "min", "max", "value_count", "cardinality"):
                if agg_type in agg_def and isinstance(agg_def[agg_type], dict):
                    field = agg_def[agg_type].get("field")
                    if field:
                        mapping[agg_name] = field
                    break
            # 递归子聚合
            for sub_key in ("aggs", "aggregations"):
                if sub_key in agg_def:
                    _walk_aggs(agg_def[sub_key])

    aggs = dsl.get("aggs") or dsl.get("aggregations")
    if aggs:
        _walk_aggs(aggs)
    return mapping


def resolve_metric_from_query(query_text: str) -> Optional[str]:
    """
    从用户查询文本中识别指标名（支持同义词）。
    返回指标标准英文名，找不到返回 None。

    注意：只做简单的关键词匹配，用于辅助判断。复杂的还是走 LLM。
    """
    query_lower = query_text.lower()
    for metric_name, info in METRICS.items():
        for syn in info["synonyms"]:
            if syn.lower() in query_lower:
                return metric_name
    for metric_name, info in DERIVED_METRICS.items():
        for syn in info["synonyms"]:
            if syn.lower() in query_lower:
                return metric_name
    return None
