"""
DSL Templates public API exports
"""
from .common import (
    LEVEL_TO_FIELD,
    LEVEL_TO_INDEX,
    DERIVED_METRICS,
    get_data_type,
    is_derived_metric,
    get_level_field,
    get_level_index,
    build_time_filter,
    build_bucket_script,
    build_bucket_selector,
    build_base_metric_sum_aggs,
    build_common_filters,
    validate_es_dsl,
)

from .filter_templates import (
    build_having_filter,
    build_derived_having_filter,
    build_where_dimension_filter,
    build_cross_level_up_filter,
    build_cross_level_down_filter_step1,
    build_full_filter,
)

from .analysis_templates import (
    build_single_series_trend,
    build_multi_series_trend,
    build_entity_table,
    build_top_n_entities,
    build_period_comparison_summary,
    build_audience_distribution,
    build_summary,
    build_detail_list,
)

from .result_extractors import (
    extract_entity_ids,
    extract_trend_data,
    extract_entity_table_data,
    extract_summary_data,
    extract_comparison_data,
    extract_audience_data,
    extract_detail_data,
)

__all__ = [
    # Common exports
    "LEVEL_TO_FIELD",
    "LEVEL_TO_INDEX",
    "DERIVED_METRICS",
    "get_data_type",
    "is_derived_metric",
    "get_level_field",
    "get_level_index",
    "build_time_filter",
    "build_bucket_script",
    "build_bucket_selector",
    "build_base_metric_sum_aggs",
    "build_common_filters",
    "validate_es_dsl",

    # Filter templates exports
    "build_having_filter",
    "build_derived_having_filter",
    "build_where_dimension_filter",
    "build_cross_level_up_filter",
    "build_cross_level_down_filter_step1",
    "build_full_filter",

    # Analysis templates exports
    "build_single_series_trend",
    "build_multi_series_trend",
    "build_entity_table",
    "build_top_n_entities",
    "build_period_comparison_summary",
    "build_audience_distribution",
    "build_summary",
    "build_detail_list",

    # Result extractors exports
    "extract_entity_ids",
    "extract_trend_data",
    "extract_entity_table_data",
    "extract_summary_data",
    "extract_comparison_data",
    "extract_audience_data",
    "extract_detail_data",
]
