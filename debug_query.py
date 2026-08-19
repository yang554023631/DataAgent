#!/usr/bin/env python3
import json
from elasticsearch import Elasticsearch
from typing import List, Dict, Any

es = Elasticsearch(["http://localhost:9200"])

# Test case 18: digital_0 投放中的广告计划，名称含有 best，列出消耗和点击
# We found: campaign_id = 13
filters = [
    {"field": "status", "operator": "eq", "value": 1, "type": "where"},
    {"field": "campaign_name", "operator": "like", "value": "best", "type": "where"}
]
advertiser_ids = ["6"]
time_range = {"start": "", "end": "", "is_lifetime": True}
metrics = ["cost", "clicks"]
group_by = ["campaign_id", "campaign_name"]

# Simulate what build_es_query does
NAME_FIELD_TO_DIM_INDEX = {
    "campaign_name": "campaign",
    "adgroup_name": "adgroup",
    "creative_name": "creative",
}

bool_must = []

# 时间范围过滤
if time_range:
    start_date = "2000-01-01"
    end_date = "2026-08-16"
    if start_date and end_date:
        bool_must.append({
            "range": {
                "data_date": {
                    "gte": str(start_date),
                    "lte": str(end_date),
                }
            }
        })

# 广告主ID过滤
if advertiser_ids:
    bool_must.append({"terms": {"advertiser_id": [int(aid) for aid in advertiser_ids]}})

# 处理名称like过滤 - two-level search
matched_ids = [13]  # We already found this from dimension table
if matched_ids:
    id_field = "campaign_id"
    bool_must.append({"terms": {id_field: matched_ids}})

# Add status filter
bool_must.append({"term": {"status": 1}})

query = {"bool": {"must": bool_must}} if bool_must else {"match_all": {}}

print("Final ES Query:")
print(json.dumps(query, indent=2))
print()

# Execute
result = es.search(index="ad_stat_data", query=query, size=0, aggs={
    "group_0": {
        "terms": {"field": "campaign_id", "size": 100},
        "aggs": {
            "sum_cost": {
                "filter": {"term": {"data_type": 3}},
                "aggs": {"value": {"sum": {"field": "data_value"}}
                }
            },
            "sum_clicks": {
                "filter": {"term": {"data_type": 2}},
                "aggs": {"value": {"sum": {"field": "data_value"}}
                }
            }
        }
    }
})

print(f"Total matching docs: {result['hits']['total']['value']}")
print(f"Number of aggregation buckets: {len(result['aggregations']['group_0']['buckets'])}")
for bucket in result['aggregations']['group_0']['buckets']:
    print(f"  bucket {bucket['key']}: cost={bucket['sum_cost']['value']['value']}, clicks={bucket['sum_clicks']['value']['value']}")
