#!/usr/bin/env python3
import sys
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Let's manually query the same way and see what we get
filters = [
    {"terms": {"advertiser_id": [6]}},
    {"range": {"data_date": {"gte": "2000-01-01", "lte": "2026-08-17"}}},
    {"terms": {"data_type": [1, 2, 3, 4]}},
]

dsl = {
    "query": {"bool": {"filter": filters}},
    "size": 0,
}
print("Without creative_id filter:")
resp = es.search(index="ad_stat_data", body=dsl)
print(f"  doc_count = {resp['hits']['total']['value']}")

# Now with all 80 creative_ids
print("\nGetting all creative_ids from creative dimension table...")
must = [{"terms": {"advertiser_id": [6]}}]
resp_dim = es.search(index="creative", body={
    "query": {"bool": {"must": must}},
    "size": 200,
})
creative_ids = [hit["_source"]["creative_id"] for hit in resp_dim["hits"]["hits"]]
print(f"  got {len(creative_ids)} creative_ids")

filters.append({"terms": {"creative_id": creative_ids}})
dsl = {
    "query": {"bool": {"filter": filters}},
    "size": 0,
}
print("\nWith creative_id filter (exact same as EmptyResultChecker does it):")
resp_final = es.search(index="ad_stat_data", body=dsl)
doc_count = resp_final["hits"]["total"]["value"]
print(f"  doc_count = {doc_count}")
