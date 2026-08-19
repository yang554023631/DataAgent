#!/usr/bin/env python3
import requests
import json
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

# The 6 problematic test cases that should have data but were returning empty
TEST_CASES = [
    {
        "id": 9,
        "name": "9: 找出 digital_0 名称带 digital 的广告计划，按消耗排序",
        "query": "找出 digital_0 名称带 digital 的广告计划，按消耗排序",
        "expected": {
            "success": True,
            "min_rows": 1,
            "has_data_table": True,
            "allow_all_zero": False,
        }
    },
    {
        "id": 18,
        "name": "18: digital_0 投放中的广告计划，名称含有 best，列出消耗和点击",
        "query": "digital_0 投放中的广告计划，名称含有 best，列出消耗和点击",
        "expected": {
            "success": True,
            "min_rows": 1,
            "has_data_table": True,
            "allow_all_zero": False,
        }
    },
    {
        "id": 19,
        "name": "19: 找出 digital_0 下名称含 mini 的创意，点击量大于50的",
        "query": "找出 digital_0 下名称含 mini 的创意，点击量大于50的",
        "expected": {
            "success": True,
            "min_rows": 1,
            "has_data_table": True,
            "allow_all_zero": False,
        }
    },
    {
        "id": 50,
        "name": "50: 列出广告主6点击率从高到低排前五的广告组",
        "query": "列出广告主6点击率从高到低排前五的广告组",
        "expected": {
            "success": True,
            "min_rows": 1,
            "has_data_table": True,
            "allow_all_zero": False,
        }
    },
    {
        "id": 52,
        "name": "52: 广告主6转化率最高的三个创意",
        "query": "广告主6转化率最高的三个创意",
        "expected": {
            "success": True,
            "min_rows": 1,
            "has_data_table": True,
            "allow_all_zero": False,
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


def send_message(session_id: str, query: str, timeout: int = 180) -> Dict[str, Any]:
    resp = requests.post(
        f"{BASE_URL}/api/sessions/{session_id}/messages",
        json={"content": query},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()


def validate_result(result: Dict[str, Any], expected: Dict[str, Any]) -> tuple[bool, str]:
    if "result" not in result:
        return False, "Missing 'result' in response"

    result_data = result["result"]

    if "final_report" not in result_data:
        if "warnings" in result_data and result_data["warnings"]:
            return False, f"Result has warnings: {result_data['warnings']}"
        return False, "Missing final_report in result"

    final = result_data["final_report"]

    if expected.get("success") is not None:
        report_type = final.get("report_type", "error")
        if expected["success"] and report_type != "success":
            error_msg = final.get("message", "Unknown error")
            return False, f"Expected success=True, got report_type={report_type}: {error_msg}"

    if expected.get("has_data_table"):
        if "data_table" not in final:
            return False, "Missing data_table in response"
        rows = final["data_table"].get("rows", [])
        min_rows = expected.get("min_rows", 1)
        if len(rows) < min_rows:
            return False, f"Expected at least {min_rows} rows, got {len(rows)}"

    if not expected.get("allow_all_zero", True):
        if "data_table" in final and "rows" in final["data_table"]:
            rows = final["data_table"]["rows"]
            if rows:
                numeric_values = []
                for row in rows:
                    if isinstance(row, dict):
                        for v in row.values():
                            if isinstance(v, (int, float)) and v != 0:
                                numeric_values.append(v)
                            elif isinstance(v, dict) and "value" in v:
                                val = v["value"]
                                if isinstance(val, (int, float)) and val != 0:
                                    numeric_values.append(val)
                    if numeric_values and all(v == 0 for v in numeric_values):
                        return False, "All table values are zero, expected non-zero values"

    # Also print the actual data for debugging
    if "data_table" in final:
        rows = final["data_table"].get("rows", [])
        print(f"   Actual rows returned: {len(rows)}")
        if len(rows) > 0:
            print(f"   First row: {json.dumps(rows[0], indent=4, ensure_ascii=False)}")

    return True, "OK"


def main():
    passed = 0
    failed = 0
    results = []

    print(f"🚀 Testing the 6 fixed problematic cases")
    print(f"📡 Backend URL: {BASE_URL}")
    print(f"🧪 Total test cases: {len(TEST_CASES)}\n")

    try:
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ Backend is reachable")
    except requests.exceptions.ConnectionError:
        print(f"❌ ERROR: Cannot connect to backend at {BASE_URL}")
        print("Please make sure the backend server is running")
        sys.exit(1)

    import time
    for test in TEST_CASES:
        start_time = time.time()
        try:
            print(f"\n{'='*70}")
            print(f"▶️ Running: {test['name']}")
            print(f"   Query: {test['query']}")
            session_id = create_session()
            result = send_message(session_id, test["query"])
            ok, msg = validate_result(result, test["expected"])
            elapsed = time.time() - start_time
            status_icon = "✅" if ok else "❌"
            print(f"{status_icon} {test['name']}")
            print(f"   Result: {'PASSED' if ok else 'FAILED'} - {msg}")
            print(f"   Time elapsed: {elapsed:.2f}s")

            if ok:
                passed += 1
            else:
                failed += 1

            results.append({
                "id": test["id"],
                "name": test["name"],
                "query": test["query"],
                "passed": ok,
                "message": msg,
                "elapsed": elapsed,
                "full_response": result,
            })

        except Exception as e:
            elapsed = time.time() - start_time
            status_icon = "❌"
            print(f"{status_icon} {test['name']}")
            print(f"   Result: FAILED - Exception: {str(e)}")
            print(f"   Time elapsed: {elapsed:.2f}s")
            failed += 1
            results.append({
                "id": test["id"],
                "name": test["name"],
                "query": test["query"],
                "passed": False,
                "message": f"Exception: {str(e)}",
                "elapsed": elapsed,
            })

    print(f"\n{'='*70}")
    print("📊 FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"Total: {len(TEST_CASES)}, Passed: {passed}, Failed: {failed}")
    print()

    # Save results to file
    with open("fixed_cases_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"📝 Full results saved to fixed_cases_results.json")
    print()

    if failed > 0:
        print("❌ Some tests FAILED:")
        for r in results:
            if not r["passed"]:
                print(f"  - {r['id']}. {r['name']}: {r['message']}")
        sys.exit(1)
    else:
        print("✅ ALL 6 TESTS PASSED!")
        sys.exit(0)


if __name__ == "__main__":
    main()
