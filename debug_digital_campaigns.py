#!/usr/bin/env python3
import sys
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Find ALL campaigns on advertiser 6 that have 'digital' in name
must = [
    {"terms": {"advertiser_id": [6]}},
    {"wildcard": {"campaign_name": "*digital*"}}
]

dsl = {
    "query": {"bool": {"must": must}},
    "size": 10,
}

response = es.search(index="campaign", body=dsl)
print(f"Total campaigns matching: {response['hits']['total']['value']}")
print()
for hit in response["hits"]["hits"]:
    source = hit["_source"]
    cid = source.get("campaign_id")
    name = source.get("campaign_name")
    print(f"  campaign_id={cid}, name={name}")
