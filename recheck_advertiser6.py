#!/usr/bin/env python3
"""重新检查广告主6的数据，修复字段类型错误"""

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

# 1. 检查 advertiser 维度表中是否有广告主6
print("=== 1. 检查 advertiser 维度表 ===\n")
query = {
    "query": {
        "term": {"advertiser_id": 6}
    },
    "size": 10
}
result = es.search(index="advertiser", body=query)
hits = result["hits"]["hits"]
print(f"找到 {len(hits)} 个文档:\n")
for hit in hits:
    source = hit["_source"]
    print(f"advertiser_id={source.get('advertiser_id')}, name={source.get('advertiser_name')}")
print()

# 2. 检查整个时间范围分布
print("=== 2. ad_stat_data 中广告主6的时间分布 ===\n")
query = {
    "size": 0,
    "query": {
        "term": {"advertiser_id": 6}
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
print(f"按月分布:\n")
has_data = False
for bucket in buckets:
    val = bucket["total_cost"]["value"]
    date = bucket["key_as_string"][:7]
    doc_count = bucket["doc_count"]
    print(f"  {date}: doc_count={doc_count}, 总消耗={val:.2f}")
    if doc_count > 0:
        has_data = True
print()

# 3. 检查 4月份具体数据
print("=== 3. 广告主6 4月份具体数据 ===\n")
query = {
    "size": 0,
    "query": {
        "bool": {
            "filter": [
                {"term": {"advertiser_id": 6}},
                {"range": {"data_date": {"gte": "2026-04-01", "lte": "2026-04-30"}}}
            ]
        }
    },
    "aggs": {
        "by_campaign": {
            "terms": {"field": "campaign_id", "size": 100},
            "aggs": {"total_cost": {"sum": {"field": "data_value"}}}
        }
    }
}

result = es.search(index="ad_stat_data", body=query)
buckets = result["aggregations"]["by_campaign"]["buckets"]
print(f"广告计划数: {len(buckets)}\n")
if buckets:
    print(f"  campaign_id | 总消耗")
    print(f"  ----------|-------")
    for bucket in buckets:
        print(f"  {bucket['key']:>10d} | {bucket['total_cost']['value']:.2f}")
print()

# 4. 检查 campaign 维度表
print("=== 4. campaign 维度表中广告主6的广告计划 ===\n")
query = {
    "query": {
        "term": {"advertiser_id": 6}
    },
    "size": 100
}
result = es.search(index="campaign", body=query)
hits = result["hits"]["hits"]
print(f"找到 {len(hits)} 个广告计划:\n")
for hit in hits:
    source = hit["_source"]
    print(f"  - campaign_id={source.get('campaign_id')}, name={source.get('campaign_name')}, is_deleted={source.get('is_deleted')}")
print()

# 5. 检查 adgroup 维度表
print("=== 5. adgroup 维度表中广告主6的广告组 ===\n")
query = {
    "query": {
        "term": {"advertiser_id": 6}
    },
    "size": 100
}
result = es.search(index="adgroup", body=query)
hits = result["hits"]["hits"]
print(f"找到 {len(hits)} 个广告组:\n")
for hit in hits:
    source = hit["_source"]
    print(f"  - adgroup_id={source.get('ad_group_id')}, name={source.get('ad_group_name')}, is_deleted={source.get('is_deleted')}")
print()

# 6. 检查 creative 维度表
print("=== 6. creative 维度表中广告主6的创意 ===\n")
query = {
    "query": {
        "term": {"advertiser_id": 6}
    },
    "size": 100
}
result = es.search(index="creative", body=query)
hits = result["hits"]["hits"]
print(f"找到 {len(hits)} 个创意:\n")
for hit in hits:
    source = hit["_source"]
    print(f"  - creative_id={source.get('creative_id')}, name={source.get('creative_name')}, is_deleted={source.get('is_deleted')}")
