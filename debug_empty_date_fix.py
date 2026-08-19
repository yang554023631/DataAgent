#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.dsl_templates.common import build_common_filters, LEVEL_TO_FIELD

es = Elasticsearch(["http://localhost:9200"])

# Test with empty strings like in the actual case
advertiser_ids = ["6"]
start_date = ""
end_date = ""
entity_ids = [69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148]
entity_level = "creative"
data_types = [1, 3]

# This is what build_common_filters returns now
filters = build_common_filters(
    advertiser_ids=advertiser_ids,
    start_date=start_date,
    end_date=end_date,
    data_types=data_types
)

level_field = LEVEL_TO_FIELD.get(entity_level, f"{entity_level}_id")
filters.append({"terms": {level_field: entity_ids}})

print(f"build_common_filters with empty start/end:")
print(f"Number of filters: {len(filters)}")
for i, f in enumerate(filters):
    print(f"  [{i}]: {f}")

print(f"\nQuery ES...")
dsl = {
    "query": {"bool": {"filter": filters}},
    "size": 0
}
response = es.search(index="ad_stat_data", body=dsl)
doc_count = response.get("hits", {}).get("total", {}).get("value", 0)
print(f"doc_count = {doc_count}")

# Now check core sum
aggs = {}
for dt in data_types:
    aggs[f"sum_dt_{dt}"] = {
        "filter": {"term": {"data_type": dt}},
        "aggs": {
            "total": {"sum": {"field": "data_value"}},
        }
    }
dsl = {
    "query": {"bool": {"filter": filters}},
    "size": 0,
    "aggs": aggs
}
response = es.search(index="ad_stat_data", body=dsl)
total_sum = 0.0
aggregations = response.get("aggregations", {})
for dt in data_types:
    agg_result = aggregations.get(f"sum_dt_{dt}", {})
    dt_sum = agg_result.get("total", {}).get("value", 0)
    name = "cost" if dt == 1 else "impressions"
    print(f"  {name}: {dt_sum}")
    if dt_sum:
        total_sum += dt_sum

print(f"\nFinal total_sum = {total_sum}")
print(f"core_sum == 0 ? {total_sum == 0}")
