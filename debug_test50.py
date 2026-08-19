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
                print(f"First 3 rows: {rows[:3]}")

    return result

# Test 50: Ad Group TopN - 点击率前五
result = test_query("列出广告主6点击率从高到低排前五的广告组")
