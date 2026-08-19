#!/usr/bin/env python3
"""检查ad_stat_data中广告主6的cost字段到底有没有非零值"""

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

print("=== 检查广告主6 4月份 ad_stat_data 中 cost 字段是否有非零值 ===\n")

# 抽样查看几条文档
query = {
    "query": {
        "bool": {
            "filter": [
                {"term": {"advertiser_id": 6}},
                {"range": {"data_date": {"gte": "2026-04-01", "lte": "2026-04-30"}}}
            ]
        }
    },
    "size": 20
}

result = es.search(index="ad_stat_data", body=query)
hits = result["hits"]["hits"]

print(f"总共返回 {len(hits)} 条样本:\n")
print(f"  doc_id | campaign_id | adgroup_id | cost | clicks | impressions | conversions")
print(f"  ------|------------|-----------|------|-------|-----------|-----------")

non_zero_cost = 0
total_cost = 0
for hit in hits:
    source = hit["_source"]
    doc_id = hit["_id"][:8]
    cid = source.get("campaign_id", "N/A")
    aid = source.get("ad_group_id", "N/A")
    cost = source.get("cost", 0)
    clicks = source.get("clicks", 0)
    impr = source.get("impressions", 0)
    conv = source.get("conversions", 0)
    print(f"  {doc_id} | {cid:10d} | {aid:9d} | {cost:.2f} | {clicks:5d} | {impr:9d} | {conv:6d}")
    if cost > 0:
        non_zero_cost += 1
    total_cost += cost

print(f"\n=== 统计 ===\n")
print(f"样本条数: {len(hits)}")
print(f"非零cost条数: {non_zero_cost}")
print(f"样本总cost: {total_cost:.2f}")

# 全量聚合
print(f"\n=== 全量聚合 ===\n")
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
        "total_cost": {"sum": {"field": "cost"}},
        "total_clicks": {"sum": {"field": "clicks"}},
        "total_impressions": {"sum": {"field": "impressions"}},
        "total_conversions": {"sum": {"field": "conversions"}},
        "doc_count": {"value_count": {"field": "_id"}}
    }
}

result = es.search(index="ad_stat_data", body=query)
aggs = result["aggregations"]
print(f"总文档数: {int(aggs['doc_count']['value'])}")
print(f"总cost: {aggs['total_cost']['value']:.2f}")
print(f"总clicks: {int(aggs['total_clicks']['value'])}")
print(f"总impressions: {int(aggs['total_impressions']['value'])}")
print(f"总conversions: {int(aggs['total_conversions']['value'])}")

# 按campaign聚合
print(f"\n=== 按campaign聚合 ===\n")
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
print(f"campaign_id | 文档数 | 总cost | 总clicks")
print(f"-----------|--------|--------|---------")
for bucket in buckets:
    print(f" {bucket['key']:>10d} | {bucket['doc_count']:>6d} | {bucket['total_cost']['value']:>6.2f} | {int(bucket['total_clicks']['value']):>7d}")
