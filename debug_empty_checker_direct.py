#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.empty_checker import EmptyResultChecker
from src.nl_dsl.dsl_templates.common import build_common_filters, LEVEL_TO_FIELD
from src.nl_dsl.models import EmptyCheckResult

es = Elasticsearch(["http://localhost:9200"])

# Recreate the exact call
advertiser_ids = ["6"]
entity_ids = [69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148]
entity_level = "creative"
start_date = "2000-01-01"
end_date = "2026-08-17"

# This is what _run_es_checks does:
empty_checker = EmptyResultChecker(es)

# Let's replicate manually to see what happens
# Check doc count
data_types = {1, 3}  # cost and impressions
filters = build_common_filters(
    advertiser_ids=advertiser_ids,
    start_date=start_date,
    end_date=end_date,
    data_types=list(data_types)
)
level_field = LEVEL_TO_FIELD.get(entity_level, f"{entity_level}_id")
filters.append({"terms": {level_field: entity_ids}})

print(f"Filters: {filters}")

dsl = {
    "query": {"bool": {"filter": filters}},
    "size": 0
}
response = es.search(index="ad_stat_data", body=dsl)
doc_count = response.get("hits", {}).get("total", {}).get("value", 0)
print(f"\ndoc_count = {doc_count}")

# Check core sum
core_metrics = ["cost", "impressions"]
core_data_types = set()
from src.nl_dsl.dsl_templates.common import get_data_type
for metric in core_metrics:
    dt = get_data_type(metric)
    if dt is not None:
        core_data_types.add(dt)

print(f"\ncore_data_types = {core_data_types}")

core_filters = build_common_filters(
    advertiser_ids=advertiser_ids,
    start_date=start_date,
    end_date=end_date,
    data_types=list(core_data_types)
)
core_filters.append({"terms": {level_field: entity_ids}})

aggs = {}
for dt in core_data_types:
    aggs[f"sum_dt_{dt}"] = {
        "filter": {"term": {"data_type": dt}},
        "aggs": {
            "total": {"sum": {"field": "data_value"}}
        }
    }

dsl = {
    "query": {"bool": {"filter": core_filters}},
    "size": 0,
    "aggs": aggs
}

response = es.search(index="ad_stat_data", body=dsl)
total_sum = 0.0
aggregations = response.get("aggregations", {})
for dt in core_data_types:
    agg_result = aggregations.get(f"sum_dt_{dt}", {})
    dt_sum = agg_result.get("total", {}).get("value", 0)
    name = "cost" if dt == 1 else "impressions"
    print(f"  {name}: {dt_sum}")
    if dt_sum:
        total_sum += dt_sum

print(f"\ntotal_sum = {total_sum}")
print(f"core_sum == 0 ? {total_sum == 0}")
