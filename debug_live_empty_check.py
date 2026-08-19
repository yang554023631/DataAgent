#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
import asyncio
from elasticsearch import Elasticsearch
from src.nl_dsl.empty_checker import EmptyResultChecker
from src.analysis.models import AnalysisPlan, AnalysisTimeRange
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition

es = Elasticsearch(["http://localhost:9200"])

# This is what the request looks like
from src.nl_dsl.filter_executor import FilterExecutor
executor = FilterExecutor(es)
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
filter_result = executor.execute(plan, advertiser_ids=["6"], time_range={"start_date": "2000-01-01", "end_date": "2026-08-17"})
print(f"Filter got {filter_result.total_count} entities")

# Now let's manually reconstruct what _get_doc_count does
from src.nl_dsl.dsl_templates.common import build_common_filters
from src.nl_dsl.dsl_templates.common import LEVEL_TO_FIELD
time_range = AnalysisTimeRange(
    start_date="2000-01-01",
    end_date="2026-08-17",
    granularity="day"
)
metrics = ["conversions", "impressions", "cost", "cvr", "clicks"]

data_types = set()
from src.nl_dsl.dsl_templates.common import get_data_type
for metric in metrics:
    dt = get_data_type(metric)
    if dt is not None:
        data_types.add(dt)

filters = build_common_filters(
    advertiser_ids=["6"],
    start_date=time_range.start_date,
    end_date=time_range.end_date,
    data_types=list(data_types) if data_types else None,
)

level_field = LEVEL_TO_FIELD.get(filter_result.entity_level, f"{filter_result.entity_level}_id")
entity_ids = filter_result.entity_ids
print(f"Adding terms filter {level_field} with {len(entity_ids)} ids")
print(f"First 5 ids: {entity_ids[:5]}")
print(f"All are int: {all(isinstance(x, int) for x in entity_ids)}")

filters.append({"terms": {level_field: entity_ids}})

dsl = {
    "query": {
        "bool": {
            "filter": filters,
        },
    },
    "size": 0,
}

print(f"\nFinal query:")
print(f"  number of filters: {len(filters)}")
for i, f in enumerate(filters):
    print(f"    [{i}]: {f}")

response = es.search(index="ad_stat_data", body=dsl)
doc_count = response["hits"]["total"]["value"]
print(f"\nFINAL DOC COUNT: {doc_count}")
