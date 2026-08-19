#!/usr/bin/env python3
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_query(query):
    print(f"\n{'='*60}")
    print(f"Testing: {query}")
    print(f"{'='*60}\n")

    # Create session
    sys.stdout.flush()
    resp = requests.post(
        f"{BASE_URL}/api/sessions",
        json={"user_id": "test19_final"},
        timeout=10
    )
    print(f"Create session status: {resp.status_code}")
    session_id = resp.json()["session_id"]
    print(f"Created session: {session_id}\n")

    # Send query
    print("Sending query... (this may take a few minutes)")
    sys.stdout.flush()
    resp = requests.post(
        f"{BASE_URL}/api/sessions/{session_id}/messages",
        json={"content": query},
        timeout=(10, 900)  # (connection timeout, read timeout)
    )
    print(f"\nResponse status: {resp.status_code}")
    result = resp.json()

    print(f"\nResult status: {result.get('status')}")
    if "result" in result and "final_report" in result["result"]:
        final = result["result"]["final_report"]
        print(f"Report type: {final.get('report_type')}")
        print(f"Message: {final.get('message', 'No message')}")
        if "data_table" in final:
            rows = final["data_table"].get("rows", [])
            print(f"Data table rows: {len(rows)}")
            if rows:
                print(f"\nResult rows:")
                for i, row in enumerate(rows):
                    print(f"  {i+1}. {row}")

    return result

# Test 19 modified
if __name__ == "__main__":
    result = test_query("找出 广告主 digital_0 下名称含 mini 的创意，点击量大于50")
