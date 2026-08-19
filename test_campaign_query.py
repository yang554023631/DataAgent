#!/usr/bin/env python3
import os
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()

ES_URL = os.getenv("ES_URL")
ES_USER = os.getenv("ES_USER")
ES_PASSWORD = os.getenv("ES_PASSWORD")

if ES_USER and ES_PASSWORD:
    es = Elasticsearch(ES_URL, basic_auth=(ES_USER, ES_PASSWORD))
else:
    es = Elasticsearch(ES_URL)

# 测试查询: 广告主6下未删除的广告计划
query = {
    "query": {
        "bool": {
            "filter": [
                {"terms": {"advertiser_id": [6]}},
                {"term": {"is_deleted": 0}}
            ]
        }
    },
    "size": 100
}

print("Testing query:")
print(query)

try:
    result = es.search(index="campaign", body=query)
    hits = result["hits"]["hits"]
    print(f"\nFound {len(hits)} hits:")
    for hit in hits:
        print(f"  {hit['_source']}")
except Exception as e:
    print(f"\nError: {e}")
