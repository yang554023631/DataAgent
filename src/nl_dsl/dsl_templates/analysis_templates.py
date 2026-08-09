"""
分析类 DSL 模板 (5 types)
"""
from typing import Dict, Any, List, Optional
from .common import (
    get_data_type,
    get_level_field,
    is_derived_metric,
    build_bucket_script,
    build_base_metric_sum_aggs,
    build_common_filters,
    DERIVED_METRICS,
)

# Allowed operators for value filters
ALLOWED_VALUE_OPERATORS = {">", "<", ">=", "<=", "=="}
# Allowed order directions
ALLOWED_ORDER_DIRS = {"asc", "desc"}
# Allowed granularities for date histograms
ALLOWED_GRANULARITIES = {"day", "week", "month"}


def build_single_series_trend(
    advertiser_ids: List[str],
    start_date: str,
    end_date: str,
    metric: str,
    granularity: str,
    index: str = "ad_stat_data",
) -> Dict[str, Any]:
    """A1: 单系列趋势分析"""
    # Validate granularity
    if granularity not in ALLOWED_GRANULARITIES:
        raise ValueError(
            f"Invalid granularity '{granularity}'. Allowed: {', '.join(sorted(ALLOWED_GRANULARITIES))}"
        )

    data_type = get_data_type(metric)
    if data_type is None:
        raise ValueError(f"Unknown metric: {metric}")

    # Map granularity to Elasticsearch interval
    interval_map = {
        "day": "1d",
        "week": "1w",
        "month": "1M"
    }
    interval = interval_map[granularity]

    dsl = {
        "index": index,
        "query": {
            "bool": {
                "filter": build_common_filters(advertiser_ids, start_date, end_date, [data_type])
            }
        },
        "size": 0,
        "aggs": {
            "by_date": {
                "date_histogram": {
                    "field": "data_date",
                    "interval": interval,
                    "format": "yyyy-MM-dd"
                },
                "aggs": {
                    "metric_sum": {"sum": {"field": "data_value"}}
                }
            }
        },
    }
    return dsl


def build_multi_series_trend(
    advertiser_ids: List[str],
    start_date: str,
    end_date: str,
    metric: str,
    series_level: str,
    series_ids: Optional[List[Any]] = None,
    granularity: str = "day",
    index: str = "ad_stat_data",
) -> Dict[str, Any]:
    """A2: 多系列趋势分析"""
    # Validate granularity
    if granularity not in ALLOWED_GRANULARITIES:
        raise ValueError(
            f"Invalid granularity '{granularity}'. Allowed: {', '.join(sorted(ALLOWED_GRANULARITIES))}"
        )

    data_type = get_data_type(metric)
    if data_type is None:
        raise ValueError(f"Unknown metric: {metric}")

    level_field = get_level_field(series_level)

    # Map granularity to Elasticsearch interval
    interval_map = {
        "day": "1d",
        "week": "1w",
        "month": "1M"
    }
    interval = interval_map[granularity]

    filters = build_common_filters(advertiser_ids, start_date, end_date, [data_type])

    # Add series IDs filter if provided
    if series_ids:
        filters.append({"terms": {level_field: series_ids}})

    dsl = {
        "index": index,
        "query": {
            "bool": {
                "filter": filters
            }
        },
        "size": 0,
        "aggs": {
            "by_date": {
                "date_histogram": {
                    "field": "data_date",
                    "interval": interval,
                    "format": "yyyy-MM-dd"
                },
                "aggs": {
                    f"by_{series_level}": {
                        "terms": {"field": level_field, "size": 100},
                        "aggs": {
                            "metric_sum": {"sum": {"field": "data_value"}}
                        }
                    }
                }
            }
        },
    }
    return dsl


