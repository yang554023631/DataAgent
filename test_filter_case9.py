#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition

es = Elasticsearch(["http://localhost:9200"])

# Test case 9: 找出 digital_0 名称带 digital 的广告计划
# level: campaign, condition: campaign_name like 'digital'
conditions = [
    FilterCondition(field="campaign_name", operator="like", value="digital"),
]

step = FilterStep(
    step_id="1",
    step_type="where_filter",
    level="campaign",
    index="campaign",
    output_field="campaign_id",
    conditions=conditions,
)

plan = FilterPlan(
    filter_type="where_filter",
    target_level="campaign",
    entity_ids=None,
    steps=[step],
)

executor = FilterExecutor(es)
result = executor.execute(plan, advertiser_ids=["6"], time_range={"start_date": "2000-01-01", "end_date": "2026-08-17"})

print(f"Result:")
print(f"  entity_ids: {result.entity_ids}")
print(f"  total_count: {result.total_count}")
print(f"  truncated: {result.truncated}")
