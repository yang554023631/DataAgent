#!/usr/bin/env python3
import sys
sys.path.insert(0, 'backend')
from src.analysis.prompts import build_few_shot_section

# A few-shot example that contains JSON
example = {
    'question': 'test cross-level',
    'category': 'cross_level',
    'plan': '''{
  "target_level": "campaign",
  "filter_plan": {
    "filter_type": "cross_level",
    "target_level": "campaign",
    "steps": [
      {
        "step_id": "step_1",
        "step_type": "where_filter",
        "level": "advertiser",
        "index": "advertiser",
        "conditions": [
          {
            "field": "advertiser_id",
            "operator": "=",
            "value": 123
          }
        ],
        "output_field": "advertiser_id"
      }
    ]
  }
}'''
}

result = build_few_shot_section([example])
print(result)
