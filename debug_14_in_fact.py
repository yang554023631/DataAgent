#!/usr/bin/env python3
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Check fact table for campaign_id=14, any advertiser_id
query1 = {
    "query": {
        "bool": {
            "must": [{"terms": {"campaign_id": [14]}}]
        }
    },
    "size": 5
}

result1 = es.search(index="ad_stat_data", query=query1["query"])
print(f"With just campaign_id=14: total={result1['hits']['total']['value']}")
if result1['hits']['hits']:
    print(f"First hit: {result1['hits']['hits'][0]['_source']}")

print()

# Check campaign dimension for campaign_id=14
query2 = {
    "query": {
        "bool": {
            "must": [{"term": {"campaign_id": 14}}]
        }
    }
}
result2 = es.search(index="campaign", query=query2["query"])
print(f"In dimension table campaign: total={result2['hits']['total']['value']}")
if result2['hits']['hits']:
    source = result2['hits']['hits'][0]['_source']
    print(f"  campaign_name: {source.get('campaign_name')}")
    print(f"  advertiser_id: {source.get('advertiser_id')}")
    print(f"  status: {source.get('status')}")
