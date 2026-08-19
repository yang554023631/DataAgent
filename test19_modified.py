#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8000"

def test_query(query):
    print(f"\n{'='*60}")
    print(f"Testing modified query: {query}")
    print(f"{'='*60}")

    # Create session
    resp = requests.post(
        f"{BASE_URL}/api/sessions",
        json={"user_id": "test19_modified"},
        timeout=10
    )
    session_id = resp.json()["session_id"]
    print(f"Created session: {session_id}")

    # Send query
    print("Sending query...")
    resp = requests.post(
        f"{BASE_URL}/api/sessions/{session_id}/messages",
        json={"content": query},
        timeout=600
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
                print(f"First 5 rows:")
                for i, row in enumerate(rows[:5]):
                    print(f"  {i+1}. {row}")

    return result

# Modified test 19 - clear that "digital_0" is advertiser name
result = test_query("找出 广告主 digital_0 下名称含 mini 的创意，点击量大于50")
