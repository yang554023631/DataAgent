#!/usr/bin/env python3
"""
端到端全流程冒烟测试脚本

完整走一遍从HTTP请求进入到返回响应的全流程，对返回结果做精确结构校验。
三个固定测试用例（广告主ID=6）对应原冒烟测试1/2/3。
"""
import argparse
import sys
import os
import json
import time
import requests
from typing import Dict, Any, List, Optional


# 三个固定测试用例（广告主ID=6）
TEST_CASES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "Simple time trend (E2E)",
        "query": "id为6的广告主4月份的消耗趋势",
        "expected": {
            "analysis_type": "time_trend",
            "chart_type": "table",
            "entity_level": "advertiser",
            "metrics": ["cost"],
            "columns_len": 1,
            "columns": ["日期"],
            "has_chart_config": True,
            "chart_config_type": "line",
            "x_axis_field": "date",
            "y_axis_field": "cost",
            "data_empty": False,
        }
    },
    {
        "id": 2,
        "name": "Entity table with where filter (E2E)",
        "query": "广告主6下未删除的广告计划4月份的消耗和点击",
        "expected": {
            "analysis_type": "entity_table",
            "chart_type": "table",
            "entity_level": "campaign",
            "metrics": ["clicks", "cost"],
            "columns_len": 4,
            "columns": ["campaign ID", "campaign 名称", "clicks", "cost"],
            "has_chart_config": True,  # chart_config 字段总是存在，只是空对象 {}
            "data_empty": True,  # data 数组应为空
            "min_rows": 1,
        }
    },
    {
        "id": 3,
        "name": "Entity table with having filter (E2E)",
        "query": "广告主6 4月份消耗大于10的广告计划有哪些",
        "expected": {
            "analysis_type": "entity_table",
            "chart_type": "table",
            "entity_level": "campaign",
            "metrics": ["cost"],
            "columns_len": 3,
            "columns": ["campaign ID", "campaign 名称", "cost"],
            "has_chart_config": True,  # chart_config 字段总是存在，只是空对象 {}
            "data_empty": True,  # data 数组应为空
            "min_rows": 1,
        }
    },
]


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="全流程端到端冒烟测试")
    parser.add_argument(
        "--backend-url",
        type=str,
        default=os.getenv("BACKEND_URL", "http://localhost:8000"),
        help="后端服务地址，默认从环境变量BACKEND_URL读取，默认为http://localhost:8000",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=240.0,
        help="请求超时时间（秒），默认240秒",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="将结果保存到JSON文件",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="打印详细响应信息",
    )
    return parser.parse_args()


