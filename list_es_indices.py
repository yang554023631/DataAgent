#!/usr/bin/env python3
"""List all Elasticsearch indices"""
import sys
from pathlib import Path

# Add backend to path
script_dir = Path(__file__).parent
backend_dir = script_dir / "backend"
sys.path.insert(0, str(backend_dir.resolve()))

from src.tools.custom_report_client import es_client

print("Listing all Elasticsearch indices...")
try:
    indices = es_client.indices.get(index="*")
    print(f"Found {len(indices)} indices:")
    for name in sorted(indices.keys()):
        print(f"  - {name}")
except Exception as e:
    print(f"Error: {str(e)}")
    sys.exit(1)
