#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.empty_checker import EmptyResultChecker
from src.nl_dsl.models import AnalysisPlan, AnalysisTimeRange
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition

es = Elasticsearch(["http://localhost:9200"])

# Recreate the exact scenario
advertiser_ids = ["6"]
analysis_plan = AnalysisPlan(
    metrics=["conversions", "impressions", "cost", "cvr", "clicks"],
    dimensions=["creative_id", "creative_name"],
    time_range=AnalysisTimeRange(start_date="2000-01-01", end_date="2026-08-17"),
)

# Get filter_result same as actual execution
executor = FilterExecutor(es)
filter_plan = FilterPlan(
    filter_type="cross_level_down",
    target_level="creative",
    steps=[
        FilterStep(
            step_id="1",
            step_type="cross_level_down",
            level="advertiser",
            output_field="creative_id",
            index="ad_stat_data",
            conditions=[],
        )
    ],
    entity_ids=None,
)
time_range_dict = {"start_date": "2000-01-01", "end_date": "2026-08-17"}
filter_result = executor.execute(filter_plan, advertiser_ids, time_range_dict)

print(f"filter_result: {len(filter_result.entity_ids)} entities, all int={all(isinstance(x, int) for x in filter_result.entity_ids)}")
print(f"first 5: {filter_result.entity_ids[:5]}")

# Now run EmptyResultChecker exactly like the graph does
empty_checker = EmptyResultChecker(es)
result = empty_checker.check(
    analysis_plan=analysis_plan,
    advertiser_ids=advertiser_ids,
    filter_result=filter_result
)

print(f"\nEmptyResultChecker result:")
print(f"  found_error: {result.found_error}")
print(f"  error_type: {result.error_type}")
print(f"  hints: {result.hints}")
