#!/usr/bin/env python3
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def create_session() -> str:
    resp = requests.post(
        f"{BASE_URL}/api/sessions",
        json={"user_id": "smoke_test"},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()["session_id"]

def send_message(session_id: str, query: str, timeout: int = 180):
    resp = requests.post(
        f"{BASE_URL}/api/sessions/{session_id}/messages",
        json={"content": query},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()

# Test case 9
query = "找出 digital_0 名称带 digital 的广告计划，按消耗排序"
print(f"Testing query: {query}")
print()

session_id = create_session()
result = send_message(session_id, query)

final = result["result"]["final_report"]
report_type = final.get("report_type", "error")
print(f"Report type: {report_type}")
print()

if "data_table" in final:
    rows = final["data_table"].get("rows", [])
    print(f"Number of rows: {len(rows)}")
    print()
    if len(rows) > 0:
        print("Data:")
        for row in rows:
            print(f"  {json.dumps(row, ensure_ascii=False)}")

print()
print(f"Full metadata: {json.dumps(final.get('metadata', {}), ensure_ascii=False, indent=2)}")
