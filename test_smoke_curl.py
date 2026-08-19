#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8000"

def create_session():
    """Create a new session"""
    resp = requests.post(f"{BASE_URL}/api/sessions", json={"user_id": "test"})
    resp.raise_for_status()
    return resp.json()["session_id"]

def send_message(session_id, query):
    """Send a message and get the final result"""
    resp = requests.post(
        f"{BASE_URL}/api/sessions/{session_id}/messages",
        json={"content": query}
    )
    resp.raise_for_status()
    return resp.json()

def print_result(result, test_name):
    """Print result summary"""
    print(f"\n{'='*60}")
    print(f"Test: {test_name}")
    print(f"{'='*60}")

    if "final_report" in result:
        final = result["final_report"]
        print(f"Title: {final.get('title', 'N/A')}")
        print(f"Success: {final.get('success', False)}")

        if "data_table" in final:
            rows = final["data_table"]["rows"]
            print(f"Data table: {len(rows)} rows")
            for i, row in enumerate(rows[:5]):
                print(f"  Row {i+1}: {list(row.values())}")
            if len(rows) > 5:
                print(f"  ... and {len(rows)-5} more")

        if "chart_data" in final:
            data = final["chart_data"]["data"]
            print(f"Chart data: {len(data)} points")
            for i, point in enumerate(data[:5]):
                print(f"  Point {i+1}: {point}")
            if len(data) > 5:
                print(f"  ... and {len(data)-5} more")

    print()

def main():
    # Tests to run
    tests = [
        ("Test 1: Time trend", "id为6的广告主4月份的消耗趋势"),
        ("Test 2: Where filter (is_deleted=0)", "广告主6下未删除的广告计划4月份的消耗和点击"),
        ("Test 3: Having filter (cost > 10)", "广告主6 4月份消耗大于10的广告计划有哪些"),
    ]

    # Create session
    session_id = create_session()
    print(f"Created session: {session_id}")

    # Run each test
    for name, query in tests:
        print(f"\n>>> Running: {name}")
        print(f"    Query: {query}")
        try:
            result = send_message(session_id, query)
            print_result(result, name)
        except Exception as e:
            print(f"✗ ERROR: {e}")

if __name__ == "__main__":
    main()
