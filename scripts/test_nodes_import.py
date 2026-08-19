#!/usr/bin/env python3
"""Test import after fixing path"""

import sys
from pathlib import Path

# Add root
root_dir = Path(__file__).parent / ".."
sys.path.insert(0, str(root_dir.resolve()))
print(f"root_dir: {root_dir.resolve()}")
print(f"sys.path[0] = {sys.path[0]}")
print(f"backend/src exists: {(root_dir / 'backend' / 'src').exists()}")

# Now import nodes
try:
    from backend.src.graph.nodes import analysis_node
    print("✅ Import analysis_node from backend.src.graph.nodes OK")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()

print("\n--- Let's see what os.path.dirname(__file__) gives in nodes.py ---")
import os
nodes_path = os.path.join(root_dir.resolve(), "backend", "src", "graph", "nodes.py")
print(f"nodes_path: {nodes_path}")
print(f"dirname(__file__) for nodes.py would be: {os.path.dirname(nodes_path)}")
print(f"os.path.join(dirname, '..', '..') = {os.path.join(os.path.dirname(nodes_path), '..', '..')}")
print(f"exists? {os.path.exists(os.path.join(os.path.dirname(nodes_path), '..', '..'))}:")
