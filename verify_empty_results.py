#!/usr/bin/env python3
"""
验证这7个空结果查询在ES中是否真的没有数据
"""

import sys
import os
from pathlib import Path
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# 添加backend路径
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir / "backend"))

# 加载环境变量
load_dotenv()

ES_URL = os.getenv("ES_URL", "http://localhost:9200")
es = Elasticsearch([ES_URL])

print(f"连接ES: {ES_URL}")
print(f"ES连接成功: {es.ping()}")
print()

# 检查各个索引是否存在
indices = ["advertiser", "campaign", "adgroup", "creative", "ad_stat_data"]
for idx in indices:
    if es.indices.exists(index=idx):
        count = es.count(index=idx)["count"]
        print(f"✓ 索引 {idx} 存在，文档数: {count}")
    else:
        print(f"✗ 索引 {idx} 不存在")
print()

# 1. 先查广告主 digital_0 是否存在
print("=" * 60)
print("1. 检查广告主 digital_0 是否存在")
result = es.search(
    index="advertiser",
    query={"wildcard": {"advertiser_name": "*digital_0*"}},
    size=10
)
print(f"匹配 'digital_0' 的广告主数量: {result['hits']['total']['value']}")
for hit in result['hits']['hits']:
    print(f"   ID: {hit['_source'].get('advertiser_id')}, 名称: {hit['_source'].get('advertiser_name')}")
print()

# 2. 检查广告主6是否存在
print("=" * 60)
print("2. 检查广告主ID=6 是否存在")
result = es.search(
    index="advertiser",
    query={"term": {"advertiser_id": 6}},
    size=1
)
print(f"匹配广告主ID=6的数量: {result['hits']['total']['value']}")
for hit in result['hits']['hits']:
    print(f"   ID: {hit['_source'].get('advertiser_id')}, 名称: {hit['_source'].get('advertiser_name')}")
print()

# 3. 检查 digital_0 下广告计划中是否有名称含 digital 的
print("=" * 60)
print("3. 检查 digital_0 (假设ID=? 需要先找到advertiser_id) → 广告计划含 'digital'")
# 先找digital_0的id
adv_result = es.search(
    index="advertiser",
    query={"term": {"advertiser_name": "digital_0"}},
    size=1
)
if adv_result['hits']['total']['value'] > 0:
    adv_id = adv_result['hits']['hits'][0]['_source']['advertiser_id']
    print(f"digital_0 的advertiser_id = {adv_id}")

    result = es.search(
        index="campaign",
        query={
            "bool": {
                "must": [
                    {"term": {"advertiser_id": adv_id}},
                    {"wildcard": {"campaign_name": "*digital*"}}
                ]
            }
        },
        size=20
    )
    print(f"广告计划名称包含 'digital' 的数量: {result['hits']['total']['value']}")
    for hit in result['hits']['hits']:
        print(f"   ID: {hit['_source'].get('campaign_id')}, 名称: {hit['_source'].get('campaign_name')}")
else:
    print("未找到advertiser_name=digital_0")
print()

# 4. 检查 digital_0 下广告组中是否有名称含"六一八"的
print("=" * 60)
print("4. 检查 digital_0 下广告组名称含 '六一八'")
if adv_result['hits']['total']['value'] > 0:
    adv_id = adv_result['hits']['hits'][0]['_source']['advertiser_id']
    result = es.search(
        index="adgroup",
        query={
            "bool": {
                "must": [
                    {"term": {"advertiser_id": adv_id}},
                    {"wildcard": {"adgroup_name": "*六一八*"}}
                ]
            }
        },
        size=20
    )
    print(f"广告组名称包含 '六一八' 的数量: {result['hits']['total']['value']}")
    for hit in result['hits']['hits']:
        print(f"   ID: {hit['_source'].get('adgroup_id')}, 名称: {hit['_source'].get('adgroup_name')}")
