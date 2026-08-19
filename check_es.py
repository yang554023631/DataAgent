#!/usr/bin/env python3
import os
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()

ES_URL = os.getenv("ES_URL")
ES_USER = os.getenv("ES_USER")
ES_PASSWORD = os.getenv("ES_PASSWORD")

print(f"ES_URL: {ES_URL}")

if ES_USER and ES_PASSWORD:
    es = Elasticsearch(ES_URL, basic_auth=(ES_USER, ES_PASSWORD))
else:
    es = Elasticsearch(ES_URL)

# 检查连接
print("\n=== 检查连接 ===")
try:
    info = es.info()
    print(f"ES连接成功! 版本: {info['version']['number']}")
except Exception as e:
    print(f"ES连接失败: {e}")
    exit(1)

# 列出所有索引
print("\n=== 所有索引 ===")
indices = es.cat.indices(format="json")
for idx in indices:
    print(f"  {idx['index']:20} docs: {idx['docs.count']}")

# 检查ad_stat_data是否存在
print("\n=== 检查 ad_stat_data 索引 ===")
if es.exists(index="ad_stat_data"):
    count = es.count(index="ad_stat_data")
    print(f"ad_stat_data 存在，总文档数: {count['count']}")

    # 看看有哪些advertiser_id
    print("\nTop 10 advertiser_id by document count:")
    query = {
        "size": 0,
        "aggs": {
            "by_advertiser": {
                "terms": {"field": "advertiser_id.keyword", "size": 10}
            }
        }
    }
    result = es.search(index="ad_stat_data", body=query)
    buckets = result["aggregations"]["by_advertiser"]["buckets"]
    for bucket in buckets:
        print(f"  advertiser_id={bucket['key']}: {bucket['doc_count']} 文档")
else:
    print("ad_stat_data 索引不存在!")

# 检查campaign维度表
print("\n=== 检查 campaign 维度表 ===")
if es.exists(index="campaign"):
    count = es.count(index="campaign")
    print(f"campaign 存在，总文档数: {count['count']}")
else:
    print("campaign 索引不存在!")
