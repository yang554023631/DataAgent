#!/usr/bin/env python3
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Find all campaigns for advertiser 6 with name containing 'digital' anywhere
query = {
    "bool": {
        "must": [
            {"terms": {"advertiser_id": [6]}},
            {"wildcard": {"campaign_name": "*digital*"}}
        ]
    }
}

result = es.search(index="campaign", query=query, size=100)
print(f"Found {result['hits']['total']['value']} campaigns with 'digital' in name:")
for hit in result['hits']['hits']:
    source = hit['_source']
    cid = source['campaign_id']
    name = source['campaign_name']
    status = source['status']
    print(f"  campaign_id={cid:3d}: name='{name}', status={status}")

print("\nChecking fact table for all:")
for hit in result['hits']['hits']:
    cid = int(hit['_source']['campaign_id'])
    query_fact = {
        "bool": {
            "must": [
                {"terms": {"advertiser_id": [6]}},
                {"terms": {"campaign_id": [cid]}}
            ]
        }
    }
    result_fact = es.search(index="ad_stat_data", query=query_fact, size=0)
    total = result_fact['hits']['total']['value']
    if total > 0:
        print(f"✅ campaign_id={cid}: {total} rows in fact table")
    else:
        print(f"❌ campaign_id={cid}: 0 rows in fact table")
