"""
多层级广告ID关联工具
支持: 广告主 → 广告组 → 创意/活动 的层级关联查询
"""
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
from .custom_report_client import es_client
import logging

logger = logging.getLogger(__name__)

# 状态码定义
ADVERTISER_STATUS_NORMAL = 1
ADVERTISER_STATUS_PUNISHED = 2  # 惩罚/合规问题
ADVERTISER_STATUS_ARREARS = 3   # 欠费/停机


def get_date_range_from_query(time_range: Dict) -> Tuple[str, str]:
    """从查询时间范围解析开始和结束日期"""
    start_date = time_range.get("start_date", "")
    end_date = time_range.get("end_date", "")

    # 如果没有，默认最近30天
    if not start_date or not end_date:
        end = datetime.now()
        start = end - timedelta(days=30)
        start_date = start.strftime("%Y-%m-%d")
        end_date = end.strftime("%Y-%m-%d")

    return start_date, end_date


def get_ad_groups_for_advertiser(
    advertiser_ids: List[int],
    start_date: str,
    end_date: str
) -> Set[int]:
    """查询指定广告主在指定时间范围内有投放的广告组ID"""
    if not advertiser_ids:
        return set()

    query = {
        "query": {
            "bool": {
                "must": [
                    {"terms": {"advertiser_id": advertiser_ids}},
                    {"range": {"data_date": {"gte": start_date, "lte": end_date}}}
                ]
            }
        },
        "size": 0,
        "aggs": {
            "by_adgroup": {"terms": {"field": "ad_group_id", "size": 10000}}
        }
    }

    try:
        response = es_client.search(index="ad_stat_data", **query)
        ad_group_ids = {
            bucket["key"]
            for bucket in response["aggregations"]["by_adgroup"]["buckets"]
        }
        logger.info(f"广告主 {advertiser_ids} 在 {start_date}~{end_date} 找到 {len(ad_group_ids)} 个广告组")
        return ad_group_ids
    except Exception as e:
        logger.error(f"查询广告组ID失败: {e}")
        return set()


def get_campaigns_for_ad_groups(
    ad_group_ids: Set[int],
    start_date: str,
    end_date: str
) -> Set[int]:
    """根据广告组ID查询对应的活动ID"""
    if not ad_group_ids:
        return set()

    query = {
        "query": {
            "bool": {
                "must": [
                    {"terms": {"ad_group_id": list(ad_group_ids)}},
                    {"range": {"data_date": {"gte": start_date, "lte": end_date}}}
                ]
            }
        },
        "size": 0,
        "aggs": {
            "by_campaign": {"terms": {"field": "campaign_id", "size": 10000}}
        }
    }

    try:
        response = es_client.search(index="ad_stat_data", **query)
        campaign_ids = {
            bucket["key"]
            for bucket in response["aggregations"]["by_campaign"]["buckets"]
        }
        logger.info(f"{len(ad_group_ids)} 个广告组对应 {len(campaign_ids)} 个活动")
        return campaign_ids
    except Exception as e:
        logger.error(f"查询活动ID失败: {e}")
        return set()


def get_creatives_for_ad_groups(
    ad_group_ids: Set[int],
    start_date: str,
    end_date: str
) -> Set[int]:
    """根据广告组ID查询对应的创意ID"""
    if not ad_group_ids:
        return set()

    query = {
        "query": {
            "bool": {
                "must": [
                    {"terms": {"ad_group_id": list(ad_group_ids)}},
                    {"range": {"data_date": {"gte": start_date, "lte": end_date}}}
                ]
            }
        },
        "size": 0,
        "aggs": {
            "by_creative": {"terms": {"field": "creative_id", "size": 10000}}
        }
    }

    try:
        response = es_client.search(index="ad_stat_data", **query)
        creative_ids = {
            bucket["key"]
            for bucket in response["aggregations"]["by_creative"]["buckets"]
        }
        logger.info(f"{len(ad_group_ids)} 个广告组对应 {len(creative_ids)} 个创意")
        return creative_ids
    except Exception as e:
        logger.error(f"查询创意ID失败: {e}")
        return set()


