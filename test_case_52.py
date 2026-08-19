#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8000"

# Test case 52: 广告主6转化率最高的创意
query = "广告主6转化率最高的创意"

print(f"Testing query: {query}")
print("=" * 60)

# Create session
resp = requests.post(f"{BASE_URL}/api/sessions", json={"user_id": "test"})
session = resp.json()
session_id = session["session_id"]
print(f"Created session: {session_id}")

# Send message
print("\nSending query...")
resp = requests.post(
    f"{BASE_URL}/api/sessions/{session_id}/messages",
    json={"content": query}
)

result = resp.json()
print(f"\nResponse status: {result['status']}")

if result["status"] == "completed":
    print(f"\nResult found:")
    if "result" in result:
        query_result = result["result"].get("query_result", {})
        print(f"  query_result keys: {list(query_result.keys())}")
        final_report = result["result"].get("final_report")
        if final_report:
            print(f"  final_report keys: {list(final_report.keys())}")
            if "data" in final_report:
                data = final_report["data"]
                print(f"  data keys: {list(data.keys())}")
                if "rows" in data:
                    print(f"  Number of rows: {len(data['rows'])}")
                    if len(data["rows"]) > 0:
                        print(f"  First row: {data['rows'][0]}")
                if "entities" in data:
                    print(f"  Number of entities: {len(data['entities'])}")
        print("\n✅ SUCCESS - Data returned (not empty)")
    else:
        print("\n❌ FAILED - No result field")
elif result["status"] == "waiting_for_clarification":
    print(f"\n⚠️  Waiting for clarification: {result['clarification']['question']}")
else:
    print(f"\n❌ Unexpected status: {result['status']}")
    print(f"Full response: {json.dumps(result, indent=2, ensure_ascii=False)}")
