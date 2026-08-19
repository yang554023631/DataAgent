#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.empty_checker import EmptyResultChecker
from src.analysis.models import AnalysisPlan, AnalysisTimeRange

es = Elasticsearch(["http://localhost:9200"])

# case 18:
# After filter, entity_ids should be [13]
analysis_plan = AnalysisPlan(
    analysis_type="entity_table",
    chart_type="table",
    time_range=AnalysisTimeRange(
        start_date="2000-01-01",
        end_date="2026-08-17",
        granularity="day"
    ),
    metrics=["cost", "clicks"],
    dimensions=["campaign_id", "campaign_name"],
    filters=[]
)

checker = EmptyResultChecker(es)

# entity_ids = [13], entity_level = campaign
result = checker._run_es_checks(
    analysis_plan=analysis_plan,
    advertiser_ids=["6"],
    entity_ids=[13],
    entity_level="campaign"
)

print(f"found_error: {result.found_error}")
print(f"error_type: {result.error_type if result.found_error else None}")
print(f"hints: {result.hints}")

# Let's manually see what's happening
from src.nl_dsl.dsl_templates.common import build_common_filters
filters = build_common_filters(
    advertiser_ids=["6"],
    start_date="2000-01-01",
    end_date="2026-08-17",
    data_types=[3, 2],  # cost=3, clicks=2
)
from src.nl_dsl.dsl_templates.common import LEVEL_TO_FIELD
level_field = LEVEL_TO_FIELD.get("campaign", f"{'campaign'}_id")
filters.append({"terms": {level_field: [13]}})

print()
print(f"Filters:")
import json
print(json.dumps(filters, indent=2))

# Execute
dsl = {
    "query": {"bool": {"filter": filters}},
    "size": 0,
}
response = es.search(index="ad_stat_data", body=dsl)
doc_count = response.get("hits", {}).get("total", {}).get("value", 0)
print()
print(f"Manually checked doc_count = {doc_count}")
