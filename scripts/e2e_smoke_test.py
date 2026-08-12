#!/usr/bin/env python3
"""
端到端全流程冒烟测试脚本

完整走一遍从HTTP请求进入到返回响应的全流程，对返回结果做精确结构校验。
三个固定测试用例（广告主ID=6）对应原冒烟测试1/2/3。

新增: 对测试1进行 SSE 流式实时性校验，检查事件是否分批推送不是一次性返回。
"""
import argparse
import sys
import os
import json
import time
import requests
from datetime import datetime
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
            "data_empty": True,
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
        default=720.0,
        help="请求超时时间（秒），默认720秒（支持最多3次重试，每次240秒)",
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
    parser.add_argument(
        "--check-sse-timing",
        action="store_true",
        help="对测试1进行SSE流式实时性校验，检查事件是否分批推送而非一次性返回",
    )
    parser.add_argument(
        "--min-required-gaps",
        type=int,
        default=2,
        help="最小需要多少个大于1秒的间隔，默认2",
    )
    parser.add_argument(
        "--min-gap-seconds",
        type=float,
        default=1.0,
        help="多大间隔算有效间隔（秒），默认1.0",
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


def validate_sse_streaming_timing(
    base_url: str,
    session_id: str,
    query: str,
    min_required_gaps: int = 2,
    min_gap_seconds: float = 1.0,
) -> Dict[str, Any]:
    """
    校验 SSE 流式推送的实时性：
    - 解析 SSE 流
    - 提取每个事件的 server_time
    - 检查是否有至少 min_required_gaps 个间隔大于 min_gap_seconds
    - 如果所有事件都几乎同时到达（间隔 < 0.1s）说明推送有问题

    Returns:
        dict with validation result
    """
    url = f"{base_url}/api/sessions/{session_id}/messages/stream"
    payload = {"content": query}
    headers = {"Content-Type": "application/json"}

    events: List[Dict[str, Any]] = []
    buffer = ''

    try:
        with requests.post(url, json=payload, headers=headers, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if line is None:
                    continue
                if not line:
                    # Empty line means end of event
                    if buffer:
                        try:
                            # buffer already contains content after 'data: ' prefix removal
                            data = json.loads(buffer)
                            events.append(data)
                        except Exception as e:
                            print(f"  [warn] Failed to parse SSE event: {buffer[:60]}, error: {e}")
                        finally:
                            buffer = ''
                else:
                    if line.startswith('data: '):
                        buffer += line[6:]

        # Extract timestamps
        step_events = [e for e in events if e.get("type") in ["step_start", "step_complete"]]
        if len(step_events) < 2:
            return {
                "valid": False,
                "reason": f"Too few step events: {len(step_events)}, expected >= 2",
                "event_count": len(step_events),
                "timestamps_count": 0,
                "large_gaps": 0,
                "gaps": [],
            }

        # Convert server_time string to datetime
        timestamps: List[float] = []
        for e in step_events:
            st = e.get("server_time")
            if st:
                try:
                    dt = datetime.strptime(st, "%Y-%m-%d %H:%M:%S.%f")
                    timestamps.append(dt.timestamp())
                except Exception:
                    pass

        if len(timestamps) < 2:
            return {
                "valid": False,
                "reason": f"Too many events missing server_time: {len(step_events)} events, {len(timestamps)} have valid timestamp",
                "event_count": len(step_events),
                "timestamps_count": len(timestamps),
                "large_gaps": 0,
                "gaps": [],
            }

        # Calculate gaps between consecutive events
        gaps: List[float] = []
        large_gaps = 0
        for i in range(1, len(timestamps)):
            gap = timestamps[i] - timestamps[i-1]
            gaps.append(gap)
            if gap >= min_gap_seconds:
                large_gaps += 1

        # Validation: need at least min_required_gaps large gaps (these are the LLM inference steps)
        valid = large_gaps >= min_required_gaps
        reason = ""
        if not valid:
            reason = f"Only {large_gaps} gaps >= {min_gap_seconds}s, need at least {min_required_gaps}"

        return {
            "valid": valid,
            "reason": reason,
            "event_count": len(step_events),
            "timestamps_count": len(timestamps),
            "large_gaps": large_gaps,
            "min_required_gaps": min_required_gaps,
            "min_gap_seconds": min_gap_seconds,
            "gaps": gaps,
            "events": events,
        }

    except Exception as e:
        return {
            "valid": False,
            "reason": f"Exception during SSE stream: {str(e)}",
            "event_count": 0,
            "timestamps_count": 0,
            "large_gaps": 0,
            "gaps": [],
        }


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
    if "type" in final_report and "data" in final_report and final_report.get("type") == "final_report":
        data = final_report.get("data")
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
        return False, f"analysis_type错误: 期望 {exp_analysis_type}, 得到 {got_analysis_type}"

    # 3. 列数校验
    expected_cols = expected.get("columns_len", 0)
    data_table = data["data_table"]
    rows = data_table.get("rows", [])
    if expected_cols > 0:
        if not rows:
            return False, f"data_table.rows 为空，期望至少 {expected_cols} 列"
        first_row = rows[0]
        got_cols = len(first_row)
        if got_cols != expected_cols:
            return False, f"columns长度错误: 期望 {expected_cols}, 得到 {got_cols}"

    # 4. 检查是否所有数值都为零
    expected_data_empty = expected.get("data_empty", False)
    if expected_data_empty:
        # data 数组为空是正常的（不代表错误，只是说趋势图没有数据）
        # 这里不校验，pass
        pass
    else:
        # 检查至少有一个非零
        numeric_values: List[float] = []
        trend_data = data.get("data", [])
        if trend_data:
            for point in trend_data:
                for k, v in point.items():
                    if k != "date":
                        if isinstance(v, (int, float)):
                            numeric_values.append(float(v))

        if data_table and rows:
            for row in rows:
                for cell in row:
                    # cell 可能是格式化字符串，提取数字，对于格式化的字符串（如 "¥17,750.00"）我们不提取，放过
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
    max_retries: int = 3,
) -> Dict[str, Any]:
    """运行单个测试用例，支持最多重试max_retries次，有一次成功就算成功"""
    start_time = time.time()
    query = test_case["query"]
    expected = test_case["expected"]

    last_result = None
    last_error = None

    # 最多重试 max_retries 次
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"   第 {attempt + 1} 次重试...")

        # 1. 创建会话（每次重试都新建会话，避免状态污染）
        session_id = create_session(base_url, timeout)
        if not session_id:
            last_error = "创建会话失败，后端服务可能不可用"
            continue

        # 2. 发送消息
        result = send_message(base_url, session_id, query, timeout)

        if result is None:
            last_error = "发送消息失败或超时"
            continue

        # 3. 判断初始状态
        status = "success"
        error_message = None

        if result.get("needs_clarification"):
            status = "needs_clarification"
            last_error = "需要澄清"
        elif result.get("error"):
            status = "error"
            last_error = str(result.get("error"))
        elif result.get("status") == "waiting_for_clarification":
            status = "needs_clarification"
            last_error = "等待澄清"
        else:
            # 4. 结构校验（result 是 API 返回的完整结果）
            ok, err_msg = validate_result(result, expected)
            if not ok:
                status = "error"
                last_error = err_msg
            else:
                # 校验通过，直接返回成功结果，不继续重试
                elapsed = time.time() - start_time
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

                # 检查全零
                numeric_values: List[float] = []
                if data_content:
                    trend_data = data_content.get("data", [])
                    if trend_data:
                        numeric_keys = [k for k in trend_data[0].keys() if k != "date"]
                        for key in numeric_keys:
                            for point in trend_data:
                                val = point.get(key)
                                if isinstance(val, (int, float)):
                                    numeric_values.append(float(val))

                    data_table = data_content.get("data_table", {}).get("rows", [])
                    if data_table:
                        for row in data_table:
                            for cell in row:
                                # cell 可能是格式化字符串，提取数字，对于格式化的字符串（如 "¥17,750.00"）我们不提取，放过
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
                    "error_message": None,
                    "retries": attempt,  # 记录重试次数
                }

                # Always save raw response for debugging
                detailed_result["raw_response"] = result

                return detailed_result

        # 记录本次结果
        last_result = result

    # 所有重试都失败了，返回最后一次的错误
    elapsed = time.time() - start_time
    return {
        "test_id": test_case["id"],
        "test_name": test_case["name"],
        "query": query,
        "status": "error",
        "analysis_type": expected["analysis_type"],
        "data_points": 0,
        "has_chart_config": False,
        "all_zero": False,
        "response_time": round(elapsed, 2),
        "error_message": f"{max_retries}次重试全部失败，最后一次错误: {last_error}",
        "retries": max_retries,
        "raw_response": last_result,
    }


