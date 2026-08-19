#!/usr/bin/env python3
import requests
import json
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

TEST_CASES = [
    {
        "id": 9,
        "name": "模糊名称查询 - 包含digital + 排序",
        "query": "找出 digital_0 名称带 digital 的广告计划，按消耗排序",
        "expected": {
            "success": True,
            "min_rows": 1,
            "has_data_table": True,
            "allow_all_zero": False,
        }
    },
    {
        "id": 12,
        "name": "模糊查询 + 排序 + TopN - ad_group",
        "query": "在 digital_0 中找出名称包含六一八的所有广告组，按消耗降序排列前三",
        "expected": {
            "success": True,
            "min_rows": 1,
            "has_data_table": True,
            "allow_all_zero": False,
        }
    },
    {
        "id": 15,
        "name": "模糊名称查询 - creative",
        "query": "列出 digital_0 名称含尊享的所有创意及消耗",
        "expected": {
            "success": True,
            "min_rows": 1,
            "has_data_table": True,
            "allow_all_zero": False,
        }
    },
    {
        "id": 18,
        "name": "混合筛选 - status + 名称contains",
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
        "name": "混合筛选 - 名称 + having点击",
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
        "name": "Ad Group TopN - 点击率前五",
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
        "name": "Creative TopN - 转化率前三",
        "query": "广告主6转化率最高的三个创意",
        "expected": {
            "success": True,
            "min_rows": 1,
            "has_data_table": True,
            "allow_all_zero": False,
        }
    },
    {
        "id": 54,
        "name": "受众分布 - 操作系统占比",
        "query": "广告主6按不同操作系统看消耗占比",
        "expected": {
            "success": True,
            "min_data_points": 1,
            "has_chart_data": True,
            "allow_all_zero": False,
        }
    },
]

def create_session() -> str:
    resp = requests.post(
        f"{BASE_URL}/api/sessions",
        json={"user_id": "retest_test"},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()["session_id"]

def send_message(session_id: str, query: str, timeout: int = 300) -> Dict[str, Any]:
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
            if "error_type" in final and final.get("report_type") == "data_empty":
                return False, f"Got data_empty error: {final.get('message', 'empty result')}"
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
            if len(data) < min_points:
                return False, f"Expected at least {min_points} data points, got {len(data)}"

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
                    elif isinstance(row, dict) and "value" in row:
                        val = row["value"]
                        if isinstance(val, (int, float)):
                            numeric_values.append(val)
                if numeric_values and all(v == 0 for v in numeric_values):
                    return False, "All table values are zero, expected non-zero values"

    return True, "OK"

def main():
    passed = 0
    failed = 0
    results = []

    print(f"🚀 Retesting specific cases after cross_level_down fix\n")
    print(f"📡 Backend URL: {BASE_URL}\n")

    try:
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ Backend is reachable\n")
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
    print("📊 FINAL SUMMARY AFTER FIX")
    print(f"{'='*70}")
    print(f"Total: {len(TEST_CASES)}, Passed: {passed}, Failed: {failed}")
    print()

    if failed > 0:
        print("❌ Some tests FAILED:")
        for r in results:
            if not r["passed"]:
                print(f"  - Test {r['id']}: {r['name']}: {r['message']}")
    else:
        print("✅ ALL TESTS PASSED!")

    # Save results
    output_file = "/Users/simon/AL/DataAgent/retest_results_after_fix.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Results saved to {output_file}")

    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
