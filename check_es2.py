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
try:
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
except Exception as e:
    print(f"ad_stat_data 查询失败: {e}")

# 检查campaign维度表
print("\n=== 检查 campaign 维度表 ===")
try:
    count = es.count(index="campaign")
    print(f"campaign 存在，总文档数: {count['count']}")

    # 看看广告主6有没有数据
    print("\n检查广告主ID=6 在 campaign 表:")
    query = {
        "query": {
            "term": {"advertiser_id": 6}
        },
        "size": 10
    }
    result = es.search(index="campaign", body=query)
    hits = result["hits"]["hits"]
    print(f"找到 {len(hits)} 条记录:")
    for hit in hits:
        source = hit["_source"]
        print(f"  campaign_id={source.get('campaign_id')}, name={source.get('campaign_name')}, is_deleted={source.get('is_deleted')}")
except Exception as e:
    print(f"campaign 查询失败: {e}")

# 检查advertiser维度表
print("\n=== 检查 advertiser 维度表 ===")
try:
    count = es.count(index="advertiser")
    print(f"advertiser 存在，总文档数: {count['count']}")

    # 列出所有广告主
    query = {
        "size": 100,
        "_source": ["advertiser_id", "advertiser_name"]
    }
    result = es.search(index="advertiser", body=query)
    hits = result["hits"]["hits"]
    print(f"广告主列表 (前{len(hits)}个):")
    for hit in hits:
        source = hit["_source"]
        print(f"  {source.get('advertiser_id')}: {source.get('advertiser_name')}")
except Exception as e:
    print(f"advertiser 查询失败: {e}")
