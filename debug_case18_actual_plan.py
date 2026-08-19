#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition

es = Elasticsearch(["http://localhost:9200"])
executor = FilterExecutor(es)

# Actual plan from CoT for case 18:
# Single where_filter step on campaign level with two conditions: status=1 AND campaign_name like 'best'
steps = [
    FilterStep(
        step_id="1",
        step_type="where_filter",
        level="campaign",
        index="campaign",
        output_field="campaign_id",
        conditions=[
            FilterCondition(field="status", operator="eq", value=1),
            FilterCondition(field="campaign_name", operator="like", value="best"),
        ]
    ),
]

plan = FilterPlan(
    filter_type="where_filter",
    target_level="campaign",
    entity_ids=None,
    steps=steps,
)

print("=== Testing case 18 actual single-step plan ===\n")
result = executor.execute(plan, advertiser_ids=["6"], time_range={"start_date": "2000-01-01", "end_date": "2026-08-17"})

print(f"Result:")
print(f"  entity_ids: {result.entity_ids}")
print(f"  total_count: {result.total_count}")
