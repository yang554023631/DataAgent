#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
import asyncio
from elasticsearch import Elasticsearch
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.empty_checker import EmptyResultChecker
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition
from src.analysis.models import AnalysisPlan, AnalysisTimeRange
from src.nl_dsl.models import FilterResult

es = Elasticsearch(["http://localhost:9200"])

# Exact same flow that should happen:
# Step 1: filter advertiser_id = 6 on advertiser level
# Step 2: cross_level_down to creative (no extra conditions)
# Since there are no dimension_conditions, it should go to traditional two-step aggregation
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

print("=== Step 1: FilterExecutor.execute ===\n")
executor = FilterExecutor(es)
filter_result = executor.execute(plan, advertiser_ids=["6"], time_range={"start_date": "2000-01-01", "end_date": "2026-08-17"})

print(f"FilterExecutor result:")
print(f"  entity_ids length: {len(filter_result.entity_ids)}")
print(f"  First 10: {filter_result.entity_ids[:10]}")
print(f"  All integers? {all(isinstance(x, int) for x in filter_result.entity_ids)}")
print()

# Now run EmptyResultChecker
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

async def run_check():
    check_result = await checker.async_check(
        analysis_plan=analysis_plan,
        advertiser_ids=["6"],
        filter_result=filter_result
    )
    print(f"EmptyResultChecker result:")
    print(f"  found_error: {check_result.found_error}")
    print(f"  error_type: {check_result.error_type}")
    print(f"  hints: {check_result.hints}")

    # Let's manually count docs:
    from src.nl_dsl.dsl_templates.common import build_common_filters
    from src.nl_dsl.dsl_templates.common import LEVEL_TO_FIELD
    data_types = set()
    from src.nl_dsl.dsl_templates.common import get_data_type
    for metric in analysis_plan.metrics:
        dt = get_data_type(metric)
        if dt is not None:
            data_types.add(dt)
    filters = build_common_filters(
        advertiser_ids=["6"],
        start_date=analysis_plan.time_range.start_date,
        end_date=analysis_plan.time_range.end_date,
        data_types=list(data_types) if data_types else None,
    )
    level_field = LEVEL_TO_FIELD.get(filter_result.entity_level, f"{filter_result.entity_level}_id")
    filters.append({"terms": {level_field: filter_result.entity_ids}})
    dsl = {
        "query": {"bool": {"filter": filters}},
        "size": 0,
    }
    response = es.search(index="ad_stat_data", body=dsl)
    doc_count = response["hits"]["total"]["value"]
    print()
    print(f"Manual doc count: {doc_count}")

asyncio.run(run_check())
