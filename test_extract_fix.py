#!/usr/bin/env python3
import sys
import json
sys.path.insert(0, '/Users/simon/AL/DataAgent/backend')
from elasticsearch import Elasticsearch
from src.nl_dsl.dsl_templates.analysis_templates import build_period_comparison_summary
from src.nl_dsl.dsl_templates.result_extractors import extract_comparison_data

# Build the DSL same as test 4
dsl = build_period_comparison_summary(
    advertiser_ids=["6"],
    current_start="2026-04-01",
    current_end="2026-04-30",
    compare_start="2026-03-01",
    compare_end="2026-03-31",
    metrics=["cost"],
)

# Execute it
es = Elasticsearch("http://localhost:9200")
index = dsl.pop("index")
response = es.search(index=index, **dsl)

# Extract with fixed function
result = extract_comparison_data(response, ["cost"])
print("=== EXTRACT RESULT ===")
print(json.dumps(result, indent=2))
print(f"\ncurrent cost: {result['current_period']['cost']}")
print(f"compare cost: {result['compare_period']['cost']}")
