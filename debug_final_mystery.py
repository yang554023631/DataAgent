#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
import asyncio
from elasticsearch import Elasticsearch
from src.nl_dsl.empty_checker import EmptyResultChecker
from src.analysis.models import AnalysisPlan, AnalysisTimeRange
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition

es = Elasticsearch(["http://localhost:9200"])

# Exact same as request:
executor = FilterExecutor(es)
steps = [
    FilterStep(
        step_id="1",
        step_type="where_filter",
        level="advertiser",
        index="advertiser",
        output_field="advertiser_id",
        conditions=[
            FilterCondition(field="advertiser_id", operator="=", value=6),
        ]
    ),
    FilterStep(
        step_id="2",
        step_type="cross_level_down",
        level="advertiser",
        output_field="creative_id",
        index="ad_stat_data",
        conditions=[],
    ),
]
plan = FilterPlan(
    filter_type="where_filter",
    target_level="creative",
    entity_ids=None,
    steps=steps,
)
filter_result = executor.execute(plan, advertiser_ids=["6"], time_range={"start_date": "2000-01-01", "end_date": "2026-08-17"})
print(f"FilterResult:")
print(f"  entity_ids: {len(filter_result.entity_ids)}")
print(f"  entity_level: {filter_result.entity_level}")
print(f"  Is it None? {filter_result.entity_ids is None}")
print(f"  All int: {all(isinstance(x, int) for x in filter_result.entity_ids)}")

# Now check what EmptyChecker gets
checker = EmptyResultChecker(es)
analysis_plan = AnalysisPlan(
    analysis_type="entity_table",
    chart_type="table",
    time_range=AnalysisTimeRange(
        start_date="2000-01-01",
        end_date="2026-08-17",
        granularity="day"
    ),
    metrics=["conversions", "impressions", "cost", "cvr", "clicks"],
    dimensions=["creative_id", "creative_name"],
    filters=[]
)

import logging
logging.basicConfig(level=logging.INFO)

async def run():
    result = await checker.async_check(
        analysis_plan=analysis_plan,
        advertiser_ids=["6"],
        filter_result=filter_result
    )
    print(f"\nEmptyCheckResult:")
    print(f"  found_error: {result.found_error}")
    print(f"  error_type: {result.error_type}")

asyncio.run(run())
