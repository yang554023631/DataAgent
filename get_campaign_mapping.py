#!/usr/bin/env python3
"""Get campaign index mapping"""
import sys
from pathlib import Path

# Add backend to path
script_dir = Path(__file__).parent
backend_dir = script_dir / "backend"
sys.path.insert(0, str(backend_dir.resolve()))

from src.tools.custom_report_client import es_client

print("Getting mapping for campaign index...")
try:
    mapping = es_client.indices.get_mapping(index="campaign")
    properties = mapping['campaign']['mappings']['properties']
    print("\nProperties:")
    for field, props in properties.items():
        print(f"  - {field}: {props.get('type', 'unknown')}")

    if 'campaign_status' in properties:
        print(f"\ncampaign_status mapping: {properties['campaign_status']}")

except Exception as e:
    print(f"Error: {str(e)}")
    sys.exit(1)
