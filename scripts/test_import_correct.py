#!/usr/bin/env python3
"""Correct import test after path fix"""

import sys
from pathlib import Path

# Add backend directory to path (contains src/)
script_dir = Path(__file__).parent
backend_dir = script_dir / "../backend"
sys.path.insert(0, str(backend_dir.resolve()))

print(f"backend_dir: {backend_dir.resolve()}")
print(f"sys.path[0] = {sys.path[0]}")
print(f"backend_dir/src exists: {(backend_dir / 'src').exists()}")
print(f"backend_dir/src/analysis exists: {(backend_dir / 'src' / 'analysis').exists()}")

# Now import
try:
    from src.graph.nodes import analysis_node
    print("✅ Import analysis_node OK")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
