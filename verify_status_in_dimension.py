#!/usr/bin/env python3
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Check campaign dimension table for campaign_id=13 status
query = {
    "bool": {
        "must": [
            {"term": {"campaign_id": 13}}
        ]
    }
}
result = es.search(index="campaign", query=query, size=5)
print(f"Found {result['hits']['total']['value']} docs in campaign dimension table")
if result['hits']['hits']:
    source = result['hits']['hits'][0]['_source']
    print(f"Source fields: {list(source.keys())}")
    print(f"status: {source.get('status')}")
    print(f"campaign_name: {source.get('campaign_name')}")
    print(f"advertiser_id: {source.get('advertiser_id')}")
