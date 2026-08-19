#!/usr/bin/env python3
"""检查 ID 60 测试条件修改后是否有数据"""

import os
import sys
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()

ES_URL = os.getenv("ES_URL")
es = Elasticsearch(ES_URL)

INDEX = "ad_stat_data"
ADVERTISER_ID = "6"
START_DATE = "2026-04-01"
END_DATE = "2026-04-30"

print(f"🔍 查询广告主 {ADVERTISER_ID} 四月份数据...")
print(f"   条件: conversions > 1, cvr > 0.01")

# 先找出所有 creative_id 在四月份
query = {
    "size": 0,
    "query": {
        "bool": {
            "filter": [
                {"terms": {"advertiser_id": [int(ADVERTISER_ID)]}},
                {"terms": {"data_type": [1]}},
                {"range": {"data_date": {"gte": START_DATE, "lte": END_DATE}}}
            ]
        }
    },
    "aggs": {
        "creative_ids": {
            "terms": {"field": "creative_id", "size": 1000},
            "aggs": {
                "total_conversions": {"sum": {"field": "data_value"}}
            }
        }
    }
}

result = es.search(index=INDEX, body=query)
buckets = result["aggregations"]["creative_ids"]["buckets"]

print(f"\n📊 四月份广告主 {ADVERTISER_ID} 共有 {len(buckets)} 个创意有转化数据")

count_qualified = 0
qualified_list = []
for bucket in buckets:
    creative_id = bucket["key"]
    total_conv = bucket["total_conversions"]["value"]
    if total_conv > 1:
        # cvr = conversions / clicks, need to check clicks > 0 and cvr > 0.01
        # get total clicks for this creative
        query_clicks = {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {"terms": {"advertiser_id": [int(ADVERTISER_ID)]}},
                        {"terms": {"creative_id": [creative_id]}},
                        {"terms": {"data_type": [2]}},
                        {"range": {"data_date": {"gte": START_DATE, "lte": END_DATE}}}
                    ]
                }
            },
            "aggs": {
                "total_clicks": {"sum": {"field": "data_value"}}
            }
        }
        res_clicks = es.search(index=INDEX, body=query_clicks)
        total_clicks = res_clicks["aggregations"]["total_clicks"]["value"] or 0

        if total_clicks > 0:
            cvr = total_conv / total_clicks
            if cvr > 0.01:
                count_qualified += 1
                qualified_list.append({
                    "creative_id": creative_id,
                    "conversions": round(total_conv, 2),
                    "clicks": round(total_clicks, 2),
                    "cvr": round(cvr, 4)
                })

print(f"\n✅ 满足条件 (conversions > 1 AND cvr > 0.01): {count_qualified} 个创意")
if count_qualified > 0:
    print("\n列表：")
    for item in qualified_list[:10]:
        print(f"  - creative_id={item['creative_id']}, conv={item['conversions']}, clicks={item['clicks']}, cvr={item['cvr']}")
