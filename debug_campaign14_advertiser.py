#!/usr/bin/env python3
import sys
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Get full source of campaign 14
dsl = {
  "query": {"term": {"campaign_id": 14}},
  "size": 1
}

response = es.search(index="campaign", body=dsl)
if response["hits"]["total"]["value"] > 0:
    source = response["hits"]["hits"][0]["_source"]
    print("Full source for campaign 14:")
    for k, v in source.items():
        print(f"  {k}: {v}")
