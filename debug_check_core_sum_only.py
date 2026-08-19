#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.dsl_templates.common import build_common_filters, get_data_type, LEVEL_TO_FIELD

es = Elasticsearch(["http://localhost:9200"])

# Same as case 52
advertiser_ids = ["6"]
start_date = "2000-01-01"
end_date = "2026-08-17"
entity_level = "creative"

# Get entity_ids from FilterExecutor's result
print("Getting all creative_ids for advertiser 6 from creative dimension...")
must = [{"terms": {"advertiser_id": [6]}}]
resp_dim = es.search(index="creative", body={
    "query": {"bool": {"must": must}},
    "size": 200
})
entity_ids = [hit["_source"]["creative_id"] for hit in resp_dim["hits"]["hits"]]
print(f"Got {len(entity_ids)} entity_ids")

# Build exactly what EmptyResultChecker builds for core sum check
from src.nl_dsl.dsl_templates.common import is_derived_metric, DERIVED_METRICS
metrics = ["conversions", "impressions", "cost", "cvr", "clicks"]
core_metrics = ["cost", "impressions"]

core_data_types = set()
for metric in core_metrics:
    dt = get_data_type(metric)
    if dt is not None:
        core_data_types.add(dt)

print(f"core_data_types: {sorted(core_data_types)}")

core_filters = build_common_filters(
    advertiser_ids=advertiser_ids,
    start_date=start_date,
    end_date=end_date,
    data_types=list(core_data_types),
)
level_field = LEVEL_TO_FIELD.get(entity_level, f"{entity_level}_id")
core_filters.append({"terms": {level_field: entity_ids}})

print(f"\ncore_filters len={len(core_filters)}:")
for i, f in enumerate(core_filters):
    print(f"  [{i}] {f}")

# Build aggs and query
aggs = {}
for dt in core_data_types:
    aggs[f"sum_dt_{dt}"] = {
        "filter": {"term": {"data_type": dt}},
        "aggs": {
            "total": {"sum": {"field": "data_value"}}
        }
    }

dsl = {
    "query": {
        "bool": {
            "filter": core_filters
        }
    },
    "size": 0,
    "aggs": aggs
}

response = es.search(index="ad_stat_data", body=dsl)
total_sum = 0.0
aggregations = response.get("aggregations", {})
print(f"\nAggregations: {list(aggregations.keys())}")
for dt in core_data_types:
    agg_result = aggregations.get(f"sum_dt_{dt}", {})
    dt_sum = agg_result.get("total", {}).get("value", 0)
    name = "cost" if dt == 1 else "impressions"
    print(f"  {name}: sum = {dt_sum}")
    if dt_sum:
        total_sum += dt_sum

print(f"\nFINAL RESULT:")
print(f"  Total core sum (cost + impressions) = {total_sum}")
print(f"  total_sum == 0 ? {total_sum == 0}")
