from typing import Dict, List, Any, Optional, Union
from collections import defaultdict


def extract_entity_ids(es_response: Dict[str, Any], agg_path: str) -> List[Any]:
    """Extract entity IDs from terms buckets at the given aggregation path.

    Args:
        es_response: Full Elasticsearch response dict
        agg_path: Dot-separated path to the terms aggregation (e.g. "by_campaign" or "by_date.by_campaign")

    Returns:
        List of entity IDs (bucket keys)
    """
    current = es_response.get("aggregations", {})
    # Traverse the aggregation path
    for part in agg_path.split("."):
        if not isinstance(current, dict):
            return []
        current = current.get(part, {})

    buckets = current.get("buckets", [])
    return [bucket["key"] for bucket in buckets]


def extract_trend_data(es_response: Dict[str, Any], series_level: Optional[str] = None) -> Dict[str, Any]:
    """Extract trend data from ES response.

    Args:
        es_response: Full Elasticsearch response dict
        series_level: Optional entity level for multi-series trend (if None, assumes single series)

    Returns:
        Structured trend data: {date: {series_id: metric_value} or date: metric_value}
    """
    trend_agg = es_response.get("aggregations", {}).get("by_date", {})
    buckets = trend_agg.get("buckets", [])

    # Only multi-series if series_level is non-empty AND not date-related
    # This matches the logic in _execute_time_trend of AnalysisExecutor
    date_related = ['data_date', 'date', 'day', 'month', 'time']
    is_multi_series = False
    if series_level:
        if series_level.lower() not in date_related:
            is_multi_series = True

    result = {}
    for date_bucket in buckets:
        date_key = date_bucket["key"]

        if is_multi_series:
            # Multi-series trend: nested by_<series_level> aggregation
            series_buckets = date_bucket.get(f"by_{series_level}", {}).get("buckets", [])
            series_data = {}
            for sb in series_buckets:
                series_id = sb["key"]
                # Get the first metric sum (handles both base and derived metrics)
                metric_value = None
                for agg_key, agg_val in sb.items():
                    if agg_key.startswith("sum_") or agg_key == "metric_sum" or agg_key in ["ctr", "cvr", "cpc", "cpm"]:
                        metric_value = agg_val.get("value", agg_val.get("value", None))
                        break
                if metric_value is not None:
                    series_data[series_id] = metric_value
            result[date_key] = series_data
        else:
            # Single series trend
            metric_value = None
            for agg_key, agg_val in date_bucket.items():
                if agg_key.startswith("sum_") or agg_key == "metric_sum" or agg_key in ["ctr", "cvr", "cpc", "cpm"]:
                    metric_value = agg_val.get("value", agg_val.get("value", None))
                    break
            result[date_key] = metric_value

    return result


def extract_entity_table_data(es_response: Dict[str, Any], level: str) -> Dict[Any, Dict[str, float]]:
    """Extract entity table data from ES response.

    Args:
        es_response: Full Elasticsearch response dict
        level: Entity level (advertiser, campaign, ad_group, creative)

    Returns:
        Dict of {entity_id: {metric_name: metric_value}}
    """
    entity_agg = es_response.get("aggregations", {}).get(f"by_{level}", {})
    buckets = entity_agg.get("buckets", [])

    result = {}
    for bucket in buckets:
        entity_id = bucket["key"]
        metrics_data = {}

        # Extract all metric aggregations
        for agg_key, agg_val in bucket.items():
            if agg_key == "key" or agg_key == "doc_count":
                continue
            # Handle both sum aggregations and derived metrics
            if agg_key.startswith("sum_"):
                # sum_{metric} in DSL: {filter: ..., aggs: {value: {sum: {}}}}
                # In ES result: filter aggregation does NOT preserve the 'aggs' key,
                # the inner aggregation is directly at the top level.
                # So structure is: {doc_count: ..., value: {value: 12345}}
                if "value" in agg_val and isinstance(agg_val["value"], dict) and "value" in agg_val["value"]:
                    # Correct path: agg_val['value']['value']
                    metrics_data[agg_key[4:]] = agg_val["value"]["value"]
                elif "value" in agg_val and not isinstance(agg_val["value"], dict):
                    # Fallback: if already flattened (value is directly a number)
                    metrics_data[agg_key[4:]] = agg_val["value"]
            elif "value" in agg_val:
                # Derived metrics (bucket_script) already puts value directly here
                metrics_data[agg_key] = agg_val["value"]

        result[entity_id] = metrics_data

    return result


import logging
logger = logging.getLogger(__name__)