def build_entity_table(
    advertiser_ids: List[str],
    start_date: str,
    end_date: str,
    metrics: List[str],
    group_by_level: str,
    order_by: Optional[str] = None,
    order_dir: str = "desc",
    limit: int = 100,
    index: str = "ad_stat_data",
) -> Dict[str, Any]:
    """A3: 实体明细表格"""
    # Validate order direction
    if order_dir not in ALLOWED_ORDER_DIRS:
        raise ValueError(
            f"Invalid order_dir '{order_dir}'. Allowed: {', '.join(sorted(ALLOWED_ORDER_DIRS))}"
        )

    level_field = get_level_field(group_by_level)

    # Separate base metrics and derived metrics
    base_metrics = []
    derived_metrics = []
    for metric in metrics:
        if is_derived_metric(metric):
            derived_metrics.append(metric)
            base_metrics.extend(DERIVED_METRICS[metric]["depends_on"])
        else:
            base_metrics.append(metric)

    # Remove duplicates from base_metrics
    base_metrics = list(set(base_metrics))

    # Get data types for base metrics
    data_types = [get_data_type(m) for m in base_metrics if get_data_type(m) is not None]

    dsl = {
        "index": index,
        "query": {
            "bool": {
                "filter": build_common_filters(advertiser_ids, start_date, end_date, data_types)
            }
        },
        "size": 0,
        "aggs": {
            f"by_{group_by_level}": {
                "terms": {
                    "field": level_field,
                    "size": limit
                },
                "aggs": {}
            }
        },
    }

    terms_aggs = dsl["aggs"][f"by_{group_by_level}"]["aggs"]

    # Add base metric sum aggregations
    base_aggs = build_base_metric_sum_aggs(base_metrics)
    terms_aggs.update(base_aggs)

    # Add derived metric bucket_script aggregations
    for derived_metric in derived_metrics:
        derived_agg = build_bucket_script(derived_metric)
        terms_aggs.update(derived_agg)

    # Add order by if specified
    if order_by:
        order_path = None
        if is_derived_metric(order_by):
            order_path = order_by
        else:
            order_path = f"sum_{order_by}>value"

        dsl["aggs"][f"by_{group_by_level}"]["terms"]["order"] = {order_path: order_dir}

    return dsl


def build_top_n_entities(
    advertiser_ids: List[str],
    start_date: str,
    end_date: str,
    metric: str,
    group_by_level: str,
    n: int = 10,
    order_dir: str = "desc",
    index: str = "ad_stat_data",
) -> Dict[str, Any]:
    """A4: Top N 实体（build_entity_table 的简化版）"""
    return build_entity_table(
        advertiser_ids=advertiser_ids,
        start_date=start_date,
        end_date=end_date,
        metrics=[metric],
        group_by_level=group_by_level,
        order_by=metric,
        order_dir=order_dir,
        limit=n,
        index=index,
    )


def build_period_comparison_summary(
    advertiser_ids: List[str],
    current_start: str,
    current_end: str,
    compare_start: str,
    compare_end: str,
    metrics: List[str],
    index: str = "ad_stat_data",
) -> Dict[str, Any]:
    """A5: 时期对比汇总"""
    # Separate base metrics and derived metrics
    base_metrics = []
    derived_metrics = []
    for metric in metrics:
        if is_derived_metric(metric):
            derived_metrics.append(metric)
            base_metrics.extend(DERIVED_METRICS[metric]["depends_on"])
        else:
            base_metrics.append(metric)

    # Remove duplicates from base_metrics
    base_metrics = list(set(base_metrics))

    # Get data types for base metrics
    data_types = [get_data_type(m) for m in base_metrics if get_data_type(m) is not None]

    dsl = {
        "index": index,
        "query": {
            "bool": {
                "filter": [
                    {"terms": {"advertiser_id": advertiser_ids}},
                    {"terms": {"data_type": data_types}}
                ]
            }
        },
        "size": 0,
        "aggs": {
            "current_period": {
                "filter": {
                    "range": {
                        "data_date": {
                            "gte": current_start,
                            "lte": current_end
                        }
                    }
                },
                "aggs": {}
            },
            "compare_period": {
                "filter": {
                    "range": {
                        "data_date": {
                            "gte": compare_start,
                            "lte": compare_end
                        }
                    }
                },
                "aggs": {}
            }
        },
    }

    # Add aggregations to both periods
    for period_key in ["current_period", "compare_period"]:
        period_aggs = dsl["aggs"][period_key]["aggs"]

        # Add base metric sum aggregations
        base_aggs = build_base_metric_sum_aggs(base_metrics)
        period_aggs.update(base_aggs)

        # Add derived metric bucket_script aggregations
        for derived_metric in derived_metrics:
            derived_agg = build_bucket_script(derived_metric)
            period_aggs.update(derived_agg)

    return dsl


