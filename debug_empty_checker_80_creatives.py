#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
import asyncio
from elasticsearch import Elasticsearch
from src.nl_dsl.empty_checker import EmptyResultChecker
from src.analysis.models import AnalysisPlan, AnalysisTimeRange
from src.nl_dsl.models import FilterResult

es = Elasticsearch(["http://localhost:9200"])

# case 52: 广告主6转化率最高的三个创意
# FilterExecutor got 80 entities
filter_result = FilterResult(
    entity_ids=list(range(1, 81)),  # 80 creative ids
    entity_level="creative",
    total_count=80,
    trace=[],
    truncated=False
)

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

checker = EmptyResultChecker(es)

async def run():
    result = await checker.async_check(
        analysis_plan=analysis_plan,
        advertiser_ids=["6"],
        filter_result=filter_result
    )
    print(f"Empty check result:")
    print(f"  found_error: {result.found_error}")
    print(f"  error_type: {result.error_type if result.found_error else None}")
    print(f"  hints: {result.hints}")

asyncio.run(run())
