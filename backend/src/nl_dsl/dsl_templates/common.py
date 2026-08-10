from typing import Optional, Dict, List, Any
from src.nl_dsl.field_mapping import METRICS


# Level to corresponding ID field mapping
LEVEL_TO_FIELD: Dict[str, str] = {
    "advertiser": "advertiser_id",
    "campaign": "campaign_id",
    "ad_group": "adgroup_id",
    "creative": "creative_id"
}


# Derived metrics definitions
DERIVED_METRICS: Dict[str, Dict[str, Any]] = {
    "ctr": {
        "depends_on": ["clicks", "impressions"],
        "unit": "%",
        "display_name_cn": "点击率",
        "formula": "params.clicks / params.impressions"
    },
    "cvr": {
        "depends_on": ["conversions", "clicks"],
        "unit": "%",
        "display_name_cn": "转化率",
        "formula": "params.conversions / params.clicks"
    },
    "cpc": {
        "depends_on": ["cost", "clicks"],
        "unit": "元",
        "display_name_cn": "单次点击成本",
        "formula": "params.cost / params.clicks"
    },
    "cpm": {
        "depends_on": ["cost", "impressions"],
        "unit": "元",
        "display_name_cn": "千次曝光成本",
        "formula": "params.cost / params.impressions * 1000"
    }
}


def get_data_type(metric: str) -> Optional[int]:
    """Look up data_type from METRICS for a given metric name."""
    return METRICS.get(metric, {}).get("data_type")


def is_derived_metric(metric: str) -> bool:
    """Check if a metric is a derived metric."""
    return metric in DERIVED_METRICS


def get_level_field(level: str) -> str:
    """Get the ID field name for a given entity level."""
    return LEVEL_TO_FIELD[level]


def build_time_filter(start_date: str, end_date: str, field: str = "data_date") -> Dict[str, Any]:
    """Build an Elasticsearch range filter for a date range."""
    return {
        "range": {
            field: {
                "gte": start_date,
                "lte": end_date
            }
        }
    }


def build_bucket_script(metric: str) -> Dict[str, Any]:
    """Build an Elasticsearch bucket_script aggregation for a derived metric."""
    if metric not in DERIVED_METRICS:
        raise ValueError(f"Unknown derived metric: {metric}")

    derived = DERIVED_METRICS[metric]
    depends_on = derived["depends_on"]
    buckets_path = {dep: f"sum_{dep}>value" for dep in depends_on}

    return {
        metric: {
            "bucket_script": {
                "buckets_path": buckets_path,
                "script": derived["formula"]
            }
        }
    }


def build_bucket_selector(value_path: str, operator: str, threshold: float) -> Dict[str, Any]:
    """Build an Elasticsearch bucket_selector pipeline aggregation."""
    return {
        "having_filter": {
            "bucket_selector": {
                "buckets_path": {"value": value_path},
                "script": f"params.value {operator} {threshold}"
            }
        }
    }


def build_base_metric_sum_aggs(metrics: List[str]) -> Dict[str, Any]:
    """Build filter+sum aggregations for multiple base metrics (long table model)."""
    aggs = {}
    for metric in metrics:
        data_type = get_data_type(metric)
        if data_type is None:
            raise ValueError(f"Unknown base metric: {metric}")
        agg_key = f"sum_{metric}"
        aggs[agg_key] = {
            "filter": {"term": {"data_type": data_type}},
            "aggs": {
                "value": {
                    "sum": {"field": "data_value"}
                }
            }
        }
    return aggs


def build_common_filters(
    advertiser_ids: List[str],
    start_date: str,
    end_date: str,
    data_types: Optional[List[int]] = None,
    date_field: str = "data_date"
) -> List[Dict[str, Any]]:
    """Build common Elasticsearch filters: advertiser ID + date range + optional data types.

    Automatically converts advertiser_ids to integer if possible,
    because ES mapping stores advertiser_id as integer. Keep as string if UUID.
    """
    filters = []

    # Advertiser ID terms filter - convert to int if possible
    converted_ids = []
    for adv_id in advertiser_ids:
        try:
            converted_ids.append(int(adv_id))
        except ValueError:
            converted_ids.append(adv_id)
    filters.append({"terms": {"advertiser_id": converted_ids}})

    # Date range filter
    filters.append(build_time_filter(start_date, end_date, date_field))

    # Optional data type terms filter
    if data_types is not None:
        filters.append({"terms": {"data_type": data_types}})

    return filters


def validate_es_dsl(dsl: Dict[str, Any], index: str = "ad_stat_data") -> tuple[bool, str | None]:
    """
    Validate an Elasticsearch DSL query using the indices.validate_query API.

    Args:
        dsl: The DSL query dictionary to validate
        index: The Elasticsearch index to validate against

    Returns:
        (is_valid: bool, error_message: str | None)

    Raises:
        ImportError: If elasticsearch package is not installed
        ConnectionError: If cannot connect to Elasticsearch (handled in tests for skipping)
    """
    from elasticsearch import Elasticsearch, exceptions

    # Try to create an Elasticsearch client
    es = Elasticsearch()

    try:
        # Perform validation
        response = es.indices.validate_query(index=index, body=dsl)
        return response["valid"], response.get("error", "Unknown error")
    except exceptions.ConnectionError as e:
        raise ConnectionError(f"Failed to connect to Elasticsearch: {e}") from e
    except Exception as e:
        return False, str(e)