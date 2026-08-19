#!/usr/bin/env python3
import sys
import os
import json
from pathlib import Path

script_dir = Path(__file__).parent
backend_dir = script_dir / 'backend'
sys.path.insert(0, str(backend_dir.resolve()))

from src.tools.custom_report_client import build_es_query, CustomReportClient

query = {
    'advertiser_ids': ['6'],
    'time_range': {'start_date': '', 'end_date': '', 'is_lifetime': True},
    'metrics': ['cost'],
    'ad_level': 'campaign',
    'group_by': ['campaign_id', 'campaign_name'],
    'filters': [
        {'field': 'campaign_name', 'operator': 'like', 'value': 'digital', 'type': 'where'}
    ],
    'top_n': None,
    'sort': {'field': 'cost', 'order': 'desc'},
}

index, es_query = build_es_query(query)
print(f'index: {index}')
print(json.dumps(es_query, indent=2))
