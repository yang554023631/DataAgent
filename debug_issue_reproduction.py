#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.dsl_templates.common import build_common_filters, LEVEL_TO_FIELD

es = Elasticsearch(["http://localhost:9200"])

# Exact same scenario:
advertiser_ids = ["6"]
start_date = "2000-01-01"
end_date = "2026-08-17"
metrics = ["conversions", "impressions", "cost", "cvr", "clicks"]

# Build data_types exactly like EmptyResultChecker does
from src.nl_dsl.dsl_templates.common import get_data_type, is_derived_metric, DERIVED_METRICS
data_types = set()
for metric in metrics:
    if is_derived_metric(metric):
        derived = DERIVED_METRICS[metric]
        for dep in derived["depends_on"]:
            dt = get_data_type(dep)
            if dt is not None:
                data_types.add(dt)
    else:
        dt = get_data_type(metric)
        if dt is not None:
            data_types.add(dt)

print(f"metrics: {metrics}")
print(f"data_types after processing: {sorted(data_types)}")

# Get all creative_ids from creative dimension table for advertiser 6
must = [{"terms": {"advertiser_id": [6]}}]
dsl_dim = {
    "query": {"bool": {"must": must}},
    "size": 200,
}
resp_dim = es.search(index="creative", body=dsl_dim)
entity_ids = [hit["_source"]["creative_id"] for hit in resp_dim["hits"]["hits"]]
print(f"\nGot {len(entity_ids)} creative_ids from dimension table")
print(f"entity_ids are all integers: {all(isinstance(x, int) for x in entity_ids)}")
print(f"First 10: {entity_ids[:10]}")

# Build filters exactly like EmptyResultChecker does
filters = build_common_filters(
    advertiser_ids=advertiser_ids,
    start_date=start_date,
    end_date=end_date,
    data_types=list(data_types) if data_types else None,
)
level_field = LEVEL_TO_FIELD.get("creative", "creative_id")
filters.append({"terms": {level_field: entity_ids}})

print(f"\nFinal filters: {len(filters)} filters")
for i, f in enumerate(filters):
    print(f"  [{i}]: {f}")

# Execute query
dsl = {
    "query": {
        "bool": {
            "filter": filters,
        },
    },
    "size": 0,
}
response = es.search(index="ad_stat_data", body=dsl)
doc_count = response["hits"]["total"]["value"]
print(f"\nFINAL DOC COUNT = {doc_count}")
