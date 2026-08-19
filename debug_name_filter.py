#!/usr/bin/env python3
"""
Debug 名称筛选
"""

import sys
import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

# 加载环境变量
load_dotenv()
ES_URL = os.getenv("ES_URL", "http://localhost:9200")
es = Elasticsearch([ES_URL])

print("=== Debug 测试 ID 9: 找出 digital_0 名称带 digital 的广告计划 ===")
print()

# 测试查询
query = {
    "bool": {
        "must": [
            {"terms": {"advertiser_id": [6]}},
            {"wildcard": {"campaign_name": "*digital*"}}
        ]
    }
}

result = es.search(index="campaign", query=query, size=10)
print(f"ES 查询结果: 总共 {result['hits']['total']['value']} 条")
for hit in result['hits']['hits']:
    print(f"  campaign_id={hit['_source']['campaign_id']}, name={hit['_source']['campaign_name']}")

print()
print("=== 测试 ID 18: digital_0 投放中的广告计划，名称含有 best ===")
print()

query = {
    "bool": {
        "must": [
            {"terms": {"advertiser_id": [6]}},
            {"wildcard": {"campaign_name": "*best*"}}
        ]
    }
}

result = es.search(index="campaign", query=query, size=10)
print(f"ES 查询结果: 总共 {result['hits']['total']['value']} 条")
for hit in result['hits']['hits']:
    print(f"  campaign_id={hit['_source']['campaign_id']}, name={hit['_source']['campaign_name']}, status={hit['_source'].get('status')}")

print()
print("=== 测试 ID 15: 列出 digital_0 名称含尊享的所有创意 ===")
print()

query = {
    "bool": {
        "must": [
            {"terms": {"advertiser_id": [6]}},
            {"wildcard": {"creative_name": "*尊享*"}}
        ]
    }
}

result = es.search(index="creative", query=query, size=10)
print(f"ES 查询结果: 总共 {result['hits']['total']['value']} 条")
for hit in result['hits']['hits']:
    print(f"  creative_id={hit['_source']['creative_id']}, name={hit['_source']['creative_name']}")

print()
print("=== 测试 ID 19: 找出 digital_0 下名称含 mini 的创意 ===")
print()

query = {
    "bool": {
        "must": [
            {"terms": {"advertiser_id": [6]}},
            {"wildcard": {"creative_name": "*mini*"}}
        ]
    }
}

result = es.search(index="creative", query=query, size=10)
print(f"ES 查询结果: 总共 {result['hits']['total']['value']} 条")
for hit in result['hits']['hits']:
    print(f"  creative_id={hit['_source']['creative_id']}, name={hit['_source']['creative_name']}")

print()
print("=== 测试 ID 50: 列出广告主6点击率前五的广告组 ===")
print()

# 先看有多少广告组
result = es.search(index="adgroup", query={"term": {"advertiser_id": 6}}, size=50)
print(f"广告主6总共有 {result['hits']['total']['value']} 个广告组:")
for i, hit in enumerate(result['hits']['hits']):
    print(f"  {i+1}. adgroup_id={hit['_source']['adgroup_id']}, name={hit['_source']['adgroup_name']}")

print()
print("=== 测试 ID 52: 列出广告主6转化率前三的创意 ===")
print()

result = es.search(index="creative", query={"term": {"advertiser_id": 6}}, size=50)
print(f"广告主6总共有 {result['hits']['total']['value']} 个创意:")
for i, hit in enumerate(result['hits']['hits'][:10]):
    print(f"  {i+1}. creative_id={hit['_source']['creative_id']}, name={hit['_source']['creative_name']}")
