#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.empty_checker import EmptyResultChecker
from src.analysis.models import AnalysisPlan, AnalysisTimeRange

es = Elasticsearch(["http://localhost:9200"])

# After filtering: entity_ids = [13], entity_level = campaign
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
result = checker.check(
    analysis_plan=analysis_plan,
    advertiser_ids=["6"],
    entity_ids=[13],
    entity_level="campaign"
)

print(f"found_error: {result.found_error}")
if result.found_error:
    print(f"error_type: {result.error_type}")
    print(f"hints: {result.hints}")
else:
    print("No error found, should proceed")
