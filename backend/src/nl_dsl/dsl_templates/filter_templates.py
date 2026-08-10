"""
筛选类 DSL 模板
"""
from typing import Dict, Any, List, Optional
from .common import (
    get_data_type,
    get_level_field,
    is_derived_metric,
    build_bucket_script,
    build_base_metric_sum_aggs,
    build_common_filters,
    build_bucket_selector,
)

# Allowed operators for having filters
ALLOWED_HAVING_OPERATORS = {">", "<", ">=", "<=", "=="}
# Allowed operators for field conditions
ALLOWED_FIELD_OPERATORS = {"=", "in", ">", "<", ">=", "<=", "contains", "match"}


def build_having_filter(
    advertiser_ids: List[str],
    start_date: str,
    end_date: str,
    metric: str,
    operator: str,
    threshold: float,
    group_by_level: str,
    index: str = "ad_stat_data",
) -> Dict[str, Any]:
    """F2-1: 基础指标 having 筛选"""
    # Validate operator
    if operator not in ALLOWED_HAVING_OPERATORS:
        raise ValueError(
            f"Invalid operator '{operator}'. Allowed operators: {', '.join(sorted(ALLOWED_HAVING_OPERATORS))}"
        )

    level_field = get_level_field(group_by_level)
    data_type = get_data_type(metric)
    if data_type is None:
        raise ValueError(f"Unknown metric: {metric}")

    dsl = {
        "index": index,
        "query": {
            "bool": {
                "filter": build_common_filters(advertiser_ids, start_date, end_date, [data_type])
            }
        },
        "size": 0,
        "aggs": {
            f"by_{group_by_level}": {
                "terms": {"field": level_field, "size": 1000},
                "aggs": {
                    "metric_sum": {"sum": {"field": "data_value"}}
                },
            }
        },
    }

    # Use the common helper for bucket_selector
    bucket_selector = build_bucket_selector("metric_sum", operator, threshold)
    dsl["aggs"][f"by_{group_by_level}"]["aggs"].update(bucket_selector)
    return dsl


def build_derived_having_filter(
    advertiser_ids: List[str],
    start_date: str,
    end_date: str,
    metric: str,
    operator: str,
    threshold: float,
    group_by_level: str,
    index: str = "ad_stat_data",
) -> Dict[str, Any]:
    """F2-2: 衍生指标 having 筛选"""
    # Validate operator
    if operator not in ALLOWED_HAVING_OPERATORS:
        raise ValueError(
            f"Invalid operator '{operator}'. Allowed operators: {', '.join(sorted(ALLOWED_HAVING_OPERATORS))}"
        )

    from .common import DERIVED_METRICS
    if not is_derived_metric(metric):
        raise ValueError(f"Not a derived metric: {metric}")

    info = DERIVED_METRICS[metric]
    base_metrics = info["depends_on"]
    data_types = [get_data_type(m) for m in base_metrics if get_data_type(m) is not None]
    level_field = get_level_field(group_by_level)

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
                "terms": {"field": level_field, "size": 1000},
                "aggs": {},
            }
        },
    }

    terms_aggs = dsl["aggs"][f"by_{group_by_level}"]["aggs"]
    # 基础指标 sum 聚合
    base_aggs = build_base_metric_sum_aggs(base_metrics)
    terms_aggs.update(base_aggs)
    # bucket_script 衍生指标
    derived_agg = build_bucket_script(metric)
    terms_aggs.update(derived_agg)
    # Use the common helper for bucket_selector
    bucket_selector = build_bucket_selector(metric, operator, threshold)
    terms_aggs.update(bucket_selector)
    return dsl


