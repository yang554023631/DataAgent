#!/usr/bin/env python3
import sys
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

mapping = es.indices.get_mapping(index="ad_stat_data")
props = mapping['ad_stat_data']['mappings']['properties']
print("ad_stat_data mapping key fields:")
for key in sorted(props.keys()):
    if key.endswith('_id'):
        print(f"  {key}: {props[key]}")
