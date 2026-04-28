from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime
from src.models.insight import Insight, InsightType, Severity, InsightSource
from src.tools.insight_config import insight_config
from src.tools.custom_report_client import es_client
from src.tools.hierarchy_utils import get_advertiser_status
import logging

logger = logging.getLogger(__name__)

# ============ ES查询辅助函数 ============

def _query_daily_metrics(ad_group_id: int = None, creative_id: int = None,
                         start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
    """查询按天聚合的基础指标（曝光、点击、消耗、转化、触达）"""
    must_conditions = []
    if ad_group_id:
        must_conditions.append({"term": {"ad_group_id": ad_group_id}})
    if creative_id:
        must_conditions.append({"term": {"creative_id": creative_id}})
    if start_date and end_date:
        must_conditions.append({"range": {"data_date": {"gte": start_date, "lte": end_date}}})

    query = {
        "size": 0,
        "query": {"bool": {"must": must_conditions}},
        "aggs": {
            "by_date": {
                "terms": {"field": "data_date", "size": 100},
                "aggs": {
                    "impressions": {"filter": {"term": {"data_type": 1}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                    "clicks": {"filter": {"term": {"data_type": 2}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                    "cost": {"filter": {"term": {"data_type": 3}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                    "conversions": {"filter": {"term": {"data_type": 4}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                    "reach": {"filter": {"term": {"data_type": 5}}, "aggs": {"value": {"sum": {"field": "data_value"}}}}
                }
            }
        }
    }

    response = es_client.search(index="ad_stat_data", body=query)
    daily_data = []
    for bucket in response["aggregations"]["by_date"]["buckets"]:
        daily_data.append({
            "date": bucket["key"],
            "impressions": bucket["impressions"]["value"]["value"],
            "clicks": bucket["clicks"]["value"]["value"],
            "cost": bucket["cost"]["value"]["value"],
            "conversions": bucket["conversions"]["value"]["value"],
            "reach": bucket["reach"]["value"]["value"]
        })

    # 按日期排序
    daily_data.sort(key=lambda x: x["date"])
    return daily_data

def _query_device_metrics(ad_group_id: int = None, creative_id: int = None,
                          start_date: str = None, end_date: str = None) -> Dict[str, Dict[str, Any]]:
    """查询按设备（操作系统）聚合的指标"""
    must_conditions = [{"term": {"audience_type": 3}}]  # 操作系统
    if ad_group_id:
        must_conditions.append({"term": {"ad_group_id": ad_group_id}})
    if creative_id:
        must_conditions.append({"term": {"creative_id": creative_id}})
    if start_date and end_date:
        must_conditions.append({"range": {"data_date": {"gte": start_date, "lte": end_date}}})

    query = {
        "size": 0,
        "query": {"bool": {"must": must_conditions}},
        "aggs": {
            "by_device": {
                "terms": {"field": "audience_tag_value", "size": 10},
                "aggs": {
                    "impressions": {"filter": {"term": {"data_type": 1}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                    "clicks": {"filter": {"term": {"data_type": 2}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                    "cost": {"filter": {"term": {"data_type": 3}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                    "conversions": {"filter": {"term": {"data_type": 4}}, "aggs": {"value": {"sum": {"field": "data_value"}}}}
                }
            }
        }
    }

    response = es_client.search(index="ad_stat_audience", body=query)
    device_map = {1: "iOS", 2: "Android", 3: "其他"}
    result = {}
    for bucket in response["aggregations"]["by_device"]["buckets"]:
        tag = int(bucket["key"])
        device_name = device_map.get(tag, f"设备{tag}")
        result[device_name] = {
            "impressions": bucket["impressions"]["value"]["value"],
            "clicks": bucket["clicks"]["value"]["value"],
            "cost": bucket["cost"]["value"]["value"],
            "conversions": bucket["conversions"]["value"]["value"]
        }
    return result

def _query_region_metrics(ad_group_id: int = None, creative_id: int = None,
                          start_date: str = None, end_date: str = None) -> Dict[str, Dict[str, Any]]:
    """查询按地域（城市）聚合的指标"""
    must_conditions = [{"term": {"audience_type": 7}}]  # 假设7是城市
    if ad_group_id:
        must_conditions.append({"term": {"ad_group_id": ad_group_id}})
    if creative_id:
        must_conditions.append({"term": {"creative_id": creative_id}})
    if start_date and end_date:
        must_conditions.append({"range": {"data_date": {"gte": start_date, "lte": end_date}}})

    query = {
        "size": 0,
        "query": {"bool": {"must": must_conditions}},
        "aggs": {
            "by_region": {
                "terms": {"field": "audience_tag_value", "size": 50},
                "aggs": {
                    "impressions": {"filter": {"term": {"data_type": 1}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                    "clicks": {"filter": {"term": {"data_type": 2}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                    "cost": {"filter": {"term": {"data_type": 3}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                    "conversions": {"filter": {"term": {"data_type": 4}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                    "reach": {"filter": {"term": {"data_type": 5}}, "aggs": {"value": {"sum": {"field": "data_value"}}}}
                }
            }
        }
    }

    try:
        response = es_client.search(index="ad_stat_audience", body=query)
        result = {}
        for bucket in response["aggregations"]["by_region"]["buckets"]:
            region_id = bucket["key"]
            result[f"城市{region_id}"] = {
                "impressions": bucket["impressions"]["value"]["value"],
                "clicks": bucket["clicks"]["value"]["value"],
                "cost": bucket["cost"]["value"]["value"],
                "conversions": bucket["conversions"]["value"]["value"],
                "reach": bucket["reach"]["value"]["value"]
            }
        return result
    except:
        return {}

def _get_ad_group_time_range(ad_group_id: int) -> Tuple[Optional[str], Optional[str]]:
    """从adgroup表获取投放时间范围"""
    try:
        query = {
            "query": {"term": {"ad_group_id": ad_group_id}},
            "size": 1
        }
        response = es_client.search(index="adgroup", body=query)
        if response["hits"]["total"]["value"] > 0:
            source = response["hits"]["hits"][0]["_source"]
            return source.get("start_time"), source.get("end_time")
    except:
        pass
    return None, None


@dataclass
class Rule:
    """规则数据类"""
    rule_id: str
    name: str
    type: InsightType
    severity: Severity
    check_fn: Callable[[Dict[str, Any], Dict[str, Any]], Optional[Insight]]


class RuleEngine:
    """规则引擎核心类
    使用配置文件中的固定阈值（基于ES全量数据百分位计算得出）
    """

    def __init__(self):
        self._rules: List[Rule] = []

    def register(self, rule: Rule) -> None:
        """注册规则"""
        self._rules.append(rule)
        logger.info(f"注册规则: {rule.rule_id} - {rule.name}")

    def analyze(self, query_result: Dict[str, Any], query_context: Dict[str, Any]) -> List[Insight]:
        """执行所有规则，返回洞察列表"""
        insights: List[Insight] = []

        for rule in self._rules:
            try:
                insight = rule.check_fn(query_result, query_context)
                if insight:
                    insights.append(insight)
                    logger.info(f"规则 {rule.rule_id} 触发洞察: {insight.name}")
            except Exception as e:
                logger.error(f"规则 {rule.rule_id} 执行失败: {str(e)}", exc_info=True)
                # 单个规则失败不影响整体执行
                continue

        return insights


# 全局规则引擎实例 - 在规则定义前创建
rule_engine = RuleEngine()


# ============ 辅助函数 ============

def _get_nested_value(row: Dict[str, Any], keys: List[str]) -> Optional[float]:
    """获取嵌套值，支持多个可能的键名"""
    for key in keys:
        if key in row:
            try:
                return float(row[key])
            except (ValueError, TypeError):
                continue
    return None


def _avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0


def _calc_metrics(row: Dict[str, Any]) -> Dict[str, float]:
    """从基础指标自动计算衍生指标"""
    impressions = float(_get_nested_value(row, ["impressions", "曝光", "曝光量"]) or 0)
    clicks = float(_get_nested_value(row, ["clicks", "点击", "点击量"]) or 0)
    cost = float(_get_nested_value(row, ["cost", "花费", "消费", "消耗"]) or 0)
    conversions = float(_get_nested_value(row, ["conversions", "转化", "转化量"]) or 0)

    ctr = _get_nested_value(row, ["ctr", "CTR", "点击率"]) or (clicks / impressions if impressions > 0 else 0)
    cvr = _get_nested_value(row, ["cvr", "CVR", "转化率"]) or (conversions / clicks if clicks > 0 else 0)
    cpc = _get_nested_value(row, ["cpc", "CPC", "点击成本"]) or (cost / clicks if clicks > 0 else 0)
    cpa = _get_nested_value(row, ["cpa", "CPA", "转化成本"]) or (cost / conversions if conversions > 0 else float("inf"))

    return {
        "impressions": impressions,
        "clicks": clicks,
        "cost": cost,
        "conversions": conversions,
        "ctr": float(ctr),
        "cvr": float(cvr),
        "cpc": float(cpc),
        "cpa": float(cpa),
    }


def _is_summary_row(name: str) -> bool:
    """判断是否是汇总行"""
    return name in ["总计", "合计", "汇总", "total", "Total", ""]


def _format_item_name(row: Dict[str, Any]) -> str:
    """格式化素材名称，包含ID"""
    name = row.get("name", row.get("creative_name"))
    item_id = row.get("id", row.get("creative_id", ""))

    # 如果没有name但有ID，使用"素材{ID}"作为名称
    if not name or name == "未知" or name == str(item_id):
        if item_id and str(item_id).strip() and str(item_id) != "0":
            name = f"素材{item_id}"
        else:
            name = "未知"

    if item_id and str(item_id).strip() and str(item_id) != "0":
        return f"{name}(ID:{item_id})"
    return name


# ==================== 亮点规则定义 (A01-A10) ====================

def a01_high_ctr(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A01: CTR表现优异"""
    if not insight_config.is_rule_enabled('A01_high_ctr'):
        return None

    # 从配置读取固定阈值和最小命中数
    lower_threshold = insight_config.get('highlight_rules.A01_high_ctr.threshold', 0.0230)
    upper_threshold = insight_config.get('highlight_rules.A01_high_ctr.upper_threshold', 0.0260)
    min_hits = insight_config.get('highlight_rules.A01_high_ctr.min_hits', 1)
    rule_name = insight_config.get('highlight_rules.A01_high_ctr.name', 'CTR表现优异')

    data = query_result.get("data", [])
    top_items = []
    for row in data:
        name = row.get("name", "")
        if _is_summary_row(name):
            continue
        metrics = _calc_metrics(row)
        if metrics["impressions"] >= 100 and lower_threshold <= metrics["ctr"] <= upper_threshold:
            display_name = _format_item_name(row)
            top_items.append({"name": display_name, "ctr": metrics["ctr"]})

    if len(top_items) < min_hits:
        return None

    top_items.sort(key=lambda x: x["ctr"], reverse=True)
    top3 = top_items[:3]
    names = "、".join([f"「{item['name']}」" for item in top3])
    max_ctr = max(item["ctr"] for item in top_items)

    return Insight(
        id="A01",
        type=InsightType.HIGHLIGHT,
        name=rule_name,
        severity=Severity.HIGH,
        confidence=0.95,
        source=InsightSource.RULE_ENGINE,
        metric="ctr",
        current_value=round(max_ctr * 100, 2),
        baseline_value=round(lower_threshold * 100, 2),
        evidence=f"发现 {len(top_items)} 个素材CTR表现优异（{lower_threshold*100:.2f}%~{upper_threshold*100:.2f}%）：{names}，最高CTR达{round(max_ctr * 100, 2)}%",
        suggestion="这些高CTR素材转化效率好，可考虑增加预算倾斜或复制优质创意特征",
        metadata={"lower_threshold": lower_threshold, "upper_threshold": upper_threshold, "top_count": len(top_items)}
    )


def a02_high_cvr(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A02: CVR表现优异"""
    if not insight_config.is_rule_enabled('A02_high_cvr'):
        return None

    threshold = insight_config.get('highlight_rules.A02_high_cvr.threshold', 0.0300)
    min_hits = insight_config.get('highlight_rules.A02_high_cvr.min_hits', 1)
    rule_name = insight_config.get('highlight_rules.A02_high_cvr.name', 'CVR表现优异')

    data = query_result.get("data", [])
    top_items = []
    for row in data:
        name = row.get("name", "")
        if _is_summary_row(name):
            continue
        metrics = _calc_metrics(row)
        if metrics["clicks"] >= 10 and metrics["cvr"] >= threshold:
            display_name = _format_item_name(row)
            top_items.append({"name": display_name, "cvr": metrics["cvr"]})

    if len(top_items) < min_hits:
        return None

    top_items.sort(key=lambda x: x["cvr"], reverse=True)
    top3 = top_items[:3]
    names = "、".join([f"「{item['name']}」" for item in top3])
    max_cvr = max(item["cvr"] for item in top_items)

    return Insight(
        id="A02",
        type=InsightType.HIGHLIGHT,
        name=rule_name,
        severity=Severity.HIGH,
        confidence=0.95,
        source=InsightSource.RULE_ENGINE,
        metric="cvr",
        current_value=round(max_cvr * 100, 2),
        baseline_value=round(threshold * 100, 2),
        evidence=f"发现 {len(top_items)} 个素材CVR表现优异（>= {threshold*100:.2f}%）：{names}，最高CVR达{round(max_cvr * 100, 2)}%",
        suggestion="这些高转化素材是优质潜力股，建议加大投放并分析落地页特征",
        metadata={"threshold": threshold, "top_count": len(top_items)}
    )


def a03_low_cpc(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A03: CPC成本优势显著"""
    if not insight_config.is_rule_enabled('A03_low_cpc'):
        return None

    threshold = insight_config.get('highlight_rules.A03_low_cpc.threshold', 0.0420)
    min_hits = insight_config.get('highlight_rules.A03_low_cpc.min_hits', 1)
    rule_name = insight_config.get('highlight_rules.A03_low_cpc.name', 'CPC成本优势显著')

    data = query_result.get("data", [])
    top_items = []
    for row in data:
        name = row.get("name", "")
        if _is_summary_row(name):
            continue
        metrics = _calc_metrics(row)
        if metrics["clicks"] >= 10 and 0 < metrics["cpc"] <= threshold:
            display_name = _format_item_name(row)
            top_items.append({"name": display_name, "cpc": metrics["cpc"]})

    if len(top_items) < min_hits:
        return None

    top_items.sort(key=lambda x: x["cpc"])
    top3 = top_items[:3]
    names = "、".join([f"「{item['name']}」" for item in top3])
    min_cpc = min(item["cpc"] for item in top_items)

    return Insight(
        id="A03",
        type=InsightType.HIGHLIGHT,
        name=rule_name,
        severity=Severity.HIGH,
        confidence=0.9,
        source=InsightSource.RULE_ENGINE,
        metric="cpc",
        current_value=round(min_cpc, 2),
        baseline_value=round(threshold, 2),
        evidence=f"发现 {len(top_items)} 个素材CPC成本优势明显（<= {threshold:.2f}元）：{names}，最低CPC仅{round(min_cpc, 2)}元",
        suggestion="这些低成本流量是投放红利，建议增加预算倾斜抢占流量",
        metadata={"threshold": threshold, "top_count": len(top_items)}
    )


def a04_healthy_spend_curve(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A04: 消耗曲线健康（分天消耗变化率均<50%）"""
    if not insight_config.is_rule_enabled('A04_healthy_spend'):
        return None

    ad_group_id = query_context.get("ad_group_id")
    creative_id = query_context.get("creative_id")

    daily_data = query_result.get("daily_data")
    if not daily_data:
        start_time, end_time = None, None
        if ad_group_id:
            start_time, end_time = _get_ad_group_time_range(ad_group_id)
        daily_data = _query_daily_metrics(ad_group_id, creative_id, start_time, end_time)

    if len(daily_data) < 3:
        return None

    all_healthy = True
    max_change_rate = 0
    for i in range(1, len(daily_data)):
        prev_cost = daily_data[i-1].get("cost", 0)
        curr_cost = daily_data[i].get("cost", 0)
        if prev_cost > 0:
            change_rate = abs(curr_cost - prev_cost) / prev_cost
            if change_rate > 0.5:
                all_healthy = False
                max_change_rate = max(max_change_rate, change_rate)

    if all_healthy:
        return Insight(
            id="A04",
            type=InsightType.HIGHLIGHT,
            name="消耗曲线健康",
            severity=Severity.MEDIUM,
            confidence=0.85,
            source=InsightSource.RULE_ENGINE,
            metric="spend_stability",
            current_value=len(daily_data),
            baseline_value=3,
            evidence=f"投放期间连续{len(daily_data)}天消耗波动均在50%以内，投放节奏平稳",
            suggestion="当前投放节奏良好，可保持现有策略",
            metadata={"days": len(daily_data), "max_change_rate": max_change_rate}
        )
    return None


def a05_good_frequency_control(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A05: 频次控制良好（日均频次<=2）"""
    if not insight_config.is_rule_enabled('A05_frequency_control'):
        return None

    ad_group_id = query_context.get("ad_group_id")
    creative_id = query_context.get("creative_id")

    daily_data = query_result.get("daily_data")
    if not daily_data:
        start_time, end_time = None, None
        if ad_group_id:
            start_time, end_time = _get_ad_group_time_range(ad_group_id)
        daily_data = _query_daily_metrics(ad_group_id, creative_id, start_time, end_time)

    if len(daily_data) < 3:  # 至少需要3天数据才判断
        return None

    daily_freqs = []
    for d in daily_data:
        imp = d.get("impressions", 0)
        reach = d.get("reach", 0)
        if reach > 0:
            daily_freqs.append(imp / reach)

    if not daily_freqs:
        return None

    avg_freq = sum(daily_freqs) / len(daily_freqs)

    if avg_freq <= 2.0:
        return Insight(
            id="A05",
            type=InsightType.HIGHLIGHT,
            name="曝光频次控制良好",
            severity=Severity.MEDIUM,
            confidence=0.8,
            source=InsightSource.RULE_ENGINE,
            metric="frequency",
            current_value=round(avg_freq, 2),
            baseline_value=2.0,
            evidence=f"日均曝光频次为{round(avg_freq, 2)}次，控制在健康水平",
            suggestion="频次控制合理，既保证有效触达又避免过度曝光",
            metadata={"avg_frequency": avg_freq, "days": len(daily_freqs)}
        )
    return None


def a06_ideal_conversion_timing(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A06: 转化节奏理想（首日转化占总转化>=80%）"""
    if not insight_config.is_rule_enabled('A06_conversion_timing'):
        return None

    ad_group_id = query_context.get("ad_group_id")
    creative_id = query_context.get("creative_id")

    daily_data = query_result.get("daily_data")
    if not daily_data:
        start_time, end_time = None, None
        if ad_group_id:
            start_time, end_time = _get_ad_group_time_range(ad_group_id)
        daily_data = _query_daily_metrics(ad_group_id, creative_id, start_time, end_time)

    if len(daily_data) < 3:  # 至少需要3天数据才判断
        return None

    total_conv = sum(d.get("conversions", 0) for d in daily_data)
    if total_conv <= 0:
        return None

    first_day_ratio = daily_data[0].get("conversions", 0) / total_conv

    if first_day_ratio >= 0.8:
        return Insight(
            id="A06",
            type=InsightType.HIGHLIGHT,
            name="转化节奏理想",
            severity=Severity.MEDIUM,
            confidence=0.85,
            source=InsightSource.RULE_ENGINE,
            metric="conversion_timing",
            current_value=round(first_day_ratio * 100, 1),
            baseline_value=80,
            evidence=f"首日转化占比达{round(first_day_ratio * 100, 1)}%，用户转化决策链路短",
            suggestion="用户决策意愿强，可加大首日投放力度",
            metadata={"first_day_ratio": first_day_ratio, "total_conversions": total_conv}
        )
    return None


def a07_high_cvr_contrast(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A07: CVR反差亮点"""
    if not insight_config.is_rule_enabled('A07_cvr_contrast'):
        return None

    threshold = insight_config.get('highlight_rules.A07_cvr_contrast.threshold', 0.0310)
    min_hits = insight_config.get('highlight_rules.A07_cvr_contrast.min_hits', 1)
    rule_name = insight_config.get('highlight_rules.A07_cvr_contrast.name', 'CVR反差亮点')

    data = query_result.get("data", [])
    top_items = []
    for row in data:
        name = row.get("name", "")
        if _is_summary_row(name):
            continue
        metrics = _calc_metrics(row)
        if metrics["clicks"] >= 10 and metrics["cvr"] >= threshold:
            display_name = _format_item_name(row)
            top_items.append({"name": display_name, "cvr": metrics["cvr"]})

    if len(top_items) < min_hits:
        return None

    top_items.sort(key=lambda x: x["cvr"], reverse=True)
    top3 = top_items[:3]
    names = "、".join([f"「{item['name']}」" for item in top3])
    max_cvr = max(item["cvr"] for item in top_items)

    return Insight(
        id="A07",
        type=InsightType.HIGHLIGHT,
        name=rule_name,
        severity=Severity.HIGH,
        confidence=0.9,
        source=InsightSource.RULE_ENGINE,
        metric="cvr",
        current_value=round(max_cvr * 100, 2),
        baseline_value=round(threshold * 100, 2),
        evidence=f"发现 {len(top_items)} 个素材表现特别突出（>= {threshold*100:.2f}%）：{names}，最高CVR达{round(max_cvr * 100, 2)}%",
        suggestion="这些是顶级优质素材，建议全面倾斜预算并分析其创意特征复制到其他素材",
        metadata={"threshold": threshold, "top_count": len(top_items)}
    )


def a08_device_cpa_contrast(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A08: 分设备CPA反差亮点（某设备CPA显著低于其他）"""
    if not insight_config.is_rule_enabled('A08_device_cpa_contrast'):
        return None

    threshold = insight_config.get('special_rules.A08_device_cpa_contrast.cpa_ratio_threshold', 0.5)
    rule_name = insight_config.get('special_rules.A08_device_cpa_contrast.name', '分设备CPA反差亮点')

    ad_group_id = query_context.get("ad_group_id")
    creative_id = query_context.get("creative_id")

    device_metrics = _query_device_metrics(ad_group_id, creative_id)
    if len(device_metrics) < 2:
        return None

    # 计算各设备CPA
    device_cpa = []
    for device, metrics in device_metrics.items():
        conv = metrics.get("conversions", 0)
        cost = metrics.get("cost", 0)
        if conv > 0:
            cpa = cost / conv
            device_cpa.append((cpa, device))

    if len(device_cpa) < 2:
        return None

    device_cpa.sort()
    lowest_cpa, best_device = device_cpa[0]
    second_cpa, _ = device_cpa[1]

    if lowest_cpa <= second_cpa * threshold:  # 最优设备CPA是次优的阈值以下
        return Insight(
            id="A08",
            type=InsightType.HIGHLIGHT,
            name=rule_name,
            severity=Severity.HIGH,
            confidence=0.9,
            source=InsightSource.RULE_ENGINE,
            metric="cpa",
            dimension_key="device",
            dimension_value=best_device,
            current_value=round(lowest_cpa, 2),
            baseline_value=round(second_cpa, 2),
            evidence=f"{best_device}设备CPA仅{round(lowest_cpa, 2)}元，是次优设备的{round(lowest_cpa / second_cpa * 100, 0)}%",
            suggestion=f"向{best_device}设备倾斜预算，可获得更高转化效率",
            metadata={"lowest_cpa": lowest_cpa, "second_cpa": second_cpa, "device": best_device, "threshold": threshold}
        )
    return None


def a09_ctr_low_cvr_high(query_result: Dict[str, Any], query_context: Dict[str, Any]) -> Optional[Insight]:
    """A09: 精准定向潜力股（低CTR但高CVR）"""
    if not insight_config.is_rule_enabled('A09_ctr_low_cvr_high'):
        return None

    threshold_ctr = insight_config.get('highlight_rules.A09_ctr_low_cvr_high.ctr_threshold', 0.0220)
    threshold_cvr = insight_config.get('highlight_rules.A09_ctr_low_cvr_high.cvr_threshold', 0.0300)
    min_hits = insight_config.get('highlight_rules.A09_ctr_low_cvr_high.min_hits', 1)
    rule_name = insight_config.get('highlight_rules.A09_ctr_low_cvr_high.name', '精准定向潜力股')

    data = query_result.get("data", [])
    top_items = []
    for row in data:
        name = row.get("name", "")
        if _is_summary_row(name):
            continue
        metrics = _calc_metrics(row)
        if (metrics["impressions"] >= 100 and metrics["clicks"] >= 10 and
                metrics["ctr"] <= threshold_ctr and metrics["cvr"] >= threshold_cvr):
            display_name = _format_item_name(row)
            top_items.append({"name": display_name, "ctr": metrics["ctr"], "cvr": metrics["cvr"]})

    if len(top_items) < min_hits:
        return None

    top3 = top_items[:3]
    names = "、".join([f"「{item['name']}」" for item in top3])
    max_cvr = max(item["cvr"] for item in top_items)

    return Insight(
        id="A09",
        type=InsightType.HIGHLIGHT,
        name=rule_name,
        severity=Severity.HIGH,
        confidence=0.85,
        source=InsightSource.RULE_ENGINE,
        metric="mixed",
        current_value=round(max_cvr * 100, 2),
        evidence=f"发现 {len(top_items)} 个精准定向素材：{names}，虽然CTR较低（<= {threshold_ctr*100:.2f}%）但CVR表现优异（>= {threshold_cvr*100:.2f}%），属于高意向精准流量",
        suggestion="这类素材转化质量极高，建议优化创意封面提升点击率，或放宽定向扩大覆盖人群",
        metadata={"threshold_ctr": threshold_ctr, "threshold_cvr": threshold_cvr, "top_count": len(top_items)}
    )


# ============ 问题识别规则 ============

def check_p01_low_cvr(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P01: CVR转化低下"""
    if not insight_config.is_rule_enabled('P01_low_cvr'):
        return None

    threshold = insight_config.get('problem_rules.P01_low_cvr.threshold', 0.0285)
    min_hits = insight_config.get('problem_rules.P01_low_cvr.min_hits', 1)
    rule_name = insight_config.get('problem_rules.P01_low_cvr.name', 'CVR转化低下')

    data = query_result.get("data", [])
    problem_rows = []
    for row in data:
        name = row.get("name", "")
        if _is_summary_row(name):
            continue
        metrics = _calc_metrics(row)
        if metrics["clicks"] >= 10 and metrics["cvr"] > 0 and metrics["cvr"] <= threshold:
            display_name = _format_item_name(row)
            problem_rows.append({"name": display_name, "ctr": metrics["ctr"], "cvr": metrics["cvr"]})

    if len(problem_rows) < min_hits:
        return None

    problem_rows.sort(key=lambda x: x["cvr"])
    top3 = problem_rows[:3]
    names = "、".join([f"「{r['name']}」" for r in top3])
    min_cvr = min(r["cvr"] for r in problem_rows)

    return Insight(
        id="P01",
        type=InsightType.PROBLEM,
        name=rule_name,
        severity=Severity.HIGH,
        confidence=0.9,
        source=InsightSource.RULE_ENGINE,
        metric="cvr",
        current_value=round(min_cvr * 100, 2),
        baseline_value=round(threshold * 100, 2),
        dimension_value=names,
        evidence=f"发现 {len(problem_rows)} 个素材CVR表现较差（<= {threshold*100:.2f}%）：{names}，最低CVR仅{round(min_cvr * 100, 2)}%",
        suggestion=f"建议重点检查 {names} 的定向人群是否精准，落地页与创意是否匹配，或考虑暂停低效素材",
        metadata={"threshold": threshold, "problem_count": len(problem_rows)}
    )


def check_p02_creative_fatigue(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P02: 创意疲劳衰减 - 连续多日CTR下降"""
    if not insight_config.is_rule_enabled('P02_creative_fatigue'):
        return None

    decline_days = int(insight_config.get('timing_rules.P02_creative_fatigue.decline_days', 3))
    decline_threshold = insight_config.get('timing_rules.P02_creative_fatigue.decline_threshold', 0.2)
    rule_name = insight_config.get('timing_rules.P02_creative_fatigue.name', '创意疲劳衰减')

    data = query_result.get("data", [])
    if len(data) < decline_days:
        return None

    # 提取每天的CTR（自动计算）和日期名称
    daily_data = []
    for row in data:
        metrics = _calc_metrics(row)
        name = row.get("name", row.get("date", row.get("日期", "")))
        if metrics["impressions"] > 0:  # 有曝光才算有效天
            daily_data.append({"name": name, "ctr": metrics["ctr"]})

    if len(daily_data) >= decline_days:
        # 检查连续下降趋势
        last_n = daily_data[-decline_days:]
        declining = all(last_n[i]["ctr"] > last_n[i+1]["ctr"] for i in range(decline_days - 1))
        total_drop = (last_n[0]["ctr"] - last_n[-1]["ctr"]) / last_n[0]["ctr"] if last_n[0]["ctr"] > 0 else 0

        if declining and total_drop > decline_threshold:
            dates = f"{last_n[0]['name']} 至 {last_n[-1]['name']}" if last_n[0]['name'] else f"最近{decline_days}天"
            return Insight(
                id="P02",
                type=InsightType.PROBLEM,
                name=rule_name,
                severity=Severity.MEDIUM,
                confidence=0.85,
                source=InsightSource.RULE_ENGINE,
                metric="CTR",
                dimension_value=dates,
                current_value=last_n[-1]["ctr"],
                baseline_value=last_n[0]["ctr"],
                evidence=f"CTR 连续下降：{dates}，从 {last_n[0]['ctr']*100:.2f}% 降至 {last_n[-1]['ctr']*100:.2f}%，降幅 {total_drop*100:.1f}%",
                suggestion=f"建议准备新的创意素材进行轮换，{dates}期间CTR持续下滑，目标受众可能对当前素材产生审美疲劳",
                metadata={"decline_days": decline_days, "decline_threshold": decline_threshold}
            )
    return None


def check_p03_high_cpa(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P03: CPA转化成本过高"""
    if not insight_config.is_rule_enabled('P03_high_cpa'):
        return None

    threshold = insight_config.get('problem_rules.P03_high_cpa.threshold', 1.70)
    min_hits = insight_config.get('problem_rules.P03_high_cpa.min_hits', 1)
    rule_name = insight_config.get('problem_rules.P03_high_cpa.name', 'CPA转化成本过高')

    data = query_result.get("data", [])
    problem_rows = []
    for row in data:
        name = row.get("name", "")
        if _is_summary_row(name):
            continue
        metrics = _calc_metrics(row)
        if metrics["conversions"] >= 1 and metrics["cpa"] != float("inf") and metrics["cpa"] >= threshold:
            display_name = _format_item_name(row)
            problem_rows.append({"name": display_name, "cpa": metrics["cpa"]})

    if len(problem_rows) < min_hits:
        return None

    problem_rows.sort(key=lambda x: x["cpa"], reverse=True)
    top3 = problem_rows[:3]
    names = "、".join([f"「{r['name']}」" for r in top3])
    max_cpa = max(r["cpa"] for r in problem_rows)

    return Insight(
        id="P03",
        type=InsightType.PROBLEM,
        name=rule_name,
        severity=Severity.HIGH,
        confidence=0.85,
        source=InsightSource.RULE_ENGINE,
        metric="cpa",
        current_value=round(max_cpa, 2),
        baseline_value=round(threshold, 2),
        dimension_value=names,
        evidence=f"发现 {len(problem_rows)} 个素材CPA转化成本偏高（>= {threshold:.2f}元）：{names}，最高CPA达{round(max_cpa, 2)}元",
        suggestion=f"建议重点优化 {names}，可降低出价、优化落地页转化路径，或考虑暂停投放",
        metadata={"threshold": threshold, "problem_count": len(problem_rows)}
    )


def check_p04_frequency_control(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P04: 频次失控（日均频次>=3）"""
    ad_group_id = context.get("ad_group_id")
    creative_id = context.get("creative_id")

    daily_data = query_result.get("daily_data")
    if not daily_data:
        start_time, end_time = None, None
        if ad_group_id:
            start_time, end_time = _get_ad_group_time_range(ad_group_id)
        daily_data = _query_daily_metrics(ad_group_id, creative_id, start_time, end_time)

    if len(daily_data) < 3:  # 至少需要3天数据才判断
        return None

    daily_freqs = []
    for d in daily_data:
        imp = d.get("impressions", 0)
        reach = d.get("reach", 0)
        if reach > 0:
            daily_freqs.append(imp / reach)

    if not daily_freqs:
        return None

    avg_freq = sum(daily_freqs) / len(daily_freqs)
    threshold = insight_config.get('timing_rules.P04_frequency_control.threshold', 5.0)

    if avg_freq >= threshold:
        return Insight(
            id="P04",
            type=InsightType.PROBLEM,
            name="频次失控",
            severity=Severity.HIGH,
            confidence=0.9,
            source=InsightSource.RULE_ENGINE,
            metric="frequency",
            current_value=round(avg_freq, 2),
            baseline_value=round(threshold, 2),
            evidence=f"日均曝光频次达{round(avg_freq, 2)}次，超过健康阈值{threshold}次",
            suggestion="建议设置频次上限（每人每周不超过10次），避免对同一用户过度曝光造成骚扰和浪费",
            metadata={"avg_frequency": avg_freq, "days": len(daily_freqs)}
        )
    return None


def check_p05_fraud_suspicion(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P05: CTR异常波动检测"""
    if not insight_config.is_rule_enabled('P05_ctr_anomaly'):
        return None

    threshold_low = insight_config.get('problem_rules.P05_ctr_anomaly.low_threshold', 0.0210)
    threshold_high = insight_config.get('problem_rules.P05_ctr_anomaly.high_threshold', 0.0250)
    min_hits = insight_config.get('problem_rules.P05_ctr_anomaly.min_hits', 1)
    rule_name = insight_config.get('problem_rules.P05_ctr_anomaly.name', 'CTR异常波动')

    data = query_result.get("data", [])
    extreme_rows = []
    for row in data:
        name = row.get("name", "")
        if _is_summary_row(name):
            continue
        metrics = _calc_metrics(row)
        if metrics["impressions"] >= 100 and metrics["ctr"] > 0:
            if metrics["ctr"] <= threshold_low or metrics["ctr"] >= threshold_high:
                display_name = _format_item_name(row)
                type_flag = "low" if metrics["ctr"] <= threshold_low else "high"
                extreme_rows.append({"name": display_name, "ctr": metrics["ctr"], "type": type_flag})

    if len(extreme_rows) < min_hits:
        return None

    low_count = sum(1 for r in extreme_rows if r["type"] == "low")
    high_count = len(extreme_rows) - low_count

    top3 = extreme_rows[:3]
    names = "、".join([f"「{r['name']}」" for r in top3])

    return Insight(
        id="P05",
        type=InsightType.PROBLEM,
        name=rule_name,
        severity=Severity.MEDIUM,
        confidence=0.85,
        source=InsightSource.RULE_ENGINE,
        metric="ctr",
        dimension_value=names,
        evidence=f"发现 {len(extreme_rows)} 个素材CTR表现异常（<{threshold_low*100:.2f}% 或 >{threshold_high*100:.2f}%）：{names}，低CTR {low_count} 个，高CTR {high_count} 个",
        suggestion="建议检查这些异常素材的投放人群、竞争环境，排除流量异常或定向偏差",
        metadata={"threshold_low": threshold_low, "threshold_high": threshold_high, "extreme_count": len(extreme_rows)}
    )


def check_p06_bidding_issue(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P06: 出价策略异常（单日CPC增长>100%）"""
    ad_group_id = context.get("ad_group_id")
    creative_id = context.get("creative_id")

    daily_data = query_result.get("daily_data")
    if not daily_data:
        start_time, end_time = None, None
        if ad_group_id:
            start_time, end_time = _get_ad_group_time_range(ad_group_id)
        daily_data = _query_daily_metrics(ad_group_id, creative_id, start_time, end_time)

    if len(daily_data) < 3:  # 至少需要3天数据才判断
        return None

    threshold = insight_config.get('timing_rules.P06_bidding_issue.cpc_change_threshold', 5.0)

    # 计算相邻天CPC变化率
    for i in range(1, len(daily_data)):
        prev_clicks = daily_data[i-1].get("clicks", 0)
        curr_clicks = daily_data[i].get("clicks", 0)
        prev_cost = daily_data[i-1].get("cost", 0)
        curr_cost = daily_data[i].get("cost", 0)

        if prev_clicks > 0 and curr_clicks > 0:
            prev_cpc = prev_cost / prev_clicks
            curr_cpc = curr_cost / curr_clicks
            if prev_cpc > 0:
                change_rate = (curr_cpc - prev_cpc) / prev_cpc
                if change_rate > threshold:
                    return Insight(
                        id="P06",
                        type=InsightType.PROBLEM,
                        name="出价策略异常",
                        severity=Severity.MEDIUM,
                        confidence=0.8,
                        source=InsightSource.RULE_ENGINE,
                        metric="CPC",
                        current_value=round(change_rate * 100, 1),
                        baseline_value=100,
                        evidence=f"CPC 单日涨幅达 {change_rate*100:.1f}%，波动异常",
                        suggestion="建议检查是否有竞品大幅抬价，或调整出价策略目标，设置最高出价限价避免成本失控"
                    )
    return None


def check_p07_saturation(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P07: 地域投放过于集中"""
    if not insight_config.is_rule_enabled('P07_saturation'):
        return None

    reach_threshold = insight_config.get('timing_rules.P07_saturation.reach_threshold', 0.8)
    cpa_ratio_threshold = insight_config.get('timing_rules.P07_saturation.cpa_ratio_threshold', 1.5)
    rule_name = insight_config.get('timing_rules.P07_saturation.name', '地域投放过于集中')

    ad_group_id = context.get("ad_group_id")
    creative_id = context.get("creative_id")

    region_data = _query_region_metrics(ad_group_id, creative_id)
    if len(region_data) < 2:
        return None

    total_reach = sum(r.get("reach", 0) for r in region_data.values())
    if total_reach <= 0:
        return None

    # 计算各城市reach占比
    regions_with_reach = []
    for region, metrics in region_data.items():
        reach = metrics.get("reach", 0)
        if reach > 0:
            regions_with_reach.append({"region": region, "reach_ratio": reach / total_reach, "metrics": metrics})

    if not regions_with_reach:
        return None

    regions_with_reach.sort(key=lambda x: x["reach_ratio"], reverse=True)
    top_region = regions_with_reach[0]

    if top_region["reach_ratio"] > reach_threshold:  # 单一城市占比超过阈值
        # 计算各城市CPA
        all_cpa = []
        for r in regions_with_reach:
            conv = r["metrics"].get("conversions", 0)
            cost = r["metrics"].get("cost", 0)
            if conv > 0:
                all_cpa.append({"region": r["region"], "cpa": cost / conv})

        if len(all_cpa) >= 2:
            all_cpa.sort(key=lambda x: x["cpa"])
            top_cpa = next((c["cpa"] for c in all_cpa if c["region"] == top_region["region"]), None)
            other_cpas = [c["cpa"] for c in all_cpa if c["region"] != top_region["region"]]

            if top_cpa and other_cpas:
                avg_other_cpa = sum(other_cpas) / len(other_cpas)
                if top_cpa >= avg_other_cpa * cpa_ratio_threshold:
                    return Insight(
                        id="P07",
                        type=InsightType.PROBLEM,
                        name=rule_name,
                        severity=Severity.MEDIUM,
                        confidence=0.85,
                        source=InsightSource.RULE_ENGINE,
                        metric="reach/CPA",
                        dimension_value=top_region["region"],
                        current_value=round(top_region["reach_ratio"] * 100, 1),
                        baseline_value=round(reach_threshold * 100, 1),
                        evidence=f"{top_region['region']} 触达占比达 {top_region['reach_ratio']*100:.1f}%，且CPA {top_cpa:.2f}元是其他地区均值的 {top_cpa/avg_other_cpa:.1f}倍",
                        suggestion=f"地域投放过于集中且成本偏高，建议拓展周边城市或优化投放人群",
                        metadata={"reach_threshold": reach_threshold, "cpa_ratio_threshold": cpa_ratio_threshold}
                    )
    return None


def check_p08_device_compatibility(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P08: 设备兼容问题（设备间CTR差异>5倍）"""
    ad_group_id = context.get("ad_group_id")
    creative_id = context.get("creative_id")

    device_metrics = _query_device_metrics(ad_group_id, creative_id)
    if len(device_metrics) < 2:
        return None

    threshold = insight_config.get('timing_rules.P08_device_compatibility.ctr_ratio_threshold', 5.0)

    # 计算各设备CTR
    device_ctr = []
    for device, metrics in device_metrics.items():
        imp = metrics.get("impressions", 0)
        clicks = metrics.get("clicks", 0)
        if imp > 0:
            ctr = clicks / imp
            device_ctr.append((ctr, device))

    if len(device_ctr) < 2:
        return None

    device_ctr.sort(reverse=True)
    best_ctr, best_device = device_ctr[0]
    worst_ctr, worst_device = device_ctr[-1]

    if best_ctr > 0 and worst_ctr <= best_ctr / threshold:  # 最差CTR是最好的1/threshold以下
        return Insight(
            id="P08",
            type=InsightType.PROBLEM,
            name="设备兼容问题",
            severity=Severity.MEDIUM,
            confidence=0.8,
            source=InsightSource.RULE_ENGINE,
            metric="CTR",
            dimension_value=worst_device,
            current_value=round(worst_ctr * 100, 2),
            baseline_value=round(best_ctr * 100, 2),
            evidence=f"{worst_device} 端CTR仅 {worst_ctr*100:.2f}%，是 {best_device} 端的 {worst_ctr/best_ctr*100:.1f}%",
            suggestion=f"建议检查 {worst_device} 端的广告素材兼容性、落地页加载速度，可能存在技术问题导致用户体验差"
        )
    return None


def check_p09_competitor_impact(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P09: 竞品活动冲击（CPC涨50%且CTR跌30%）"""
    ad_group_id = context.get("ad_group_id")
    creative_id = context.get("creative_id")

    daily_data = query_result.get("daily_data")
    if not daily_data:
        start_time, end_time = None, None
        if ad_group_id:
            start_time, end_time = _get_ad_group_time_range(ad_group_id)
        daily_data = _query_daily_metrics(ad_group_id, creative_id, start_time, end_time)

    if len(daily_data) < 3:  # 至少需要3天数据才判断
        return None

    # 计算相邻天CPC和CTR变化率
    for i in range(1, len(daily_data)):
        prev_clicks = daily_data[i-1].get("clicks", 0)
        curr_clicks = daily_data[i].get("clicks", 0)
        prev_cost = daily_data[i-1].get("cost", 0)
        curr_cost = daily_data[i].get("cost", 0)
        prev_imp = daily_data[i-1].get("impressions", 0)
        curr_imp = daily_data[i].get("impressions", 0)

        if prev_clicks > 0 and curr_clicks > 0 and prev_imp > 0 and curr_imp > 0:
            prev_cpc = prev_cost / prev_clicks
            curr_cpc = curr_cost / curr_clicks
            prev_ctr = prev_clicks / prev_imp
            curr_ctr = curr_clicks / curr_imp

            if prev_cpc > 0 and prev_ctr > 0:
                cpc_change = (curr_cpc - prev_cpc) / prev_cpc
                ctr_change = (curr_ctr - prev_ctr) / prev_ctr

                cpc_threshold = insight_config.get('timing_rules.P09_competitor_impact.cpc_rise_threshold', 1.0)
                ctr_threshold = insight_config.get('timing_rules.P09_competitor_impact.ctr_drop_threshold', 0.5)

                if cpc_change > cpc_threshold and ctr_change < -ctr_threshold:  # CPC涨且CTR跌
                    return Insight(
                        id="P09",
                        type=InsightType.PROBLEM,
                        name="竞品活动冲击",
                        severity=Severity.MEDIUM,
                        confidence=0.75,
                        source=InsightSource.RULE_ENGINE,
                        metric="CPC/CTR",
                        evidence=f"CPC单日上涨{cpc_change*100:.1f}%，同时CTR下降{abs(ctr_change)*100:.1f}%，典型的竞品大促竞价冲击特征",
                        suggestion="建议关注竞品动态，可能对方在进行促销活动并加大了投放。可考虑临时提升出价保持竞争力，或避开竞品高峰时段"
                    )
    return None


def check_p10_spend_volatility(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P10: 消耗波动异常（单日变化>200%）"""
    ad_group_id = context.get("ad_group_id")
    creative_id = context.get("creative_id")

    daily_data = query_result.get("daily_data")
    if not daily_data:
        start_time, end_time = None, None
        if ad_group_id:
            start_time, end_time = _get_ad_group_time_range(ad_group_id)
        daily_data = _query_daily_metrics(ad_group_id, creative_id, start_time, end_time)

    if len(daily_data) < 3:  # 至少需要3天数据才判断
        return None

    threshold = insight_config.get('timing_rules.P10_spend_volatility.change_threshold', 5.0)

    for i in range(1, len(daily_data)):
        prev_cost = daily_data[i-1].get("cost", 0)
        curr_cost = daily_data[i].get("cost", 0)
        if prev_cost > 0:
            change_rate = abs(curr_cost - prev_cost) / prev_cost
            if change_rate > threshold:
                return Insight(
                    id="P10",
                    type=InsightType.PROBLEM,
                    name="消耗波动异常",
                    severity=Severity.MEDIUM,
                    confidence=0.8,
                    source=InsightSource.RULE_ENGINE,
                    metric="spend_volatility",
                    current_value=round(change_rate * 100, 1),
                    baseline_value=round(threshold * 100, 1),
                    evidence=f"单日消耗波动达{change_rate*100:.1f}%，超过阈值{threshold*100:.0f}%，投放不稳定",
                    suggestion="建议检查预算设置是否合理，是否有流量突增或突降的异常情况"
                )
    return None


def check_p11_advertiser_punished(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P11: 广告主合规惩罚检测"""
    if not insight_config.is_rule_enabled('P11_advertiser_punished'):
        return None

    advertiser_ids = context.get("advertiser_ids", [])
    if not advertiser_ids:
        return None

    status_map = get_advertiser_status(advertiser_ids)
    punished_advertisers = [
        (adv_id, info)
        for adv_id, info in status_map.items()
        if info["is_punished"]
    ]

    if not punished_advertisers:
        return None

    adv_names = ", ".join([info["advertiser_name"] for _, info in punished_advertisers])

    return Insight(
        id="P11",
        type=InsightType.PROBLEM,
        name="广告主合规惩罚",
        severity=Severity.CRITICAL,
        confidence=1.0,
        source=InsightSource.RULE_ENGINE,
        metric="compliance_status",
        evidence=f"发现 {len(punished_advertisers)} 个广告主处于合规惩罚状态：{adv_names}，投放可能受限",
        suggestion="建议立即检查广告主账号的合规状态，处理违规内容并提交申诉，恢复正常投放",
        metadata={"punished_advertisers": punished_advertisers}
    )


def check_p12_advertiser_arrears(query_result: Dict[str, Any], context: Dict[str, Any]) -> Optional[Insight]:
    """P12: 广告主欠费检测"""
    if not insight_config.is_rule_enabled('P12_advertiser_arrears'):
        return None

    advertiser_ids = context.get("advertiser_ids", [])
    if not advertiser_ids:
        return None

    status_map = get_advertiser_status(advertiser_ids)
    arrears_advertisers = [
        (adv_id, info)
        for adv_id, info in status_map.items()
        if info["is_arrears"]
    ]

    if not arrears_advertisers:
        return None

    adv_names = ", ".join([info["advertiser_name"] for _, info in arrears_advertisers])

    return Insight(
        id="P12",
        type=InsightType.PROBLEM,
        name="广告主账号欠费",
        severity=Severity.CRITICAL,
        confidence=1.0,
        source=InsightSource.RULE_ENGINE,
        metric="account_balance",
        evidence=f"发现 {len(arrears_advertisers)} 个广告主处于欠费状态：{adv_names}，可能随时停投",
        suggestion="建议立即充值缴费，避免因欠费导致投放中断影响业务收入",
        metadata={"arrears_advertisers": arrears_advertisers}
    )


# ==================== 规则注册 ====================

# 亮点规则 A01-A09
rule_engine.register(Rule("A01", "CTR表现优异", InsightType.HIGHLIGHT, Severity.HIGH, a01_high_ctr))
rule_engine.register(Rule("A02", "CVR表现优异", InsightType.HIGHLIGHT, Severity.HIGH, a02_high_cvr))
rule_engine.register(Rule("A03", "CPC成本优势", InsightType.HIGHLIGHT, Severity.HIGH, a03_low_cpc))
rule_engine.register(Rule("A04", "消耗曲线健康", InsightType.HIGHLIGHT, Severity.MEDIUM, a04_healthy_spend_curve))
rule_engine.register(Rule("A05", "频次控制良好", InsightType.HIGHLIGHT, Severity.MEDIUM, a05_good_frequency_control))
rule_engine.register(Rule("A06", "转化节奏理想", InsightType.HIGHLIGHT, Severity.MEDIUM, a06_ideal_conversion_timing))
rule_engine.register(Rule("A07", "CVR反差亮点", InsightType.HIGHLIGHT, Severity.HIGH, a07_high_cvr_contrast))
rule_engine.register(Rule("A08", "分设备CPA反差亮点", InsightType.HIGHLIGHT, Severity.HIGH, a08_device_cpa_contrast))
rule_engine.register(Rule("A09", "精准定向潜力股", InsightType.HIGHLIGHT, Severity.HIGH, a09_ctr_low_cvr_high))

# 问题规则 P01-P12
rule_engine.register(Rule("P01", "CVR转化低下", InsightType.PROBLEM, Severity.HIGH, check_p01_low_cvr))
rule_engine.register(Rule("P02", "创意疲劳衰减", InsightType.PROBLEM, Severity.MEDIUM, check_p02_creative_fatigue))
rule_engine.register(Rule("P03", "CPA转化成本过高", InsightType.PROBLEM, Severity.HIGH, check_p03_high_cpa))
rule_engine.register(Rule("P04", "频次失控", InsightType.PROBLEM, Severity.HIGH, check_p04_frequency_control))
rule_engine.register(Rule("P05", "CTR异常波动", InsightType.PROBLEM, Severity.MEDIUM, check_p05_fraud_suspicion))
rule_engine.register(Rule("P06", "出价策略异常", InsightType.PROBLEM, Severity.MEDIUM, check_p06_bidding_issue))
rule_engine.register(Rule("P07", "地域投放过于集中", InsightType.PROBLEM, Severity.MEDIUM, check_p07_saturation))
rule_engine.register(Rule("P08", "设备兼容问题", InsightType.PROBLEM, Severity.MEDIUM, check_p08_device_compatibility))
rule_engine.register(Rule("P09", "竞品活动冲击", InsightType.PROBLEM, Severity.MEDIUM, check_p09_competitor_impact))
rule_engine.register(Rule("P10", "消耗波动异常", InsightType.PROBLEM, Severity.MEDIUM, check_p10_spend_volatility))
rule_engine.register(Rule("P11", "广告主合规惩罚", InsightType.PROBLEM, Severity.CRITICAL, check_p11_advertiser_punished))
rule_engine.register(Rule("P12", "广告主账号欠费", InsightType.PROBLEM, Severity.CRITICAL, check_p12_advertiser_arrears))
