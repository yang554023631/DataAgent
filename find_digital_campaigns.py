#!/usr/bin/env python3
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Find all campaigns for advertiser 6 with name containing 'digital'
query = {
    "bool": {
        "must": [
            {"terms": {"advertiser_id": [6]}},
            {"wildcard": {"campaign_name": "*digital*"}}
        ]
    }
}

result = es.search(index="campaign", query=query, size=100)
print(f"Found {result['hits']['total']['value']} campaigns:")
for hit in result['hits']['hits']:
    source = hit['_source']
    cid = source['campaign_id']
    name = source['campaign_name']
    status = source['status']
    print(f"  campaign_id={cid:2d}: name='{name}', status={status}")
