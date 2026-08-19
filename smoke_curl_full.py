#!/usr/bin/env python3
"""
Full curl-based end-to-end smoke test for the CoT analysis API
Runs all 7 smoke test cases against the running backend server
"""
import requests
import json
import sys
from typing import Dict, Any, List, Tuple

BASE_URL = "http://localhost:8000"

# 定义全部7个测试用例
TEST_CASES = [
    {
        "id": 1,
        "name": "Test 1: Simple time trend (April)",
        "query": "id为6的广告主4月份的消耗趋势",
        "description": "4月份单指标时间趋势分析，预期返回一条非全零趋势线，25-35个数据点",
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
        "description": "带where过滤条件的实体表格分析，预期返回campaign列表，至少1条记录",
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
        "description": "带having过滤条件的实体表格分析，预期至少1条记录",
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
        "description": "周期对比分析，预期返回对比结果",
        "expected": {
            "success": True,
            "has_highlights": True,
        }
    },
    {
        "id": 5,
        "name": "Test 5: Audience distribution",
        "query": "广告主6 4月份的消耗按性别分布",
        "description": "受众分布分析，预期返回柱状图数据",
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
        "description": "带having过滤的多序列时间趋势分析，预期每个广告计划一条趋势线",
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
        "description": "核心KPI汇总分析，预期返回多个KPI卡片",
        "expected": {
            "success": True,
            "has_highlights": True,
        }
    },
]

def create_session() -> str:
    """Create a new chat session"""
    resp = requests.post(
        f"{BASE_URL}/api/sessions",
        json={"user_id": "smoke_test"},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()["session_id"]

def send_message(session_id: str, query: str, timeout: int = 180) -> Dict[str, Any]:
    """Send a message and get the final response"""
    resp = requests.post(
        f"{BASE_URL}/api/sessions/{session_id}/messages",
        json={"content": query},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()

def validate_result(result: Dict[str, Any], expected: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate the result against expected conditions"""
    # Result structure: {"status": "completed", "result": {...}}
    if "result" not in result:
        return False, "Missing 'result' in response"

    result_data = result["result"]

    if "final_report" not in result_data:
        # Check if there's an error
        if "warnings" in result_data and result_data["warnings"]:
            return False, f"Result has warnings: {result_data['warnings']}"
        return False, "Missing final_report in result"

    final = result_data["final_report"]

    if expected.get("success") is not None:
        # final_report.report_type == "success" means success
        report_type = final.get("report_type", "error")
        if expected["success"] and report_type != "success":
            error_msg = final.get("message", "Unknown error")
            return False, f"Expected success=True, got report_type={report_type}: {error_msg}"

    # Check data table for entity tables
    if expected.get("has_data_table"):
        if "data_table" not in final:
            return False, "Missing data_table in response"
        rows = final["data_table"].get("rows", [])
        min_rows = expected.get("min_rows", 1)
        if len(rows) < min_rows:
            return False, f"Expected at least {min_rows} rows, got {len(rows)}"

    # Check chart data for trends/charts
    if expected.get("has_chart_data"):
        if "chart_data" not in final:
            # For some reports, chart_data is in final_report
            if "chart_config" in final and "data" in final:
                pass  # okay
            else:
                return False, "Missing chart_data in response"
        if "chart_data" in final and "data" in final["chart_data"]:
            data = final["chart_data"]["data"]
            min_points = expected.get("min_data_points", 1)
            max_points = expected.get("max_points", 1000)
            if len(data) < min_points:
                return False, f"Expected at least {min_points} data points, got {len(data)}"
            if len(data) > max_points:
                return False, f"Expected at most {max_points} data points, got {len(data)}"

    # Check highlights
    if expected.get("has_highlights"):
        if "highlights" not in final:
            return False, "Missing highlights in response"
        if len(final["highlights"]) == 0:
            return False, "Expected at least one highlight, got none"

    # Check for all zero values (should fail if not allowed)
    if not expected.get("allow_all_zero", True):
        # Check chart data
        if "chart_data" in final and "data" in final["chart_data"]:
            data = final["chart_data"]["data"]
            if data:
                # Check if all numeric values are zero
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
        # Check data table
        if "data_table" in final and "rows" in final["data_table"]:
            rows = final["data_table"]["rows"]
            if rows:
                # Collect all numeric values
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

    # If we got here, all checks passed
    return True, "OK"

def print_result(test: Dict[str, Any], success: bool, message: str, elapsed: float):
    """Print formatted test result"""
    status_icon = "✅" if success else "❌"
    print(f"\n{'='*70}")
    print(f"{status_icon} {test['name']}")
    print(f"{'='*70}")
    print(f"Query: {test['query']}")
    print(f"Description: {test['description']}")
    print(f"Result: {'PASSED' if success else 'FAILED'} - {message}")
    print(f"Time elapsed: {elapsed:.2f}s")

def main():
    print(f"🚀 Starting full curl-based end-to-end smoke test")
    print(f"📡 Backend URL: {BASE_URL}")
    print(f"🧪 Total test cases: {len(TEST_CASES)}")
    print()

    # Check if backend is reachable
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ Backend is reachable")
    except requests.exceptions.ConnectionError:
        print(f"❌ ERROR: Cannot connect to backend at {BASE_URL}")
        print("Please make sure the backend server is running")
        sys.exit(1)

    # Run all tests - each test uses its own session
    passed = 0
    failed = 0
    results = []

    import time
    for test in TEST_CASES:
        start_time = time.time()
        try:
            session_id = create_session()
            result = send_message(session_id, test["query"])
            ok, msg = validate_result(result, test["expected"])
            elapsed = time.time() - start_time
            print_result(test, ok, msg, elapsed)

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
            print_result(test, False, f"Exception: {str(e)}", elapsed)
            failed += 1
            results.append({
                "id": test["id"],
                "name": test["name"],
                "query": test["query"],
                "passed": False,
                "message": f"Exception: {str(e)}",
                "elapsed": elapsed,
            })

    # Summary
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
