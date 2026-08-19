#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition

es = Elasticsearch(["http://localhost:9200"])

# Test case 18 full filtering:
# "digital_0 投放中的广告计划，名称含有 best，列出消耗和点击"
# So:
# - advertiser_ids = ["6"]
# - filters: status = 1 (投放中), campaign_name like "best"

conditions = [
    FilterCondition(field="campaign_name", operator="like", value="best"),
    FilterCondition(field="status", operator="eq", value=1),
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

print(f"FilterExecutor result:")
print(f"  entity_ids: {result.entity_ids}")
print(f"  total_count: {result.total_count}")
print(f"  trace: {[t['status'] for t in result.trace]}")
