#!/usr/bin/env python3
"""Test if simple_map_metrics correctly extracts '转化率' -> cvr"""

import sys
from pathlib import Path
script_dir = Path(__file__).parent
backend_dir = script_dir / "backend"
sys.path.insert(0, str(backend_dir.resolve()))

from src.analysis.intent_analyzer import simple_map_metrics

test_cases = [
    "广告主6转化率最高的三个创意",
    "转化率",
    "转化率前三",
    "找出转化率大于3%的创意",
    "转化率cvr",
    "点击转化率",
]

print("Testing simple_map_metrics for '转化率':")
print("-" * 60)
for query in test_cases:
    result = simple_map_metrics(query)
    print(f"Query: '{query}'")
    print(f"Result: {result}")
    print(f"Contains 'cvr': {'cvr' in result}")
    print()
