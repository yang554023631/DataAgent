#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8000"

def test_query(query):
    print(f"\n{'='*60}")
    print(f"Testing: {query}")
    print(f"{'='*60}")

    # Create session
    resp = requests.post(
        f"{BASE_URL}/api/sessions",
        json={"user_id": "debug_test"},
        timeout=10
    )
    session_id = resp.json()["session_id"]
    print(f"Created session: {session_id}")

    # Send query
    print("Sending query...")
    resp = requests.post(
        f"{BASE_URL}/api/sessions/{session_id}/messages",
        json={"content": query},
        timeout=300
    )
    result = resp.json()

    print(f"\nResponse status: {result.get('status')}")
    if "result" in result and "final_report" in result["result"]:
        final = result["result"]["final_report"]
        print(f"Report type: {final.get('report_type')}")
        print(f"Message: {final.get('message', 'No message')}")
        if "data_table" in final:
            rows = final["data_table"].get("rows", [])
            print(f"Data table rows: {len(rows)}")
            if rows:
                print(f"First row: {rows[0]}")

    return result

# Test 12: 模糊查询 + 排序 + TopN - ad_group
result = test_query("在 digital_0 中找出名称包含六一八的所有广告组，按消耗降序排列前三")
