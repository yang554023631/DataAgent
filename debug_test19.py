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
    if "result" in result:
        print(f"Result keys: {list(result['result'].keys())}")
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

# Test 19: 混合筛选 - 名称 + having点击
result = test_query("找出 digital_0 下名称含 mini 的创意，点击量大于50")
