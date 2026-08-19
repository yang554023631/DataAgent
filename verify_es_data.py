#!/usr/bin/env python3
"""验证广告主6在4月份是否有数据"""

import os
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

ES_URL = os.getenv("ES_URL")
ES_USER = os.getenv("ES_USER")
ES_PASSWORD = os.getenv("ES_PASSWORD")

if ES_USER and ES_PASSWORD:
    es = Elasticsearch(ES_URL, basic_auth=(ES_USER, ES_PASSWORD))
else:
    es = Elasticsearch(ES_URL)

# 测试1: 广告主6 4月份 消耗趋势
print("=== 测试1: 广告主6 4月份消耗趋势 ===")
query = {
    "query": {
        "bool": {
            "filter": [
                {"terms": {"advertiser_id.keyword": [6]}},
                {"range": {"data_date": {"gte": "2026-04-01", "lte": "2026-04-30"}}}
            ]
        }
    },
    "size": 0,
    "aggs": {
        "by_date": {
            "date_histogram": {"field": "data_date", "calendar_interval": "day"},
            "aggs": {"total_cost": {"sum": {"field": "data_value"}}}
        }
    }
}

result = es.search(index="ad_stat_data", body=query)
buckets = result["aggregations"]["by_date"]["buckets"]
print(f"总天数: {len(buckets)}")
for bucket in buckets:
    val = bucket["total_cost"]["value"]
    if val > 0:
        print(f"  {bucket['key_as_string'][:10]}: {val:.2f}")

total_doc = result["hits"]["total"]["value"]
print(f"总文档数: {total_doc}")
print()

# 测试2: 广告主6 dimension table 中未删除的广告计划
print("=== 测试2: 广告主6 维度表 未删除的广告计划 ===")
query = {
    "query": {
        "bool": {
            "filter": [
                {"terms": {"advertiser_id.keyword": [6]}},
                {"term": {"is_deleted": False}}
            ]
        }
    },
    "size": 100
}

result = es.search(index="campaign", body=query)
hits = result["hits"]["hits"]
print(f"找到 {len(hits)} 个未删除的广告计划:")
for hit in hits:
    source = hit["_source"]
    print(f"  - {source.get('campaign_id')}: {source.get('campaign_name')}")
print()

# 测试3: 广告主6 4月份消耗 > 10 的广告计划
print("=== 测试3: 广告主6 4月份消耗 > 10 的广告计划 ===")
query = {
    "size": 0,
    "query": {
        "bool": {
            "filter": [
                {"terms": {"advertiser_id.keyword": [6]}},
                {"range": {"data_date": {"gte": "2026-04-01", "lte": "2026-04-30"}}}
            ]
        }
    },
    "aggs": {
        "by_campaign": {
            "terms": {"field": "campaign_id.keyword", "size": 1000},
            "aggs": {"total_cost": {"sum": {"field": "data_value"}}}
        }
    }
}

result = es.search(index="ad_stat_data", body=query)
buckets = result["aggregations"]["by_campaign"]["buckets"]
count_gt_10 = sum(1 for b in buckets if b["total_cost"]["value"] > 10)
print(f"广告计划总数: {len(buckets)}")
print(f"消耗 > 10 的广告计划数: {count_gt_10}")
for bucket in buckets:
    val = bucket["total_cost"]["value"]
    if val > 10:
        print(f"  - campaign_id={bucket['key']}: 消耗={val:.2f}")
