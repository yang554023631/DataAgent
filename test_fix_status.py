#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent')
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from src.tools.custom_report_client import build_es_query

# Test case 18: digital_0 投放中的广告计划，名称含有 best，列出消耗和点击
query_request = {
    "advertiser_ids": ["6"],
    "metrics": ["cost", "clicks"],
    "group_by": [{"field": "campaign_id"}, {"field": "campaign_name"}],
    "filters": [
        {"field": "status", "operator": "eq", "value": 1},
        {"field": "campaign_name", "operator": "like", "value": "best"},
    ],
    "time_range": {"start_date": "2000-01-01", "end_date": "2026-08-16"},
}

index, es_query = build_es_query(query_request)
print(f"Index: {index}")
print()
print("ES Query:")
import json
print(json.dumps(es_query, indent=2))
