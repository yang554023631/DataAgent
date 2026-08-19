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

# Get 80 entity ids as FilterExecutor does
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
result = executor.execute(plan, advertiser_ids=["6"], time_range={"start_date": "2000-01-01", "end_date": "2026-08-17"})

print(f"FilterExecutor: {result.total_count} entities, ids={result.entity_ids[:10]}...")
print()

# Now check with EmptyResultChecker
filter_result = result
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

checker = EmptyResultChecker(es)

async def run():
    check_result = await checker.async_check(
        analysis_plan=analysis_plan,
        advertiser_ids=["6"],
        filter_result=filter_result
    )
    print(f"EmptyResultChecker:")
    print(f"  found_error: {check_result.found_error}")
    print(f"  error_type: {check_result.error_type}")
    print(f"  hints: {check_result.hints}")

asyncio.run(run())