def get_advertiser_hierarchy(
    advertiser_ids: List[int],
    time_range: Dict
) -> Dict[str, Set[int]]:
    """
    获取广告主完整的层级ID关系

    Args:
        advertiser_ids: 广告主ID列表
        time_range: 时间范围 {"start_date": "...", "end_date": "..."}

    Returns:
        {
            "advertiser_ids": {1, 2, 3},
            "ad_group_ids": {101, 102, ...},
            "campaign_ids": {1001, 1002, ...},
            "creative_ids": {5001, 5002, ...}
        }
    """
    start_date, end_date = get_date_range_from_query(time_range)

    ad_group_ids = get_ad_groups_for_advertiser(advertiser_ids, start_date, end_date)
    campaign_ids = get_campaigns_for_ad_groups(ad_group_ids, start_date, end_date)
    creative_ids = get_creatives_for_ad_groups(ad_group_ids, start_date, end_date)

    return {
        "advertiser_ids": set(advertiser_ids),
        "ad_group_ids": ad_group_ids,
        "campaign_ids": campaign_ids,
        "creative_ids": creative_ids
    }


def get_advertiser_status(advertiser_ids: List[int]) -> Dict[int, Dict]:
    """
    批量查询广告主状态信息

    Returns:
        {
            advertiser_id: {
                "status": int,
                "status_text": str,  # 正常/惩罚/欠费
                "advertiser_name": str
            }
        }
    """
    if not advertiser_ids:
        return {}

    query = {
        "query": {"terms": {"advertiser_id": advertiser_ids}},
        "size": len(advertiser_ids)
    }

    try:
        response = es_client.search(index="advertiser", **query)
        result = {}

        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            adv_id = source["advertiser_id"]
            status = source.get("status", ADVERTISER_STATUS_NORMAL)

            if status == ADVERTISER_STATUS_NORMAL:
                status_text = "正常"
            elif status == ADVERTISER_STATUS_PUNISHED:
                status_text = "惩罚/合规限制"
            elif status == ADVERTISER_STATUS_ARREARS:
                status_text = "欠费/停机"
            else:
                status_text = f"未知状态({status})"

            result[adv_id] = {
                "status": status,
                "status_text": status_text,
                "advertiser_name": source.get("advertiser_name", ""),
                "is_normal": status == ADVERTISER_STATUS_NORMAL,
                "is_punished": status == ADVERTISER_STATUS_PUNISHED,
                "is_arrears": status == ADVERTISER_STATUS_ARREARS
            }

        logger.info(f"查询到 {len(result)} 个广告主的状态信息")
        return result

    except Exception as e:
        logger.error(f"查询广告主状态失败: {e}")
        return {}


def get_ad_group_level_metrics(
    ad_group_ids: Set[int],
    start_date: str,
    end_date: str
) -> List[Dict]:
    """
    按广告组聚合计算核心指标（用于广告组层级规则判断）
    返回每个广告组的汇总指标
    """
    if not ad_group_ids:
        return []

    query = {
        "query": {
            "bool": {
                "must": [
                    {"terms": {"ad_group_id": list(ad_group_ids)}},
                    {"range": {"data_date": {"gte": start_date, "lte": end_date}}}
                ]
            }
        },
        "size": 0,
        "aggs": {
            "by_adgroup": {
                "terms": {"field": "ad_group_id", "size": 10000},
                "aggs": {
                    "impressions": {
                        "filter": {"term": {"data_type": 1}},
                        "aggs": {"value": {"sum": {"field": "data_value"}}}
                    },
                    "clicks": {
                        "filter": {"term": {"data_type": 2}},
                        "aggs": {"value": {"sum": {"field": "data_value"}}}
                    },
                    "cost": {
                        "filter": {"term": {"data_type": 3}},
                        "aggs": {"value": {"sum": {"field": "data_value"}}}
                    },
                    "conversions": {
                        "filter": {"term": {"data_type": 4}},
                        "aggs": {"value": {"sum": {"field": "data_value"}}}
                    }
                }
            }
        }
    }

    try:
        response = es_client.search(index="ad_stat_data", **query)
        result = []

        for bucket in response["aggregations"]["by_adgroup"]["buckets"]:
            ad_group_id = bucket["key"]
            impressions = bucket["impressions"]["value"]["value"]
            clicks = bucket["clicks"]["value"]["value"]
            cost = bucket["cost"]["value"]["value"]
            conversions = bucket["conversions"]["value"]["value"]

            ctr = clicks / impressions if impressions > 0 else 0
            cvr = conversions / clicks if clicks > 0 else 0
            cpc = cost / clicks if clicks > 0 else 0
            cpa = cost / conversions if conversions > 0 else float("inf")

            result.append({
                "id": ad_group_id,
                "name": f"广告组{ad_group_id}",
                "impressions": impressions,
                "clicks": clicks,
                "cost": cost,
                "conversions": conversions,
                "ctr": ctr,
                "cvr": cvr,
                "cpc": cpc,
                "cpa": cpa
            })

        logger.info(f"按广告组聚合计算了 {len(result)} 条指标数据")
        return result

    except Exception as e:
        logger.error(f"按广告组聚合指标失败: {e}")
        return []
