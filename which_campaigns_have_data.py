#!/usr/bin/env python3
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Get all campaign_ids from dimension table for advertiser 6 that have 'digital' in name
query_dim = {
    "bool": {
        "must": [
            {"terms": {"advertiser_id": [6]}},
            {"wildcard": {"campaign_name": "*digital*"}}
        ]
    }
}
result_dim = es.search(index="campaign", query=query_dim, size=100)
campaign_ids = []
for hit in result_dim['hits']['hits']:
    cid = hit['_source']['campaign_id']
    campaign_ids.append(int(cid))
    print(f"Dimension: campaign_id={cid}, name={hit['_source']['campaign_name']}")

print()
print("Checking fact table...")
# Check fact table for each
for cid in campaign_ids:
    query_fact = {
        "query": {
            "bool": {
                "must": [
                    {"terms": {"advertiser_id": [6]}},
                    {"terms": {"campaign_id": [cid]}}
                ]
            }
        }
    }
    result_fact = es.search(index="ad_stat_data", query=query_fact["query"], size=0)
    total = result_fact['hits']['total']['value']
    if total > 0:
        print(f"✅ campaign_id={cid}: {total} rows in fact table")
    else:
        print(f"❌ campaign_id={cid}: 0 rows in fact table")