def build_where_dimension_filter(
    advertiser_ids: List[str],
    level: str,
    conditions: List[Dict[str, Any]],
    index: str = None,
) -> Dict[str, Any]:
    """F1: Where 型维度属性筛选"""
    if index is None:
        index = level
    level_field = get_level_field(level)
    # Convert advertiser_ids to integer if possible (dimension tables store integer IDs)
    converted_advertiser_ids = []
    for aid in advertiser_ids:
        try:
            converted_advertiser_ids.append(int(aid))
        except ValueError:
            converted_advertiser_ids.append(aid)
    filters = [{"terms": {"advertiser_id": converted_advertiser_ids}}]
    for cond in conditions:
        filters.append(_build_field_condition(cond["field"], cond["operator"], cond["value"]))

    dsl = {
        "index": index,
        "query": {"bool": {"filter": filters}},
        "size": 0,
        "aggs": {
            f"by_{level}": {
                "terms": {"field": level_field, "size": 1000}
            }
        },
    }
    return dsl


def build_cross_level_up_filter(
    advertiser_ids: List[str],
    low_level: str,
    low_level_field: str,
    low_level_value: Any,
    low_level_operator: str,
    target_level: str,
    index: str = None,
) -> Dict[str, Any]:
    """F3-1: 自下而上跨层级筛选（属性条件）"""
    if index is None:
        index = low_level
    target_field = get_level_field(target_level)
    condition = _build_field_condition(low_level_field, low_level_operator, low_level_value)

    # Convert advertiser_ids to integer if possible
    converted_advertiser_ids = []
    for aid in advertiser_ids:
        try:
            converted_advertiser_ids.append(int(aid))
        except ValueError:
            converted_advertiser_ids.append(aid)

    dsl = {
        "index": index,
        "query": {
            "bool": {
                "filter": [
                    {"terms": {"advertiser_id": converted_advertiser_ids}},
                    condition,
                ]
            }
        },
        "size": 0,
        "aggs": {
            f"by_{target_level}": {
                "terms": {"field": target_field, "size": 1000}
            }
        },
    }
    return dsl


def build_cross_level_down_filter_step1(
    advertiser_ids: List[str],
    high_level: str,
    conditions: List[Dict[str, Any]],
    index: str = None,
) -> Dict[str, Any]:
    """F4-2: 自上而下跨层级筛选 - 第一步：查高层级 ID"""
    if index is None:
        index = high_level
    high_field = get_level_field(high_level)
    # Convert advertiser_ids to integer if possible
    converted_advertiser_ids = []
    for aid in advertiser_ids:
        try:
            converted_advertiser_ids.append(int(aid))
        except ValueError:
            converted_advertiser_ids.append(aid)
    filters = [{"terms": {"advertiser_id": converted_advertiser_ids}}]
    for cond in conditions:
        filters.append(_build_field_condition(cond["field"], cond["operator"], cond["value"]))

    dsl = {
        "index": index,
        "query": {"bool": {"filter": filters}},
        "size": 0,
        "aggs": {
            f"by_{high_level}": {
                "terms": {"field": high_field, "size": 1000}
            }
        },
    }
    return dsl


def build_full_filter(
    advertiser_ids: List[str],
    level: str,
) -> None:
    """F6: 全量/无筛选 - 不需要专门的筛选查询，返回 None

    全量筛选意味着直接用 advertiser_id + 层级做过滤，
    这部分过滤会被合并到分析查询的 query.bool.filter 里。
    """
    return None


def _build_field_condition(field: str, operator: str, value: Any) -> Dict[str, Any]:
    """构建单个字段的过滤条件"""
    if operator not in ALLOWED_FIELD_OPERATORS:
        raise ValueError(
            f"Invalid operator '{operator}'. Allowed operators: {', '.join(sorted(ALLOWED_FIELD_OPERATORS))}"
        )

    # Operator mapping: symbol -> Elasticsearch keyword
    operator_map = {
        ">=": "gte",
        ">": "gt",
        "<=": "lte",
        "<": "lt",
    }

    if operator == "=":
        return {"term": {field: value}}
    elif operator == "in":
        return {"terms": {field: value}}
    elif operator in operator_map:
        es_operator = operator_map[operator]
        return {"range": {field: {es_operator: value}}}
    elif operator in ("contains", "match"):
        return {"match": {field: value}}

    # This line should never be reached due to the validation above
    raise ValueError(f"Unhandled operator '{operator}'")
