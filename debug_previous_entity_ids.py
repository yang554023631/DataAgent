#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition

es = Elasticsearch(["http://localhost:9200"])
executor = FilterExecutor(es)

# Two-step plan: typical structure for these queries
# Step 1: filter advertiser = 6
# Step 2: filter campaign where name contains X (in dimension table)
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
        step_type="where_filter",
        level="campaign",
        index="campaign",
        output_field="campaign_id",
        conditions=[
            FilterCondition(field="campaign_name", operator="like", value="digital"),
        ]
    ),
]

plan = FilterPlan(
    filter_type="where_filter",
    target_level="campaign",
    entity_ids=None,
    steps=steps,
)

print("=== Testing two-step plan (advertiser → campaign) ===\n")
result = executor.execute(plan, advertiser_ids=["6"], time_range={"start_date": "2000-01-01", "end_date": "2026-08-17"})

print(f"Result:")
print(f"  entity_ids: {result.entity_ids}")
print(f"  total_count: {result.total_count}")
