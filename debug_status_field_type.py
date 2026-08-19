#!/usr/bin/env python3
import sys
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Get mapping of campaign index
mapping = es.indices.get_mapping(index="campaign")
props = mapping['campaign']['mappings']['properties']
print("campaign index mapping:")
if 'status' in props:
    print(f"  status: {props['status']}")
print()
if 'campaign_name' in props:
    print(f"  campaign_name: {props['campaign_name']}")
if 'advertiser_id' in props:
    print(f"  advertiser_id: {props['advertiser_id']}")
if 'campaign_id' in props:
    print(f"  campaign_id: {props['campaign_id']}")