else:
    print("未找到advertiser digital_0")
print()

# 5. 检查 digital_0 下创意中是否有名称含"尊享"的
print("=" * 60)
print("5. 检查 digital_0 下创意名称含 '尊享'")
if adv_result['hits']['total']['value'] > 0:
    adv_id = adv_result['hits']['hits'][0]['_source']['advertiser_id']
    result = es.search(
        index="creative",
        query={
            "bool": {
                "must": [
                    {"term": {"advertiser_id": adv_id}},
                    {"wildcard": {"creative_name": "*尊享*"}}
                ]
            }
        },
        size=20
    )
    print(f"创意名称包含 '尊享' 的数量: {result['hits']['total']['value']}")
    for hit in result['hits']['hits']:
        print(f"   ID: {hit['_source'].get('creative_id')}, 名称: {hit['_source'].get('creative_name')}")
else:
    print("未找到advertiser digital_0")
print()

# 6. 检查 digital_0 下投放中的广告计划，是否有名称含"best"的
print("=" * 60)
print("6. 检查 digital_0 下投放中广告计划名称含 'best'")
if adv_result['hits']['total']['value'] > 0:
    adv_id = adv_result['hits']['hits'][0]['_source']['advertiser_id']
    # status=1 通常表示投放中，看看实际数据
    result = es.search(
        index="campaign",
        query={
            "bool": {
                "must": [
                    {"term": {"advertiser_id": adv_id}},
                    {"wildcard": {"campaign_name": "*best*"}}
                ]
            }
        },
        size=20
    )
    print(f"广告计划名称包含 'best' 的数量: {result['hits']['total']['value']}")
    for hit in result['hits']['hits']:
        status = hit['_source'].get('status', 'unknown')
        print(f"   ID: {hit['_source'].get('campaign_id')}, 名称: {hit['_source'].get('campaign_name')}, status: {status}")
else:
    print("未找到advertiser digital_0")
print()

# 7. 检查 digital_0 下创意中是否有名称含"mini"的
print("=" * 60)
print("7. 检查 digital_0 下创意名称含 'mini'")
if adv_result['hits']['total']['value'] > 0:
    adv_id = adv_result['hits']['hits'][0]['_source']['advertiser_id']
    result = es.search(
        index="creative",
        query={
            "bool": {
                "must": [
                    {"term": {"advertiser_id": adv_id}},
                    {"wildcard": {"creative_name": "*mini*"}}
                ]
            }
        },
        size=20
    )
    print(f"创意名称包含 'mini' 的数量: {result['hits']['total']['value']}")
    for hit in result['hits']['hits']:
        print(f"   ID: {hit['_source'].get('creative_id')}, 名称: {hit['_source'].get('creative_name')}")
else:
    print("未找到advertiser digital_0")
print()

# 8. 检查广告主6下是否有广告组（用于TopN排序测试）
print("=" * 60)
print("8. 检查广告主ID=6 下有多少广告组")
result = es.search(
    index="adgroup",
    query={"term": {"advertiser_id": 6}},
    size=20
)
print(f"广告组数量: {result['hits']['total']['value']}")
if result['hits']['total']['value'] > 0:
    for hit in result['hits']['hits'][:10]:
        print(f"   ID: {hit['_source'].get('adgroup_id')}, 名称: {hit['_source'].get('adgroup_name')}")
print()

# 9. 检查广告主6下是否有创意（用于TopN排序测试）
print("=" * 60)
print("9. 检查广告主ID=6 下有多少创意")
result = es.search(
    index="creative",
    query={"term": {"advertiser_id": 6}},
    size=20
)
print(f"创意数量: {result['hits']['total']['value']}")
if result['hits']['total']['value'] > 0:
    for hit in result['hits']['hits'][:10]:
        print(f"   ID: {hit['_source'].get('creative_id')}, 名称: {hit['_source'].get('creative_name')}")
print()
