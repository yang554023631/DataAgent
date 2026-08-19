#!/usr/bin/env python3
"""Test import with the same path setup as the test script"""

import sys
from pathlib import Path

# 这和 diversified_query_test.py 完全一样
script_dir = Path(__file__).parent
backend_dir = script_dir / "../backend"
sys.path.insert(0, str(backend_dir.resolve()))

print(f"script_dir: {script_dir.resolve()}")
print(f"backend_dir: {backend_dir.resolve()}")
print(f"sys.path[0]: {sys.path[0]}")

try:
    from src.graph.nodes import analysis_node
    print("✅ Import analysis_node OK")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
