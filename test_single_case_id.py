#!/usr/bin/env python3
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

TEST_CASES = [
    {
        "id": 9,
        "name": "9: 找出 digital_0 名称带 digital 的广告计划，按消耗排序",
        "query": "找出 digital_0 名称带 digital 的广告计划，按消耗排序",
        "expected": {
            "success": True,
            "min_rows": 1,
        }
    },
    {
        "id": 18,
        "name": "18: digital_0 投放中的广告计划，名称含有 best，列出消耗和点击",
        "query": "digital_0 投放中的广告计划，名称含有 best，列出消耗和点击",
        "expected": {
            "success": True,
            "min_rows": 1,
        }
    },
    {
        "id": 19,
        "name": "19: 找出 digital_0 下名称含 mini 的创意，点击量大于50的",
        "query": "找出 digital_0 下名称含 mini 的创意，点击量大于50的",
        "expected": {
            "success": True,
            "min_rows": 2,
        }
    },
    {
        "id": 50,
        "name": "50: 列出广告主6点击率从高到低排前五的广告组",
        "query": "列出广告主6点击率从高到低排前五的广告组",
        "expected": {
            "success": True,
            "min_rows": 1,
        }
    },
    {
        "id": 52,
        "name": "52: 广告主6转化率最高的三个创意",
        "query": "广告主6转化率最高的三个创意",
        "expected": {
            "success": True,
            "min_rows": 3,
        }
    },
]

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

def validate(result, expected):
    if "result" not in result:
        return False, "Missing 'result'"
    if "final_report" not in result["result"]:
        return False, "Missing final_report"
    final = result["result"]["final_report"]
    report_type = final.get("report_type", "error")
    if expected["success"] and report_type != "success":
        return False, f"Expected success, got {report_type}"
    if "data_table" not in final:
        return False, "Missing data_table"
    rows = final["data_table"].get("rows", [])
    if len(rows) < expected["min_rows"]:
        return False, f"Expected {expected['min_rows']} rows, got {len(rows)}"
    return True, "OK"

if len(sys.argv) != 2:
    print(f"Usage: python {sys.argv[0]} <test_id>")
    print("Available test ids: 9, 18, 19, 50, 52")
    sys.exit(1)

test_id = int(sys.argv[1])
test = next(t for t in TEST_CASES if t["id"] == test_id)

print(f"Testing case {test_id}: {test['name']}")
print(f"Query: {test['query']}")
print()

session_id = create_session()
result = send_message(session_id, test["query"], timeout=180)

ok, msg = validate(result, test["expected"])
print()
print(f"Result: {'✅ PASSED' if ok else '❌ FAILED'} - {msg}")

final = result["result"]["final_report"]
if "data_table" in final:
    rows = final["data_table"].get("rows", [])
    print(f"Actual rows returned: {len(rows)}")
    if len(rows) > 0:
        print("First row:")
        print(json.dumps(rows[0], indent=2, ensure_ascii=False))
