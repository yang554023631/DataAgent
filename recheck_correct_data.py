#!/usr/bin/env python3
"""正确查询ad_stat_data（长表结构）"""

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

print("=== 广告主6 4月份 正确查询（按data_type分组聚合） ===\n")

# 按data_type分组聚合
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
        "by_data_type": {
            "terms": {"field": "data_type", "size": 10},
            "aggs": {"total_value": {"sum": {"field": "data_value"}}}
        }
    }
}

result = es.search(index="ad_stat_data", body=query)
buckets = result["aggregations"]["by_data_type"]["buckets"]

type_map = {
    1: "曝光 (impressions)",
    2: "点击 (clicks)",
    3: "消耗 (cost)",
    4: "转化 (conversions)",
    5: "触达 (reach)",
    6: "频次 (frequency)",
}

total_docs = sum(b["doc_count"] for b in buckets)
print(f"总文档数: {total_docs}\n")
print(f"data_type | 指标名称 | 文档数 | 总和")
print(f"---------|----------|--------|-----")
for bucket in buckets:
    dtype = int(bucket["key"])
    name = type_map.get(dtype, f"未知({dtype})")
    docs = bucket["doc_count"]
    total = bucket["total_value"]["value"]
    print(f" {dtype:>8} | {name:10} | {docs:>6d} | {total:.2f}")

print("\n=== 按campaign + data_type 聚合消耗 ===\n")

# 按campaign聚合消耗（data_type=3）
query = {
    "size": 0,
    "query": {
        "bool": {
            "filter": [
                {"term": {"advertiser_id": 6}},
                {"term": {"data_type": 3}},  # 消耗
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

print(f"campaign_id | 文档数 | 总消耗")
print(f"-----------|--------|-------")
total_cost_all = 0
for bucket in buckets:
    cid = int(bucket["key"])
    docs = bucket["doc_count"]
    cost = bucket["total_cost"]["value"]
    total_cost_all += cost
    print(f" {cid:>10d} | {docs:>6d} | {cost:.2f}")

print(f"-----------|--------|-------")
print(f" **总计**  |        | {total_cost_all:.2f}")

print(f"\n=== 消耗 > 10 的campaign ===\n")
gt_10 = [b for b in buckets if b["total_cost"]["value"] > 10]
if gt_10:
    print(f"找到 {len(gt_10)} 个消耗 > 10 的campaign:")
    for bucket in gt_10:
        print(f"  - campaign_id={bucket['key']}, 消耗={bucket['total_cost']['value']:.2f}")
else:
    print(f"没有消耗 > 10 的campaign")

print("\n=== 检查广告主层级 entity_table 应该返回什么 ===\n")
# 广告主层级entity_table查询：应该一行，四个指标分别聚合
for dtype, name in [(1, "impressions"), (2, "clicks"), (3, "cost"), (4, "conversions")]:
    query = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"advertiser_id": 6}},
                    {"term": {"data_type": dtype}},
                    {"range": {"data_date": {"gte": "2026-04-01", "lte": "2026-04-30"}}}
                ]
            }
        },
        "aggs": {"total": {"sum": {"field": "data_value"}}
        }
    }
    result = es.search(index="ad_stat_data", body=query)
    total = result["aggregations"]["total"]["value"]
    print(f"  {name}: {total:.2f}")
