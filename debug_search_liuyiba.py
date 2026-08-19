#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Search all adgroups for "六一八"
print("Searching all adgroups for '六一八'...")
query = {
    "query": {
        "wildcard": {"ad_group_name": "*六一八*"}
    },
    "size": 20
}
result = es.search(index="adgroup", body=query)
hits = result["hits"]["hits"]
print(f"Found {len(hits)} adgroups:")
for hit in hits:
    source = hit["_source"]
    print(f"  advertiser_id: {source.get('advertiser_id')}, campaign_id: {source.get('campaign_id')}, id: {source.get('ad_group_id')}, name: {source.get('ad_group_name')}")
