#!/usr/bin/env python3
"""检查广告主6是否有任何数据，以及日期分布"""

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

# 检查整个时间范围
print("=== 检查广告主6的所有数据时间分布 ===\n")
query = {
    "size": 0,
    "query": {
        "bool": {
            "filter": [
                {"terms": {"advertiser_id.keyword": [6]}}
            ]
        }
    },
    "aggs": {
        "by_month": {
            "date_histogram": {"field": "data_date", "calendar_interval": "month"},
            "aggs": {"total_cost": {"sum": {"field": "data_value"}}}
        }
    }
}

result = es.search(index="ad_stat_data", body=query)
buckets = result["aggregations"]["by_month"]["buckets"]
print("按月分布:")
has_data = False
for bucket in buckets:
    val = bucket["total_cost"]["value"]
    date = bucket["key_as_string"][:7]
    doc_count = bucket["doc_count"]
    print(f"  {date}: doc_count={doc_count}, 总消耗={val:.2f}")
    if doc_count > 0:
        has_data = True

print()

# 检查 campaign 维度表 - 包括已删除的
print("=== 检查 campaign 维度表 - 包括已删除 ===\n")
query = {
    "query": {
        "bool": {
            "filter": [
                {"terms": {"advertiser_id.keyword": [6]}}
            ]
        }
    },
    "size": 100
}

result = es.search(index="campaign", body=query)
hits = result["hits"]["hits"]
print(f"总共找到 {len(hits)} 个广告计划:\n")
for hit in hits:
    source = hit["_source"]
    print(f"  - campaign_id={source.get('campaign_id')}, name={source.get('campaign_name')}, is_deleted={source.get('is_deleted')}")

print()

# 检查 adgroup 维度表
print("=== 检查 adgroup 维度表 ===\n")
query = {
    "query": {
        "bool": {
            "filter": [
                {"terms": {"advertiser_id.keyword": [6]}}
            ]
        }
    },
    "size": 100
}

result = es.search(index="adgroup", body=query)
hits = result["hits"]["hits"]
print(f"总共找到 {len(hits)} 个广告组:\n")
for hit in hits:
    source = hit["_source"]
    print(f"  - adgroup_id={source.get('ad_group_id')}, name={source.get('ad_group_name')}, is_deleted={source.get('is_deleted')}")

print()

# 检查 creative 维度表
print("=== 检查 creative 维度表 ===\n")
query = {
    "query": {
        "bool": {
            "filter": [
                {"terms": {"advertiser_id.keyword": [6]}}
            ]
        }
    },
    "size": 100
}

result = es.search(index="creative", body=query)
hits = result["hits"]["hits"]
print(f"总共找到 {len(hits)} 个创意:\n")
for hit in hits:
    source = hit["_source"]
    print(f"  - creative_id={source.get('creative_id')}, name={source.get('creative_name')}, is_deleted={source.get('is_deleted')}")
