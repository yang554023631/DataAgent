#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.dsl_templates.common import build_common_filters, LEVEL_TO_FIELD
from src.analysis.models import AnalysisPlan, AnalysisTimeRange

es = Elasticsearch(["http://localhost:9200"])

# Get all 80 creative_ids from creative index for advertiser 6
must = [{"terms": {"advertiser_id": [6]}}]
dsl_dim = {
    "query": {"bool": {"must": must}},
    "size": 200,
}
resp = es.search(index="creative", body=dsl_dim)
entity_ids = [hit["_source"]["creative_id"] for hit in resp["hits"]["hits"]]
print(f"Got {len(entity_ids)} creative_ids")

# Build query the same way EmptyResultChecker does
analysis_plan = AnalysisPlan(
    analysis_type="entity_table",
    chart_type="table",
    time_range=AnalysisTimeRange(
        start_date="2000-01-01",
        end_date="2026-08-17",
        granularity="day"
    ),
    metrics=["conversions", "impressions", "cost", "cvr", "clicks"],
    dimensions=["creative_id", "creative_name"],
    filters=[]
)

time_range = analysis_plan.time_range
metrics = analysis_plan.metrics
data_types = set()
from src.nl_dsl.dsl_templates.common import get_data_type
for metric in metrics:
    dt = get_data_type(metric)
    if dt is not None:
        data_types.add(dt)

print(f"data_types: {sorted(data_types)}")

filters = build_common_filters(
    advertiser_ids=["6"],
    start_date=time_range.start_date,
    end_date=time_range.end_date,
    data_types=list(data_types) if data_types else None,
)

level_field = LEVEL_TO_FIELD.get("creative", "creative_id")
filters.append({"terms": {level_field: entity_ids}})

print(f"\nFinal filters:")
for i, f in enumerate(filters):
    print(f"  [{i}]: {f}")

dsl = {
    "query": {
        "bool": {
            "filter": filters,
        },
    },
    "size": 0,
}

print(f"\nExecuting query...")
response = es.search(index="ad_stat_data", body=dsl)
doc_count = response["hits"]["total"]["value"]
print(f"doc_count = {doc_count}")
