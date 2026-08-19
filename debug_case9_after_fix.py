#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.empty_checker import EmptyResultChecker
from src.analysis.models import AnalysisPlan, AnalysisTimeRange

es = Elasticsearch(["http://localhost:9200"])

# case 9: after filtering, we expect entity_ids = [14], but 14 has 0 fact data
# So empty check should find it empty - which is correct because there really is no data
analysis_plan = AnalysisPlan(
    analysis_type="entity_table",
    chart_type="table",
    time_range=AnalysisTimeRange(
        start_date="2000-01-01",
        end_date="2026-08-17",
        granularity="day"
    ),
    metrics=["cost"],
    dimensions=["campaign_id", "campaign_name"],
    filters=[]
)

checker = EmptyResultChecker(es)
result = checker.check(
    analysis_plan=analysis_plan,
    advertiser_ids=["6"],
    entity_ids=[14],
    entity_level="campaign"
)

print(f"found_error: {result.found_error}")
if result.found_error:
    print(f"error_type: {result.error_type}")
    print(f"hints: {result.hints}")
else:
    print("No error found")

print()

# case 13 (which has data): should pass
print("=== Test case 13 (has 6978 rows) ===")
result2 = checker.check(
    analysis_plan=analysis_plan,
    advertiser_ids=["6"],
    entity_ids=[13],
    entity_level="campaign"
)
print(f"found_error: {result2.found_error}")
if result2.found_error:
    print(f"error_type: {result2.error_type}")
    print(f"hints: {result2.hints}")
else:
    print("No error found, will proceed to query execution")
