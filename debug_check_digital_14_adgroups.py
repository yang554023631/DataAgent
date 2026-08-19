#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Check adgroups in campaign 14 (digital_837_pbp89)
print("Finding adgroups in campaign 14 (advertiser 6)...")
query = {
    "query": {
        "bool": {
            "must": [
                {"term": {"campaign_id": 14}},
                {"term": {"advertiser_id": 6}}
            ]
        }
    },
    "size": 100
}

result = es.search(index="adgroup", body=query)
hits = result["hits"]["hits"]
print(f"Found {len(hits)} adgroups:")
for hit in hits:
    source = hit["_source"]
    name = source.get("ad_group_name", "unknown")
    print(f"  ad_group_id: {source.get('ad_group_id')}, name: {name}")

# Check if any contain "六一八"
print("\nAdgroup names containing '六一八':")
count = 0
for hit in hits:
    source = hit["_source"]
    name = source.get("ad_group_name", "")
    if "六一八" in name:
        count += 1
        print(f"  - {name} (id={source.get('ad_group_id')})")

print(f"\nTotal found: {count}")
