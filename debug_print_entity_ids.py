#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition

es = Elasticsearch(["http://localhost:9200"])
executor = FilterExecutor(es)

# For case 52: "广告主6转化率最高的三个创意"
# Filter plan:
# Step 1: filter advertiser = 6 (advertiser level)
# Step 2: cross_level_down to creative (no extra conditions)
# → should return all 80 creatives for advertiser 6
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

print("=== Testing case 52 plan ===\n")
result = executor.execute(plan, advertiser_ids=["6"], time_range={"start_date": "2000-01-01", "end_date": "2026-08-17"})

print(f"Result:")
print(f"  entity_ids ({len(result.entity_ids)}): {result.entity_ids[:10]}...")
print(f"  total_count: {result.total_count}")
print(f"  entity_level: {result.entity_level}")