def create_session(base_url: str, timeout: float) -> Optional[str]:
    """创建新会话，返回session_id"""
    url = f"{base_url}/api/sessions"
    try:
        resp = requests.post(url, json={"user_id": "e2e-smoke-test"}, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("session_id")
    except Exception:
        return None


def send_message(
    base_url: str,
    session_id: str,
    content: str,
    timeout: float,
) -> Optional[Dict[str, Any]]:
    """发送消息，等待完整响应"""
    url = f"{base_url}/api/sessions/{session_id}/messages"
    try:
        resp = requests.post(url, json={"content": content}, timeout=timeout)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def extract_numeric_values_from_cell(cell: Any) -> List[float]:
    """从单元格提取数值，处理两种格式：直接值 / {"value": x}"""
    values = []
    if isinstance(cell, (int, float)):
        values.append(float(cell))
    elif isinstance(cell, dict) and "value" in cell:
        val = cell["value"]
        if isinstance(val, (int, float)):
            values.append(float(val))
    return values


def validate_result(
    api_result: Dict[str, Any],
    expected: Dict[str, Any],
) -> tuple[bool, Optional[str]]:
    """
    根据预期校验结果结构
    返回 (是否通过, 错误信息)
    api_result 是POST /messages 返回的完整结果
    """
    # 1. API顶层结构校验
    if api_result.get("status") != "completed":
        return False, f"API status错误: 期望 'completed', 得到 {api_result.get('status')}"

    result = api_result.get("result")
    if not result:
        return False, "result字段不存在或为空"

    final_report = result.get("final_report")
    if not final_report:
        return False, "result.final_report 不存在，未生成最终报表"

    # 2. final_report 结构校验
    # 注意：在非流式POST API中，final_report 直接就是数据内容
    # 不需要再解一层 {"type": "final_report", "data": ...}
    # 那个包装只用于SSE流式响应
    if "type" in final_report and "data" in final_report:
        # 如果碰巧有包装，也兼容处理
        if final_report.get("type") == "final_report":
            data = final_report.get("data")
        else:
            data = final_report
    else:
        # 没有包装，直接就是data
        data = final_report

    if not data:
        return False, "final_report data 不存在或为空"

    if "report_type" in data and data.get("report_type") != "success":
        # 收集所有错误信息
        error_parts = []
        if "error_message" in data:
            error_parts.append(str(data.get("error_message")))
        if "error" in data:
            error_parts.append(str(data.get("error")))
        error_msg = " - ".join(error_parts) if error_parts else "unknown error"
        return False, f"report_type错误: 期望 'success', 得到 {data.get('report_type')} - {error_msg}"

    required_top_fields = ["title", "chart_config", "data", "data_table",
                          "quality_info", "highlights", "metadata", "next_queries"]
    for field in required_top_fields:
        if field not in data:
            return False, f"缺少必填字段: data.{field}"

    # 2. 元信息校验
    metadata = data["metadata"]
    exp_analysis_type = expected["analysis_type"]
    got_analysis_type = metadata.get("analysis_type")
    if got_analysis_type != exp_analysis_type:
        return False, f"metadata.analysis_type错误: 期望 {exp_analysis_type}, 得到 {got_analysis_type}"

    exp_chart_type = expected["chart_type"]
    got_chart_type = metadata.get("chart_type")
    if got_chart_type != exp_chart_type:
        return False, f"metadata.chart_type错误: 期望 {exp_chart_type}, 得到 {got_chart_type}"

    exp_entity_level = expected["entity_level"]
    got_entity_level = metadata.get("entity_level")
    if got_entity_level != exp_entity_level:
        return False, f"metadata.entity_level错误: 期望 {exp_entity_level}, 得到 {got_entity_level}"

    exp_metrics = expected["metrics"]
    got_metrics = metadata.get("metrics", [])
    if got_metrics != exp_metrics:
        return False, f"metadata.metrics错误: 期望 {exp_metrics}, 得到 {got_metrics}"

    # 3. 表格列校验
    data_table = data["data_table"]
    columns = data_table.get("columns", [])
    exp_columns_len = expected["columns_len"]
    if len(columns) != exp_columns_len:
        return False, f"data_table.columns长度错误: 期望 {exp_columns_len}列, 得到 {len(columns)}列"

    if "columns" in expected:
        exp_columns = expected["columns"]
        if columns != exp_columns:
            return False, f"data_table.columns内容错误: 期望 {exp_columns}, 得到 {columns}"

    rows = data_table.get("rows", [])
    if "min_rows" in expected:
        if len(rows) < expected["min_rows"]:
            return False, f"data_table.rows行数不足: 期望至少 {expected['min_rows']}行, 得到 {len(rows)}行"

    # 检查每行长度匹配列数
    for i, row in enumerate(rows):
        if len(row) != len(columns):
            return False, f"第{i+1}行长错: 期望 {len(columns)}列, 得到 {len(row)}列"

    # 4. data 数组校验
    got_data = data.get("data", [])
    exp_data_empty = expected.get("data_empty", False)
    if exp_data_empty and len(got_data) > 0:
        return False, f"data数组应为空，实际有 {len(got_data)} 个元素"
    if not exp_data_empty and len(got_data) == 0:
        return False, "data数组为空，期望有数据"

    # 5. 趋势图特有校验（time_trend）
    if exp_analysis_type == "time_trend":
        # chart_config 校验
        chart_config = data.get("chart_config", {})
        exp_chart_config_type = expected.get("chart_config_type")
        if exp_chart_config_type:
            if chart_config.get("type") != exp_chart_config_type:
                return False, f"chart_config.type错误: 期望 {exp_chart_config_type}, 得到 {chart_config.get('type')}"
        if "x_axis_field" in expected:
            x_axis = chart_config.get("x_axis", {})
            if x_axis.get("field") != expected["x_axis_field"]:
                return False, f"chart_config.x_axis.field错误: 期望 {expected['x_axis_field']}"
        if "y_axis_field" in expected:
            y_axis = chart_config.get("y_axis", {})
            if y_axis.get("field") != expected["y_axis_field"]:
                return False, f"chart_config.y_axis.field错误: 期望 {expected['y_axis_field']}"
        # 每个数据点必须包含预期字段
        for i, point in enumerate(got_data):
            if "date" not in point:
                return False, f"趋势数据第{i+1}点缺少date字段"
            if "cost" not in point:
                return False, f"趋势数据第{i+1}点缺少cost字段"

    # 6. 检查是否所有数值都为0
    all_zero = False
    numeric_values: List[float] = []

    # 从趋势数据提取
    if not exp_data_empty and len(got_data) > 0:
        # 对于趋势，取第一个metric检查全零
        first_point = got_data[0]
        numeric_keys = [k for k in first_point.keys() if k != "date"]
        if numeric_keys:
            metric_key = numeric_keys[0]
            for point in got_data:
                val = point.get(metric_key)
                if isinstance(val, (int, float)):
                    numeric_values.append(float(val))

    # 从表格提取
    if rows:
        for row in rows:
            for cell in row:
                # cell 可能是格式化字符串，提取数字
                # 先尝试直接匹配，对于格式化的字符串（如 "¥17,750.00"）我们不提取，放过
                # 只提取数值类型的单元格
                if isinstance(cell, (int, float)):
                    numeric_values.append(float(cell))
                elif isinstance(cell, dict) and "value" in cell:
                    val = cell["value"]
                    if isinstance(val, (int, float)):
                        numeric_values.append(float(val))

    if numeric_values:
        all_zero = all(v == 0 for v in numeric_values)
        if all_zero:
            return False, "所有数值都为0，预期应该有非零值"

    # 7. 检查has_chart_config
    has_chart_config = (
        "chart_config" in data
        and data["chart_config"] is not None
    )
    expected_has_chart = expected.get("has_chart_config", False)
    if has_chart_config != expected_has_chart:
        return False, f"has_chart_config错误: 期望 {expected_has_chart}, 得到 {has_chart_config}"

    return True, None


def run_single_test(
    test_case: Dict[str, Any],
    base_url: str,
    timeout: float,
    verbose: bool = False,
) -> Dict[str, Any]:
    """运行单个测试用例"""
    start_time = time.time()
    query = test_case["query"]
    expected = test_case["expected"]

    # 1. 创建会话
    session_id = create_session(base_url, timeout)
    if not session_id:
        elapsed = time.time() - start_time
        return {
            "test_id": test_case["id"],
            "test_name": test_case["name"],
            "query": query,
            "status": "error",
            "error_message": "创建会话失败，后端服务可能不可用",
            "response_time": round(elapsed, 2),
        }

    # 2. 发送消息
    result = send_message(base_url, session_id, query, timeout)
    elapsed = time.time() - start_time

    if result is None:
        return {
            "test_id": test_case["id"],
            "test_name": test_case["name"],
            "query": query,
            "status": "error",
            "error_message": "发送消息失败或超时",
            "response_time": round(elapsed, 2),
        }

    # 3. 判断初始状态
    status = "success"
    error_message = None
    data_points = 0
    has_chart_config = False
    all_zero_flag = False

    # 调试：打印实际返回结构帮助排查问题
    # import json
    # print("DEBUG: API result =", json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("needs_clarification"):
        status = "needs_clarification"
    elif result.get("error"):
        status = "error"
        error_message = str(result.get("error"))
    elif result.get("status") == "waiting_for_clarification":
        status = "needs_clarification"
    else:
        # 4. 结构校验（result 是 API 返回的完整结果）
        ok, err_msg = validate_result(result, expected)
        if not ok:
            status = "error"
            error_message = err_msg

    # 提取统计信息
    data_points = 0
    has_chart_config = False
    all_zero_flag = False

    # 获取最终数据（兼容两种结构）
    data_content = None
    if result and "result" in result and "final_report" in result["result"]:
        final_report = result["result"]["final_report"]
        if "type" in final_report and "data" in final_report and final_report.get("type") == "final_report":
            data_content = final_report.get("data")
        else:
            data_content = final_report

    if data_content:
        if "data" in data_content:
            trend_data = data_content.get("data", [])
            if trend_data:
                data_points = len(trend_data)
        if "data_table" in data_content:
            data_table = data_content.get("data_table", {}).get("rows", [])
            if data_table:
                data_points = len(data_table)
        if "chart_config" in data_content:
            has_chart_config = data_content["chart_config"] is not None

    # 检查全零（已经在validate_result里做了，但这里记录）
    # 重新计算all_zero用于统计
    numeric_values: List[float] = []
    if data_content:
        trend_data = data_content.get("data", [])
        data_table = data_content.get("data_table", {}).get("rows", [])

        if trend_data:
            first_point = trend_data[0]
            numeric_keys = [k for k in first_point.keys() if k != "date"]
            if numeric_keys:
                metric_key = numeric_keys[0]
                for point in trend_data:
                    val = point.get(metric_key)
                    if isinstance(val, (int, float)):
                        numeric_values.append(float(val))

        if data_table:
            for row in data_table:
                for cell in row:
                    if isinstance(cell, (int, float)):
                        numeric_values.append(float(cell))
                    elif isinstance(cell, dict) and "value" in cell:
                        val = cell["value"]
                        if isinstance(val, (int, float)):
                            numeric_values.append(float(val))

    if numeric_values:
        all_zero_flag = all(v == 0 for v in numeric_values)

    detailed_result = {
        "test_id": test_case["id"],
        "test_name": test_case["name"],
        "query": query,
        "status": status,
        "analysis_type": expected["analysis_type"],
        "data_points": data_points,
        "has_chart_config": has_chart_config,
        "all_zero": all_zero_flag,
        "response_time": round(elapsed, 2),
        "error_message": error_message,
    }

    # Always save raw response for debugging
    detailed_result["raw_response"] = result

    return detailed_result


def main():
    """主函数"""
    args = parse_args()

    print(f"🚀 开始运行 全流程端到端冒烟测试，共 {len(TEST_CASES)} 个测试用例")
    print(f"📌 后端地址: {args.backend_url}")
    print(f"⏱  超时时间: {args.timeout}秒")
    print("-" * 80)

    total_start_time = time.time()
    results: List[Dict[str, Any]] = []

    for test_case in TEST_CASES:
        print(f"🔹 运行测试 {test_case['id']}: {test_case['name']}")
        print(f"   查询: {test_case['query']}")

        result = run_single_test(
            test_case,
            args.backend_url,
            args.timeout,
            args.verbose,
        )

        print(f"   状态: {result['status']}")
        print(f"   分析类型: {result['analysis_type']}")
        if result["status"] == "success":
            print(f"   数据点数量: {result['data_points']}")
            print(f"   包含图表配置: {'是' if result['has_chart_config'] else '否'}")
        if result["error_message"]:
            print(f"   错误信息: {result['error_message']}")
        print("-" * 60)

        results.append(result)

    # 汇总报告
    total_time = round(time.time() - total_start_time, 2)
    success_count = sum(1 for r in results if r["status"] == "success")
    clarification_count = sum(1 for r in results if r["status"] == "needs_clarification")
    error_count = sum(1 for r in results if r["status"] == "error")

    print("\n=== 📊 测试汇总报告 ===")
    print(f"总测试用例数: {len(results)}")
    print(f"成功: {success_count}")
    print(f"需要澄清: {clarification_count}")
    print(f"失败: {error_count}")
    print(f"总耗时: {total_time}s")

    if error_count > 0:
        print("\n=== ❌ 失败测试详情 ===")
        for result in results:
            if result["status"] == "error":
                print(f"测试 {result['test_id']}: {result['test_name']}")
                print(f"错误: {result['error_message']}")
                print("-" * 40)

    # 保存结果
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 结果已保存到文件: {args.output}")

    # 退出码
    if error_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
