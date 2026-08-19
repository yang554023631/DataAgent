#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Search entire campaign index for digital_0
print("Searching all campaigns for 'digital_0'...")
query = {
    "query": {
        "wildcard": {"campaign_name": "*digital*"}
    },
    "size": 20
}
result = es.search(index="campaign", body=query)
hits = result["hits"]["hits"]
print(f"Found {len(hits)} campaigns containing 'digital':")
for hit in hits:
    source = hit["_source"]
    print(f"  advertiser_id: {source.get('advertiser_id')}, campaign_id: {source.get('campaign_id')}, name: {source.get('campaign_name')}")
