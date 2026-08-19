#!/usr/bin/env python3
import sys
import traceback
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition
from src.nl_dsl.dsl_templates.common import get_data_type, build_common_filters

es = Elasticsearch(["http://localhost:9200"])

# 模拟筛选计划：
# 1. 第一步：在advertiser维度找到名称包含digital_0的广告主
# 2. 第二步：cross_level_down 从advertiser -> creative，筛选名称含mini的创意
# 3. 第三步：having_filter 筛选 clicks > 50

print("=== Step 1: Find advertiser_id for digital_0 ===")
# 第一步：找advertiser_id
query = {
    "query": {
        "bool": {
            "must": [
                {"wildcard": {"advertiser_name": "*digital_0*"}}
            ]
        }
    },
    "size": 10
}
result = es.search(index="advertiser", body=query)
hits = result["hits"]["hits"]
print(f"Found {len(hits)} advertisers matching 'digital_0':")
for hit in hits:
    source = hit["_source"]
    print(f"  advertiser_id: {source.get('advertiser_id')}, name: {source.get('advertiser_name')}")

if not hits:
    print("No advertiser found!")
    sys.exit(1)

advertiser_id = hits[0]["_source"]["advertiser_id"]
print(f"\nUsing advertiser_id = {advertiser_id}")

# 现在检查：在creative维度，找到名称含mini，且advertiser_id匹配的
print("\n=== Step 2: Find creative_id where name contains 'mini' and advertiser_id = {advertiser_id} ===")

query = {
    "query": {
        "bool": {
            "must": [
                {"wildcard": {"creative_name": "*mini*"}},
                {"term": {"advertiser_id": int(advertiser_id)}}
            ]
        }
    },
    "size": 100
}
result = es.search(index="creative", body=query)
hits = result["hits"]["hits"]
print(f"Found {len(hits)} creatives matching:")
for hit in hits:
    source = hit["_source"]
    print(f"  creative_id: {source.get('creative_id')}, name: {source.get('creative_name')}")

# 看看有没有数据
if len(hits) == 0:
    print("\n❌ No creatives found with name containing 'mini' in this advertiser")
else:
    print(f"\n✅ Found {len(hits)} creatives")

# 现在检查 having 过滤：点击量 > 50
creative_ids = [hit["_source"]["creative_id"] for hit in hits]
print(f"\n=== Step 3: Check which of these {len(creative_ids)} creatives have clicks > 50 ===")

from src.nl_dsl.dsl_templates.common import build_common_filters
filters = build_common_filters([str(advertiser_id)], "", "", [get_data_type("clicks")])
filters.append({"terms": {"creative_id": [int(cid) for cid in creative_ids]}})

dsl = {
    "query": {"bool": {"filter": filters}},
    "size": 0,
    "aggs": {
        "by_creative": {
            "terms": {"field": "creative_id", "size": 100},
            "aggs": {
                "sum_clicks": {
                    "filter": {"term": {"data_type": get_data_type("clicks")}},
                    "aggs": {
                        "total": {"sum": {"field": "data_value"}}
                    }
                }
            }
        }
    }
}

from src.nl_dsl.dsl_templates.common import get_data_type
print(f"DSL filters: {filters}")

response = es.search(index="ad_stat_data", body=dsl)
agg = response["aggregations"]["by_creative"]
buckets = agg["buckets"]
print(f"\nFound {len(buckets)} buckets after aggregation:")
passed = []
for bucket in buckets:
    cid = bucket["key"]
    total = bucket["sum_clicks"]["total"]["value"]
    if total > 50:
        passed.append((cid, total))
        print(f"  ✅ creative_id {cid}: clicks = {total:.0f} > 50")
    else:
        print(f"  ⚪ creative_id {cid}: clicks = {total:.0f} ≤ 50")

print(f"\nFinal result: {len(passed)} creatives passed the clicks > 50 filter")
