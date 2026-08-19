#!/usr/bin/env python3
"""验证为什么广告主6的entity_table查询返回空"""

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

print("=== 测试1: campaign维度表 - 广告主6所有未删除的campaign ===\n")
# 查询campaign维度表
query = {
    "query": {
        "bool": {
            "filter": [
                {"term": {"advertiser_id": 6}},
                {"term": {"is_deleted": 0}}
            ]
        }
    },
    "size": 100
}

result = es.search(index="campaign", body=query)
hits = result["hits"]["hits"]
print(f"找到 {len(hits)} 个campaign:\n")
for hit in hits:
    source = hit["_source"]
    print(f"  - campaign_id={source.get('campaign_id')}, name={source.get('campaign_name')}, is_deleted={source.get('is_deleted')}")

print("\n=== 测试2: ad_stat_data - 广告主6 4月份 按campaign聚合消耗 ===\n")
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
            "aggs": {
                "total_cost": {"sum": {"field": "cost"}},
                "total_clicks": {"sum": {"field": "clicks"}}
            }
        }
    }
}

result = es.search(index="ad_stat_data", body=query)
buckets = result["aggregations"]["by_campaign"]["buckets"]
print(f"找到 {len(buckets)} 个campaign有数据:\n")
print(f"  campaign_id | 总消耗 | 总点击")
print(f"  ----------|-------|-------")
for bucket in buckets:
    print(f"  {bucket['key']:>10d} | {bucket['total_cost']['value']:.2f} | {int(bucket['total_clicks']['value'])}")

total_cost = sum(b['total_cost']['value'] for b in buckets)
total_clicks = sum(int(b['total_clicks']['value']) for b in buckets)
print(f"\n  总计: {total_cost:.2f} | {total_clicks}")

print("\n=== 测试3: adgroup维度表 - 广告主6所有adgroup ===\n")
query = {
    "query": {
        "bool": {
            "filter": [
                {"term": {"advertiser_id": 6}},
                {"term": {"is_deleted": 0}}
            ]
        }
    },
    "size": 100
}

result = es.search(index="adgroup", body=query)
hits = result["hits"]["hits"]
print(f"找到 {len(hits)} 个未删除的adgroup\n")
if len(hits) > 0:
    print(f"前5个:")
    for hit in hits[:5]:
        source = hit["_source"]
        print(f"  - adgroup_id={source.get('ad_group_id')}, name={source.get('ad_group_name')}")

print("\n=== 测试4: 检查entity_table查询DSL ===\n")
print("我们来模拟系统实际会生成的查询:\n")
print("对于 entity_table 查询广告主6层级，应该直接从 advertiser 维度表 join 事实数据聚合\n")

query = {
    "size": 10,
    "query": {
        "bool": {
            "filter": [
                {"term": {"advertiser_id": 6}}
            ]
        }
    }
}

result = es.search(index="advertiser", body=query)
hits = result["hits"]["hits"]
print(f"advertiser 维度表找到 {len(hits)} 条记录:\n")
for hit in hits:
    print(f"  {hit['_source']}")
