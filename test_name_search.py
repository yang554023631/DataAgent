#!/usr/bin/env python3
from elasticsearch import Elasticsearch
from typing import List

es_client = Elasticsearch(["http://localhost:9200"])

# Test case 1: 找出 digital_0 名称带 digital 的广告计划
# advertiser_ids = ["6"]
# field = "campaign_name"
# value = "digital"

advertiser_ids = ["6"]
field = "campaign_name"
value = "digital"
dim_index = "campaign"

query = {
    "bool": {
        "must": [
            {"wildcard": {field: f"*{value}*"}}
        ] + (
            [{"terms": {"advertiser_id": [int(aid) for aid in advertiser_ids]}}]
                if advertiser_ids else []
        )
    }
}

print(f"Testing query on index {dim_index}:")
print(f"Query: {query}")
print()

result = es_client.search(index=dim_index, query=query, size=1000)

hits = result["hits"]["hits"]
print(f"Total hits: {result['hits']['total']['value']}")
print()

matched_ids = []
for hit in hits:
    eid = hit["_source"].get("campaign_id")
    name = hit["_source"].get("campaign_name")
    matched_ids.append(int(eid))
    print(f"  Hit: campaign_id={eid}, campaign_name='{name}'")

print()
print(f"Extracted matched_ids: {matched_ids}")

# Now check fact table ad_stat_data
if matched_ids:
    print()
    print(f"Checking fact table ad_stat_data with campaign_ids: {matched_ids}")
    fact_query = {
        "bool": {
            "must": [
                {"terms": {"campaign_id": matched_ids}},
                {"terms": {"advertiser_id": [int(aid) for aid in advertiser_ids]}},
                {"range": {"data_date": {"gte": "2000-01-01", "lte": "2026-08-16"}}}
            ]
        }
    }
    fact_result = es_client.search(index="ad_stat_data", query=fact_query, size=10)
    print(f"Fact table hits: {fact_result['hits']['total']['value']}")
    for hit in fact_result["hits"]["hits"]:
        print(f"  Fact hit: {hit['_source']}")