def extract_summary_data(es_response: Dict[str, Any], metrics: List[str]) -> Dict[str, float]:
    """Extract summary metric data from ES response.

    Args:
        es_response: Full Elasticsearch response dict
        metrics: List of metric names to extract

    Returns:
        Dict of {metric_name: metric_value}
    """
    aggs = es_response.get("aggregations", {})
    result = {}

    for metric in metrics:
        # Check for derived metrics first
        if metric in ["ctr", "cvr", "cpc", "cpm"]:
            if metric in aggs:
                # Derived metric: same structure -> metric -> { bucket_script, aggs: { value: { value } } }
                agg_container = aggs[metric]
                if "value" in agg_container:
                    value_agg = agg_container["value"]
                    result[metric] = value_agg.get("value", None)
                else:
                    result[metric] = agg_container.get("value", None)
        else:
            # Base metric: sum_{metric}
            agg_key = f"sum_{metric}"
            if agg_key in aggs:
                # agg structure: agg_key -> { filter: ..., aggs: { value: { sum: ... } } }
                # value is nested one level deeper: aggs[agg_key].value.value
                agg_container = aggs[agg_key]
                if "value" in agg_container:
                    value_agg = agg_container["value"]
                    result[metric] = value_agg.get("value", None)
                    logger.debug(f"extract_summary: metric={metric}, got value={result[metric]}, type={type(result[metric])}")
                else:
                    result[metric] = agg_container.get("value", None)
                    logger.debug(f"extract_summary (else): metric={metric}, got value={result[metric]}, type={type(result[metric])}")

    logger.debug(f"extract_summary final result={result}")
    return result


def extract_comparison_data(es_response: Dict[str, Any], metrics: List[str]) -> Dict[str, Dict[str, float]]:
    """Extract period comparison data from ES response.

    Args:
        es_response: Full Elasticsearch response dict
        metrics: List of metric names to extract

    Returns:
        Dict of {period_name: {metric_name: metric_value}}
    """
    aggs = es_response.get("aggregations", {})
    result = {}

    for period in ["current_period", "compare_period"]:
        period_container = aggs.get(period, {})
        # In Elasticsearch response, sub-aggs are directly in the period container, not under "aggregations"
        period_data = {}

        for metric in metrics:
            if metric in ["ctr", "cvr", "cpc", "cpm"]:
                # Derived metrics are bucket_script, value is directly at metric.value
                if metric in period_container:
                    period_data[metric] = period_container[metric].get("value", None)
            else:
                # Base metrics: build_base_metric_sum_aggs adds filter -> aggs -> value
                # Structure: sum_metric -> {filter: ..., aggs: {value: {sum: ...}}}
                # In response: sum_metric -> doc_count + value.value (the final number)
                agg_key = f"sum_{metric}"
                if agg_key in period_container and "value" in period_container[agg_key]:
                    # Final value is at sum_metric.value.value
                    period_data[metric] = period_container[agg_key]["value"].get("value", None)

        result[period] = period_data

    return result


def extract_audience_data(es_response: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """Extract audience distribution data from ES response.

    Args:
        es_response: Full Elasticsearch response dict

    Returns:
        Dict of {audience_value: {metric_name: metric_value}}
    """
    audience_agg = es_response.get("aggregations", {}).get("by_audience", {})
    buckets = audience_agg.get("buckets", [])

    result = {}
    for bucket in buckets:
        audience_key = bucket["key"]
        metric_values = {}
        # Extract all metric values from the bucket
        for key in bucket:
            if key == "key" or key == "doc_count":
                continue
            # For base metrics: sum_{metric} > value
            if key.startswith("sum_"):
                metric_name = key[4:]  # remove "sum_" prefix
                value = bucket[key].get("value")
                if value is not None:
                    metric_values[metric_name] = value
            else:
                # For derived metrics: directly get value from bucket_script
                value = bucket.get(key, {}).get("value")
                if value is not None:
                    metric_values[key] = value
        if metric_values:
            result[audience_key] = metric_values

    return result


def extract_detail_data(es_response: Dict[str, Any], source_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Extract detailed row data from ES response.

    Args:
        es_response: Full Elasticsearch response dict
        source_fields: Optional list of source fields to extract (if None, extract all)

    Returns:
        List of detail rows (dict of field: value)
    """
    hits = es_response.get("hits", {}).get("hits", [])

    result = []
    for hit in hits:
        source = hit.get("_source", {})
        if source_fields:
            filtered_source = {field: source.get(field) for field in source_fields if field in source}
            result.append(filtered_source)
        else:
            result.append(source)

    return result