
#!/usr/bin/env python3
import requests
import json
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000"
TEST_CASES = [
    {
        "id": 1,
        "name": "Test 1: Simple time trend (April)",
        "query": "id为6的广告主4月份的消耗趋势",
        "expected": {
            "success": True,
            "min_data_points": 25,
            "max_data_points": 35,
            "has_chart_data": True,
            "allow_all_zero": False,
        }
    },
    {
        "id": 2,
        "name": "Test 2: Entity table with where filter",
        "query": "广告主6下未删除的广告计划4月份的消耗和点击",
        "expected": {
            "success": True,
            "min_rows": 1,
            "has_data_table": True,
            "allow_all_zero": False,
        }
    },
    {
        "id": 3,
        "name": "Test 3: Entity table with having filter",
        "query": "广告主6 4月份消耗大于10的广告计划有哪些",
        "expected": {
            "success": True,
            "min_rows": 1,
            "has_data_table": True,
            "allow_all_zero": False,
        }
    },
    {
        "id": 4,
        "name": "Test 4: Period comparison",
        "query": "广告主6 4月的消耗和3月比怎么样",
        "expected": {
            "success": True,
            "has_highlights": True,
        }
    },
    {
        "id": 5,
        "name": "Test 5: Audience distribution",
        "query": "广告主6 4月份的消耗按性别分布",
        "expected": {
            "success": True,
            "has_chart_data": True,
            "min_data_points": 1,
        }
    },
    {
        "id": 6,
        "name": "Test 6: Multi-series trend with having filter",
        "query": "广告主6 4月份消耗>10的广告计划的消耗趋势图",
        "expected": {
            "success": True,
            "has_chart_data": True,
            "min_data_points": 25,
        }
    },
    {
        "id": 7,
        "name": "Test 7: Summary (KPI cards)",
        "query": "广告主6 4月份的核心数据",
        "expected": {
            "success": True,
            "has_highlights": True,
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

    if expected.get("has_chart_data"):
        if "chart_data" not in final:
            if "chart_config" in final and "data" in final:
                pass
            else:
                return False, "Missing chart_data in response"
        if "chart_data" in final and "data" in final["chart_data"]:
            data = final["chart_data"]["data"]
            min_points = expected.get("min_data_points", 1)
            max_points = expected.get("max_data_points", 1000)
            if len(data) < min_points:
                return False, f"Expected at least {min_points} data points, got {len(data)}"
            if len(data) > max_points:
                return False, f"Expected at most {max_points} data points, got {len(data)}"

    if expected.get("has_highlights"):
        if "highlights" not in final:
            return False, "Missing highlights in response"
        if len(final["highlights"]) == 0:
            return False, "Expected at least one highlight, got none"

    if not expected.get("allow_all_zero", True):
        if "chart_data" in final and "data" in final["chart_data"]:
            data = final["chart_data"]["data"]
            if data:
                all_zero = True
                for point in data:
                    for k, v in point.items():
                        if k != "date" and isinstance(v, (int, float)) and v != 0:
                            all_zero = False
                            break
                    if not all_zero:
                        break
                if all_zero:
                    return False, "All data points are zero, expected non-zero values"
        if "data_table" in final and "rows" in final["data_table"]:
            rows = final["data_table"]["rows"]
            if rows:
                numeric_values = []
                for row in rows:
                    if isinstance(row, dict):
                        for v in row.values():
                            if isinstance(v, (int, float)):
                                numeric_values.append(v)
                            elif isinstance(v, dict) and "value" in v:
                                val = v["value"]
                                if isinstance(val, (int, float)):
                                    numeric_values.append(val)
                    if numeric_values and all(v == 0 for v in numeric_values):
                        return False, "All table values are zero, expected non-zero values"

    return True, "OK"

def main():
    passed = 0
    failed = 0
    results = []

    print(f"🚀 Starting full curl-based end-to-end smoke test")
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

    if failed > 0:
        print("❌ Some tests FAILED:")
        for r in results:
            if not r["passed"]:
                print(f"  - {r['id']}. {r['name']}: {r['message']}")
        sys.exit(1)
    else:
        print("✅ ALL TESTS PASSED!")
        sys.exit(0)

if __name__ == "__main__":
    main()
