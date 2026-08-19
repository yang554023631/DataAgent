#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.dsl_templates.common import build_common_filters, get_data_type

es = Elasticsearch(["http://localhost:9200"])

# Build the same query that EmptyResultChecker builds for case 52
metrics = ["conversions", "impressions", "cost", "cvr", "clicks"]
data_types = set()
for metric in metrics:
    dt = get_data_type(metric)
    if dt is not None:
        data_types.add(dt)

print(f"Metrics: {metrics}")
print(f"data_types: {list(data_types)}")

filters = build_common_filters(
    advertiser_ids=["6"],
    start_date="2000-01-01",
    end_date="2026-08-17",
    data_types=list(data_types),
)

# Get 80 creative_ids from dimension table
must = [{"terms": {"advertiser_id": [6]}}]
dsl_dim = {
    "query": {"bool": {"must": must}},
    "size": 200,
}
resp_dim = es.search(index="creative", body=dsl_dim)
entity_ids = [hit["_source"]["creative_id"] for hit in resp_dim["hits"]["hits"]]
print(f"\nGot {len(entity_ids)} creative_ids")

from src.nl_dsl.dsl_templates.common import LEVEL_TO_FIELD
level_field = LEVEL_TO_FIELD.get("creative", f"creative_id")
filters.append({"terms": {level_field: entity_ids}})

dsl = {
    "query": {
        "bool": {
            "filter": filters,
        },
    },
    "size": 0,
}

print(f"\nFinal DSL filters:")
for f in filters:
    print(f"  {f}")

response = es.search(index="ad_stat_data", body=dsl)
doc_count = response["hits"]["total"]["value"]
print(f"\nDoc count: {doc_count}")
