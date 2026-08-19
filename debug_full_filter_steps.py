#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
import logging
logging.basicConfig(level=logging.INFO)
from elasticsearch import Elasticsearch
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition

es = Elasticsearch(["http://localhost:9200"])
executor = FilterExecutor(es)

# Full multi-step plan
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
        output_field="campaign_id",
        index="ad_stat_data",
        conditions=[
            FilterCondition(field="campaign_name", operator="contains", value="best"),
            FilterCondition(field="status", operator="=", value=1),
        ]
    ),
]

plan = FilterPlan(
    filter_type="where_filter",
    target_level="campaign",
    entity_ids=None,
    steps=steps,
)

print("=== Starting full test ===")
result = executor.execute(plan, advertiser_ids=["6"], time_range={"start_date": "2000-01-01", "end_date": "2026-08-17"})

print(f"\n=== FINAL RESULT ===")
print(f"entity_ids: {result.entity_ids}")
print(f"total_count: {result.total_count}")
