#!/usr/bin/env python3
import sys
import json
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.dsl_templates.common import build_common_filters, LEVEL_TO_FIELD
from src.nl_dsl.dsl_templates.common import get_data_type

es = Elasticsearch(["http://localhost:9200"])

# 检查广告主6 全生命周期的 adgroup 数据
advertiser_ids = ["6"]
start_date = ""
end_date = ""
data_types = [get_data_type("clicks"), get_data_type("impressions")]

filters = build_common_filters(advertiser_ids, start_date, end_date, data_types)

dsl = {
    "query": {"bool": {"filter": filters}},
    "size": 0,
    "aggs": {
        "by_ad_group": {
            "terms": {"field": "adgroup_id", "size": 100}
        }
    }
}

print(f"DSL: {json.dumps(dsl, indent=2)}")
response = es.search(index="ad_stat_data", body=dsl)
doc_count = response.get("hits", {}).get("total", {}).get("value", 0)
print(f"\ndoc_count = {doc_count}")

agg = response.get("aggregations", {}).get("by_ad_group", {})
buckets = agg.get("buckets", [])
print(f"Number of distinct adgroups: {len(buckets)}")
if buckets:
    print(f"First 10 adgroup_ids: {[b['key'] for b in buckets[:10]]}")