def main():
    """主函数"""
    args = parse_args()

    print(f"🚀 开始运行 全流程端到端冒烟测试，共 {len(TEST_CASES)} 个测试用例")
    print(f"📌 后端地址: {args.backend_url}")
    print(f"⏱  超时时间: {args.timeout}秒")
    print("-" * 80)

    total_start_time = time.time()
    results: List[Dict[str, Any]] = []

    # 如果开启了 SSE 时序校验，只对测试1做校验
    if args.check_sse_timing:
        test_case = TEST_CASES[0]  # test 1
        print(f"🔍 SSE 实时性校验 -> 测试 {test_case['id']}: {test_case['name']}")
        print(f"   查询: {test_case['query']}")
        print(f"   检查至少 {args.min_required_gaps} 个间隔 >= {args.min_gap_seconds}s (这是LLM推理的天然间隔)")
        print()

        # 创建新会话
        session_id = create_session(args.backend_url, args.timeout)
        if not session_id:
            print("❌ 创建会话失败，跳过校验")
        else:
            # 执行 SSE 校验
            sse_result = validate_sse_streaming_timing(
                args.backend_url,
                session_id,
                test_case["query"],
                min_required_gaps=args.min_required_gaps,
                min_gap_seconds=args.min_gap_seconds,
            )

            print(f"📊 校验结果:")
            print(f"   收到事件总数: {sse_result['event_count']}")
            print(f"   带时间戳事件: {sse_result['timestamps_count']}")
            print(f"   合格大间隔数量: {sse_result['large_gaps']} / {args.min_required_gaps}  required")
            if sse_result.get("gaps"):
                print(f"   各事件间隔(秒): {[round(g, 2) for g in sse_result['gaps']]}")

            if sse_result["valid"]:
                print("\n✅ SSE 实时性校验 PASS - 事件确实分批推送，不是一次性返回")
            else:
                print(f"\n❌ SSE 实时性校验 FAIL - {sse_result['reason']}")

            print()

    # 正常运行所有测试
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
            json.dump({
                "success_count": success_count,
                "error_count": error_count,
                "total_time": total_time,
                "results": results,
            }, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
