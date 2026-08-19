#!/usr/bin/env python3
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def create_session():
    resp = requests.post(f"{BASE_URL}/api/sessions", json={"user_id": "test"})
    resp.raise_for_status()
    return resp.json()["session_id"]

def send_message(session_id, query):
    resp = requests.post(
        f"{BASE_URL}/api/sessions/{session_id}/messages",
        json={"content": query}
    )
    resp.raise_for_status()
    return resp.json()

def print_result(result, test_name):
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

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_single.py 'Test Name' 'query'")
        sys.exit(1)
    
    name = sys.argv[1]
    query = sys.argv[2]
    
    session_id = create_session()
    print(f"Created session: {session_id}")
    result = send_message(session_id, query)
    print_result(result, name)
