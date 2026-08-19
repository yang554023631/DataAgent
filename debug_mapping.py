#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Get mapping
mapping = es.indices.get_mapping(index="ad_stat_data")
properties = mapping["ad_stat_data"]["mappings"]["properties"]
print("Fields in ad_stat_data:")
for field in properties:
    print(f"  - {field}: {properties[field].get('type', 'no type')}")

print("\nGet one sample document:")
sample = es.search(index="ad_stat_data", body={"size": 1, "query": {"term": {"advertiser_id": 6}}})
hits = sample.get("hits", {}).get("hits", [])
if hits:
    source = hits[0]["_source"]
    print("\nSample document fields:")
    for key, value in source.items():
        print(f"  {key}: {repr(value)[:60]}")
