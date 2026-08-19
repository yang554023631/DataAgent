#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.dsl_templates.common import build_common_filters, LEVEL_TO_FIELD, get_data_type

es = Elasticsearch(["http://localhost:9200"])

# Check the core sum step that also can fail
advertiser_ids = ["6"]
start_date = "2000-01-01"
end_date = "2026-08-17"
entity_level = "creative"

# Get all creative_ids
must = [{"terms": {"advertiser_id": [6]}}]
resp_dim = es.search(index="creative", body={
    "query": {"bool": {"must": must}},
    "size": 200
})
entity_ids = [hit["_source"]["creative_id"] for hit in resp_dim["hits"]["hits"]]
print(f"Got {len(entity_ids)} creative_ids")

# Build core filters exactly like EmptyResultChecker does
core_metrics = ["cost", "impressions"]
core_data_types = set()
for metric in core_metrics:
    dt = get_data_type(metric)
    if dt is not None:
        core_data_types.add(dt)

core_filters = build_common_filters(
    advertiser_ids=advertiser_ids,
    start_date=start_date,
    end_date=end_date,
    data_types=list(core_data_types)
)
level_field = LEVEL_TO_FIELD.get(entity_level, f"{entity_level}_id")
core_filters.append({"terms": {level_field: entity_ids}})

print(f"\ncore_filters: {len(core_filters)} filters")
for f in core_filters:
    print(f"  {f}")

# Calculate core_sum
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
print(f"\nAggregations found: {list(aggregations.keys())}")
for dt in core_data_types:
    agg_result = aggregations.get(f"sum_dt_{dt}", {})
    dt_sum = agg_result.get("total", {}).get("value", 0)
    name = "cost" if dt == 1 else "impressions"
    print(f"  data_type={dt} ({name}): sum={dt_sum}")
    if dt_sum:
        total_sum += dt_sum

print(f"\nTotal core sum = {total_sum}")
print(f"core_sum == 0 ? {total_sum == 0}")
