#!/usr/bin/env python3
"""Test Elasticsearch connection"""
import sys
from pathlib import Path

# Add backend to path
script_dir = Path(__file__).parent
backend_dir = script_dir / "backend"
sys.path.insert(0, str(backend_dir.resolve()))

from src.tools.custom_report_client import es_client

print("Testing Elasticsearch connection...")
try:
    info = es_client.info()
    print(f"✅ Connected! ES version: {info['version']['number']}")

    # Check if index exists
    index_exists = es_client.indices.exists(index="ad_stat_data")
    print(f"✅ ad_stat_data index exists: {index_exists}")

    if index_exists:
        # Count documents for advertiser 6 in April
        query = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"advertiser_id": 6}},
                        {"range": {"data_date": {"gte": "2026-04-01", "lte": "2026-04-30"}}}
                    ]
                }
            }
        }
        result = es_client.count(index="ad_stat_data", body=query)
        print(f"📊 Documents for advertiser 6 in April 2026: {result['count']}")

except Exception as e:
    print(f"❌ Connection failed: {str(e)}")
    sys.exit(1)
