#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
import asyncio
from elasticsearch import Elasticsearch
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition

es = Elasticsearch(["http://localhost:9200"])

# Simulate the actual FilterPlan that CoT generates for case 18
# Step 1: filter advertiser = 6
# Step 2: cross_level_down to campaign, where campaign_name like 'best' AND status = 1

print("=== Testing with multiple steps (actual plan from CoT) ===")

steps = [
    FilterStep(
        step_id="1",
        step_type="where_filter",
        level="advertiser",
        index="advertiser",
        output_field="advertiser_id",
        conditions=[
            FilterCondition(field="advertiser_id", operator="eq", value=6),
        ]
    ),
    FilterStep(
        step_id="2",
        step_type="cross_level_down",
        level="advertiser",
        output_field="campaign_id",
        index="ad_stat_data",
        conditions=[
            FilterCondition(field="campaign_name", operator="like", value="best"),
            FilterCondition(field="status", operator="eq", value=1),
        ]
    ),
]

plan = FilterPlan(
    filter_type="where_filter",
    target_level="campaign",
    entity_ids=None,
    steps=steps,
)

executor = FilterExecutor(es)
result = executor.execute(plan, advertiser_ids=["6"], time_range={"start_date": "2000-01-01", "end_date": "2026-08-17"})

print(f"Result:")
print(f"  entity_ids: {result.entity_ids}")
print(f"  total_count: {result.total_count}")
