#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.dsl_templates.common import build_common_filters

es = Elasticsearch(["http://localhost:9200"])

# Build the same filters as EmptyResultChecker would
filters = build_common_filters(
    advertiser_ids=["6"],
    start_date="2000-01-01",
    end_date="2026-08-17",
    data_types=[1]  # data_type for cost is 1
)

# Add entity filter: campaign_id = 14
filters.append({"terms": {"campaign_id": [14]}})

dsl = {
    "query": {
        "bool": {
            "filter": filters,
        },
    },
    "size": 0,
}

print("DSL:")
print(dsl)
print()

response = es.search(index="ad_stat_data", body=dsl)
count = response.get("hits", {}).get("total", {}).get("value", 0)
print(f"Doc count in ad_stat_data: {count}")