def build_audience_distribution(
    advertiser_ids: List[str],
    start_date: str,
    end_date: str,
    metric: str,
    audience_type: str,
    index: str = "ad_stat_data",
) -> Dict[str, Any]:
    """A6: 受众分布分析"""
    data_type = get_data_type(metric)
    if data_type is None:
        raise ValueError(f"Unknown metric: {metric}")

    filters = build_common_filters(advertiser_ids, start_date, end_date, [data_type])
    filters.append({"term": {"audience_type": audience_type}})

    dsl = {
        "index": index,
        "query": {
            "bool": {
                "filter": filters
            }
        },
        "size": 0,
        "aggs": {
            "by_audience": {
                "terms": {"field": "audience_value", "size": 100},
                "aggs": {
                    "metric_sum": {"sum": {"field": "data_value"}}
                }
            }
        },
    }
    return dsl


def build_summary(
    advertiser_ids: List[str],
    start_date: str,
    end_date: str,
    metrics: List[str],
    index: str = "ad_stat_data",
) -> Dict[str, Any]:
    """A7: 汇总指标分析"""
    # Separate base metrics and derived metrics
    base_metrics = []
    derived_metrics = []
    for metric in metrics:
        if is_derived_metric(metric):
            derived_metrics.append(metric)
            base_metrics.extend(DERIVED_METRICS[metric]["depends_on"])
        else:
            base_metrics.append(metric)

    # Remove duplicates from base_metrics
    base_metrics = list(set(base_metrics))

    # Get data types for base metrics
    data_types = [get_data_type(m) for m in base_metrics if get_data_type(m) is not None]

    dsl = {
        "index": index,
        "query": {
            "bool": {
                "filter": build_common_filters(advertiser_ids, start_date, end_date, data_types)
            }
        },
        "size": 0,
        "aggs": {},
    }

    # Add base metric sum aggregations
    base_aggs = build_base_metric_sum_aggs(base_metrics)
    dsl["aggs"].update(base_aggs)

    # Add derived metric bucket_script aggregations
    for derived_metric in derived_metrics:
        derived_agg = build_bucket_script(derived_metric)
        dsl["aggs"].update(derived_agg)

    return dsl


def build_detail_list(
    advertiser_ids: List[str],
    start_date: str,
    end_date: str,
    metric: str,
    value_operator: Optional[str] = None,
    value_threshold: Optional[float] = None,
    page: int = 1,
    page_size: int = 20,
    index: str = "ad_stat_data",
) -> Dict[str, Any]:
    """A8: 明细列表查询"""
    # Validate operator if provided
    if value_operator is not None and value_operator not in ALLOWED_VALUE_OPERATORS:
        raise ValueError(
            f"Invalid value_operator '{value_operator}'. Allowed: {', '.join(sorted(ALLOWED_VALUE_OPERATORS))}"
        )

    data_type = get_data_type(metric)
    if data_type is None:
        raise ValueError(f"Unknown metric: {metric}")

    filters = build_common_filters(advertiser_ids, start_date, end_date, [data_type])

    # Add value threshold filter if provided
    if value_operator is not None and value_threshold is not None:
        # Normalize operator for Elasticsearch range query
        es_operator_map = {
            "==": "gte",  # For equality, use gte with same value (simplified)
            ">": "gt",
            "<": "lt",
            ">=": "gte",
            "<=": "lte"
        }
        es_operator = es_operator_map[value_operator]

        if value_operator == "==":
            filters.append({
                "range": {
                    "data_value": {
                        "gte": value_threshold,
                        "lte": value_threshold
                    }
                }
            })
        else:
            filters.append({
                "range": {
                    "data_value": {
                        es_operator: value_threshold
                    }
                }
            })

    dsl = {
        "index": index,
        "query": {
            "bool": {
                "filter": filters
            }
        },
        "from": (page - 1) * page_size,
        "size": page_size,
        "sort": [
            {"data_date": {"order": "desc"}},
            {"data_value": {"order": "desc"}}
        ]
    }
    return dsl