#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Case 9: 找出 digital_0 名称带 digital 的广告计划，advertiser 6
must_clauses = [
    {"terms": {"advertiser_id": [6]}},
    {"wildcard": {"campaign_name": "*digital*"}}
]

dsl = {
    "query": {"bool": {"must": must_clauses}},
    "size": 1000,
}

print("Querying campaign index for advertiser=6 AND campaign_name like '*digital*':")
response = es.search(index="campaign", body=dsl)

print(f"Total hits: {response['hits']['total']['value']}")
print()
for hit in response["hits"]["hits"]:
    source = hit["_source"]
    print(f"  campaign_id={source.get('campaign_id')}, campaign_name={source.get('campaign_name')}, advertiser_id={source.get('advertiser_id')}")
