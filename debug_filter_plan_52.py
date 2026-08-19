#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition, FilterResult

es = Elasticsearch(["http://localhost:9200"])
executor = FilterExecutor(es)

# Query: "广告主6转化率最高的创意"
# It should be: advertiser 6 -> cross_level_down to creative, NO conditions
advertiser_ids = ["6"]
time_range = {"start_date": "2000-01-01", "end_date": "2026-08-17"}

# What does the filter plan look like?
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

print("Executing filter plan...")
result = executor.execute(filter_plan, advertiser_ids, time_range)
print(f"\nResult:")
print(f"  entity_level: {result.entity_level}")
print(f"  total_count: {result.total_count}")
print(f"  entity_ids[:10]: {result.entity_ids[:10]}")
print(f"  len(entity_ids): {len(result.entity_ids)}")
print(f"  Are all int? {all(isinstance(x, int) for x in result.entity_ids)}")
