#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition

es = Elasticsearch(["http://localhost:9200"])

# Test case 19: 找出 digital_0 下名称含 mini 的创意，点击量大于50
conditions = [
    FilterCondition(field="creative_name", operator="like", value="mini"),
]

step = FilterStep(
    step_id="1",
    step_type="where_filter",
    level="creative",
    index="creative",
    output_field="creative_id",
    conditions=conditions,
)

plan = FilterPlan(
    filter_type="where_filter",
    target_level="creative",
    entity_ids=None,
    steps=[step],
)

executor = FilterExecutor(es)
result = executor.execute(plan, advertiser_ids=["6"], time_range={"start_date": "2000-01-01", "end_date": "2026-08-17"})

print(f"Result:")
print(f"  entity_ids: {result.entity_ids}")
print(f"  total_count: {result.total_count}")
