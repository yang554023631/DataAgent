#!/usr/bin/env python3
import sys
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# First find creative_ids with 'mini' in name on advertiser 6
must = [
    {"terms": {"advertiser_id": [6]}},
    {"wildcard": {"creative_name": "*mini*"}}
]

dsl = {
    "query": {"bool": {"must": must}},
    "size": 10,
}

response = es.search(index="creative", body=dsl)
print(f"Total creative matching name: {response['hits']['total']['value']}")
print()
total_with_data = 0
for hit in response["hits"]["hits"]:
    source = hit["_source"]
    cid = source.get('creative_id')
    name = source.get('creative_name')
    print(f"creative_id={cid}, name={name}")

    # Check fact table
    dsl_fact = {
        "query": {"bool": {"filter": [
            {"terms": {"advertiser_id": [6]}},
            {"terms": {"creative_id": [cid]}}
        ]}},
        "size": 0
    }
    fact_resp = es.search(index="ad_stat_data", body=dsl_fact)
    fact_count = fact_resp['hits']['total']['value']
    print(f"  → Fact table docs: {fact_count}")
    if fact_count > 0:
        total_with_data += 1

print(f"\nTotal creatives with fact data: {total_with_data}")
