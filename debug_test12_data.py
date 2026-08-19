#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Query: 在 digital_0 campaign 中找 adgroup name contains "六一八"
# 第一步：先找 campaign_id for digital_0
print("Finding campaign_id where campaign_name contains 'digital_0' in advertiser 6...")

query = {
    "query": {
        "bool": {
            "must": [
                {"wildcard": {"campaign_name": "*digital_0*"}},
                {"term": {"advertiser_id": 6}}
            ]
        }
    },
    "size": 10
}

result = es.search(index="campaign", body=query)
hits = result["hits"]["hits"]
print(f"Found {len(hits)} campaigns matching 'digital_0' in advertiser 6:")
for hit in hits:
    print(f"  campaign_id: {hit['_source']['campaign_id']}, name: {hit['_source']['campaign_name']}")

if hits:
    # Now find adgroups in those campaigns where name contains "六一八"
    campaign_ids = [hit["_source"]["campaign_id"] for hit in hits]
    print(f"\nFinding adgroups in these campaigns ({campaign_ids}) where name contains '六一八'...")

    query = {
        "query": {
            "bool": {
                "must": [
                    {"wildcard": {"ad_group_name": "*六一八*"}},
                    {"terms": {"campaign_id": campaign_ids}}
                ]
            }
        },
        "size": 10
    }

    result = es.search(index="adgroup", body=query)
    hits = result["hits"]["hits"]
    print(f"Found {len(hits)} adgroups:")
    for hit in hits:
        print(f"  ad_group_id: {hit['_source']['ad_group_id']}, name: {hit['_source']['ad_group_name']}")
