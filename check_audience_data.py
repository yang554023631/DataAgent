#!/usr/bin/env python3
"""检查广告主6是否有受众维度数据"""

import os
import sys
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

ES_URL = os.getenv("ES_URL")
ES_USER = os.getenv("ES_USER")
ES_PASSWORD = os.getenv("ES_PASSWORD")

if not ES_URL:
    print("❌ 缺少 ES_URL 环境变量")
    sys.exit(1)

# 连接ES
if ES_USER and ES_PASSWORD:
    es = Elasticsearch(ES_URL, basic_auth=(ES_USER, ES_PASSWORD))
else:
    es = Elasticsearch(ES_URL)

# 获取索引名称（通常是ads_stats或者类似）
indices = es.cat.indices(format="json")
print("📋 可用索引:")
for idx in indices:
    print(f"  - {idx['index']}")
print()

# 查找可能的索引
target_index = None
for idx in indices:
    if "stat" in idx["index"].lower() or "ad" in idx["index"].lower():
        target_index = idx["index"]
        break

if not target_index:
    print("❌ 找不到广告统计索引")
    sys.exit(1)

print(f"🔍 使用索引: {target_index}")
print()

# 查询广告主6的一条数据，看看有哪些字段
query = {
    "size": 1,
    "query": {
        "term": {
            "advertiser_id": "6"
        }
    }
}

result = es.search(index=target_index, body=query)

hits = result["hits"]["hits"]
if not hits:
    print("❌ 找不到广告主6的任何数据")
    sys.exit(1)

source = hits[0]["_source"]
print("📊 广告主6数据字段列表:")
for key in sorted(source.keys()):
    value = source[key]
    if isinstance(value, (int, float, str)):
        print(f"  - {key}: {repr(value)}")
    else:
        print(f"  - {key}: {type(value).__name__}")

print()
print("🔍 检查受众相关字段:")
audience_fields = ['gender', 'city', 'age', 'sex', 'audience', 'district', 'province']
found = False
for field in audience_fields:
    if field in source:
        print(f"  ✅ 存在字段 '{field}'，示例值: {repr(source[field])}")
        found = True
    else:
        print(f"  ❌ 不存在字段 '{field}'")

if not found:
    print()
    print("❌ 没有找到任何受众相关字段")
    print("所有字段: " + ", ".join(sorted(source.keys())))
else:
    print()
    print("✅ 找到受众字段，现在检查广告主6在4月份有多少条数据:")
    count_query = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"advertiser_id": "6"}},
                    {"range": {"date": {"gte": "2026-04-01", "lte": "2026-04-30"}}}
                ]
            }
        }
    }
    count_result = es.count(index=target_index, body=count_query)
    print(f"📊 4月份总数据条数: {count_result['count']}")
