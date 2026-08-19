#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Check adgroup dimension table
mapping = es.indices.get_mapping(index="adgroup")
properties = mapping["adgroup"]["mappings"]["properties"]
print("Fields in adgroup dimension index:")
for field in properties:
    print(f"  - {field}: {properties[field].get('type', 'no type')}")

# Get one sample
print("\nSample document from adgroup:")
sample = es.search(index="adgroup", body={"size": 1})
hits = sample.get("hits", {}).get("hits", [])
if hits:
    source = hits[0]["_source"]
    for key, value in source.items():
        print(f"  {key}: {repr(value)}")
