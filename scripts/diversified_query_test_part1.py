#!/usr/bin/env python3
"""
多样化自然语言Query测试脚本 - Part 1 (ID 1-30)

运行我们构造的60个多样化query，分为两部分并行跑提高效率。
"""
import argparse
import sys
import os
import json
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

# 添加 backend 目录到 Python 路径（确保 src 能被找到）
# 整个项目所有代码都是 import src.xxx，而 src 文件夹就在 backend 目录下
script_dir = Path(__file__).parent
backend_dir = script_dir / "../backend"
sys.path.insert(0, str(backend_dir.resolve()))

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("警告: python-dotenv 未安装，将使用系统环境变量")

# 检查必要的环境变量
required_env_vars = [
    "ES_URL",
    "LLM_API_KEY",
    "LLM_ENDPOINT"
]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    print("❌ 错误: 缺少必要的环境变量:")
    for var in missing_vars:
        print(f"  - {var}")
    print("请设置这些环境变量或在 .env 文件中配置")
    sys.exit(2)

# 定义60个多样化测试用例（来自 docs/test_cases/diversified_nl_queries.md）
# 此文件包含 Part 1: ID 1-30
DIVERSIFIED_TEST_CASES: List[Dict[str, Any]] = [
    # 一、按名称查询场景（真实名称）
    {
        "id": 1,
        "name": "按广告主名称查询 - 趋势",
        "query": "帮我看一下名称是 digital_0 的广告主四月份消耗趋势",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "advertiser",
        "prediction": "可能失败",
        "prediction_reason": "首次按名称筛选",
    },
    {
        "id": 2,
        "name": "按广告主名称查询 - 最近七天概览",
        "query": "查询广告主 digital_0 最近七天的数据概览（截止到4月27日）",
        "expected_analysis_type": "summary",
        "expected_target_level": "advertiser",
        "prediction": "可能失败",
        "prediction_reason": "按名称筛选 + 相对时间",
    },
    {
        "id": 3,
        "name": "按广告主名称查询 - 三月汇总",
        "query": "给我广告主 digital_0 三月份的曝光、点击、消耗汇总",
        "expected_analysis_type": "summary",
        "expected_target_level": "advertiser",
        "prediction": "可能失败",
        "prediction_reason": "按名称筛选",
    },
    {
        "id": 4,
        "name": "跨层级名称查询 - campaign",
        "query": "在广告主 digital_0 下找出叫 summer_mini 的广告计划四月份消耗",
        "expected_analysis_type": "summary",
        "expected_target_level": "campaign",
        "prediction": "预期成功",
        "prediction_reason": "单个campaign四月份消耗，用summary，修复后应该成功",
    },
    {
        "id": 5,
        "name": "两层名称查询 - 趋势",
        "query": "广告主 digital_0 中，尊享_50 这个广告计划四月份消耗趋势",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "campaign",
        "prediction": "可能失败",
        "prediction_reason": "两层名称筛选",
    },
    {
        "id": 6,
        "name": "两层名称查询 - 最近七天趋势",
        "query": "广告主 digital_0 的 短视频_g73 最近七天消耗变化曲线",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "campaign",
        "prediction": "很可能失败",
        "prediction_reason": "两层名称筛选",
    },
    {
        "id": 7,
        "name": "两层名称查询 - 总点击",
        "query": "给我广告主 digital_0 的 旗舰43_best 四月份总点击",
        "expected_analysis_type": "summary",
        "expected_target_level": "campaign",
        "prediction": "预期成功",
        "prediction_reason": "单个campaign总点击，用summary",
    },
    {
        "id": 8,
        "name": "模糊名称查询 - 包含mini",
        "query": "广告主 digital_0 下面名称包含 mini 的所有广告计划列出四月份消耗",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
        "prediction": "很可能失败",
        "prediction_reason": "模糊匹配contains",
    },
    {
        "id": 9,
        "name": "模糊名称查询 - 包含digital + 排序",
        "query": "找出广告主 digital_0 名称带 digital 的广告计划，按消耗排序",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
        "prediction": "很可能失败",
        "prediction_reason": "模糊匹配 + 排序",
    },
    {
        "id": 10,
        "name": "模糊名称查询 - 包含下划线",
        "query": "广告主 digital_0 下名称中包含下划线的广告计划四月份点击汇总",
        "expected_analysis_type": "summary",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "查询汇总总点击，用summary，修复后应该成功",
    },
    {
        "id": 11,
        "name": "两层名称查询 - ad_group",
        "query": "广告主 digital_0 下 精选六一八0 这个广告组四月份消耗是多少",
        "expected_analysis_type": "summary",
        "expected_target_level": "ad_group",
        "prediction": "预期成功",
        "prediction_reason": "单个ad_group总消耗，用summary",
    },
    {
        "id": 12,
        "name": "模糊查询 + 排序 + TopN - ad_group",
        "query": "在广告主 digital_0 中找出名称包含六一八的所有广告组，按消耗降序排列前三",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "ad_group",
        "prediction": "很可能失败",
        "prediction_reason": "模糊匹配 + 排序 + TopN，组合复杂",
    },
    {
        "id": 13,
        "name": "两层名称查询 - ad_group点击率",
        "query": "广告主 digital_0 的广告组 mini_045 四月份点击率是多少",
        "expected_analysis_type": "summary",
        "expected_target_level": "ad_group",
        "prediction": "预期成功",
        "prediction_reason": "单个ad_group点击率，用summary，修复后应该成功",
    },
    {
        "id": 14,
        "name": "三层名称查询 - creative",
        "query": "广告主 digital_0 下 冬季粉丝_3_zs14 这个创意四月份获得多少点击",
        "expected_analysis_type": "summary",
        "expected_target_level": "creative",
        "prediction": "预期成功",
        "prediction_reason": "单个creative总点击，用summary",
    },
    {
        "id": 15,
        "name": "模糊名称查询 - creative",
        "query": "列出广告主 digital_0 名称含尊享的所有创意及消耗",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "creative",
        "prediction": "很可能失败",
        "prediction_reason": "模糊匹配 + 名称筛选",
    },
    {
        "id": 16,
        "name": "三层名称查询 - creative转化率",
        "query": "广告主 digital_0 的创意 专场美妆_513 四月份转化率是多少",
        "expected_analysis_type": "summary",
        "expected_target_level": "creative",
        "prediction": "预期成功",
        "prediction_reason": "单个creative转化率，用summary，修复后应该成功",
    },
    {
        "id": 17,
        "name": "混合筛选 - where名称 + having消耗",
        "query": "广告主 digital_0 中名称包含 summer 而且四月份消耗大于100的广告计划有哪些",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
        "prediction": "很可能失败",
        "prediction_reason": "where+having双条件混合",
    },
    {
        "id": 18,
        "name": "混合筛选 - status + 名称contains",
        "query": "广告主 digital_0 投放中的广告计划，名称含有 best，列出消耗和点击",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
        "prediction": "很可能失败",
        "prediction_reason": "where双条件混合筛选",
    },
    {
        "id": 19,
        "name": "混合筛选 - 名称 + having点击",
        "query": "找出广告主 digital_0 下名称含 mini 的创意，点击量大于50",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "creative",
        "prediction": "很可能失败",
        "prediction_reason": "where名称 + having点击混合",
    },
    {
        "id": 20,
        "name": "广告主名称周期对比",
        "query": "广告主 digital_0 四月份消耗对比三月份",
        "expected_analysis_type": "period_comparison",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "按广告主名称查询对比",
    },
    {
        "id": 21,
        "name": "广告主名称点击趋势",
        "query": "广告主 digital_0 四月份点击数据趋势图",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "advertiser",
        "prediction": "可能失败",
        "prediction_reason": "按广告主名称查询趋势",
    },
    {
        "id": 22,
        "name": "其他广告主名称子层级表格",
        "query": "广告主 autumn_145_beauty 四月份各个广告计划消耗表格",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
        "prediction": "可能失败",
        "prediction_reason": "按广告主名称查询子层级表格",
    },
    {
        "id": 23,
        "name": "ID多样化 - 六号广告主四月趋势",
        "query": "六号广告主四月份每天花多少钱，给我看趋势",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "结构清晰，只是换说法",
    },
    {
        "id": 24,
        "name": "ID多样化 - 广告主ID为6四月曲线",
        "query": "帮我画一下广告主ID为6的四月消耗曲线",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "结构清晰",
    },
    {
        "id": 25,
        "name": "ID多样化 - 语序变化",
        "query": "四月份，广告主6的消耗是怎么变化的",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "只是换语序，关键词都在",
    },
    {
        "id": 26,
        "name": "ID多样化 - 不同措辞",
        "query": "广告主ID等于6，四月份消耗趋势",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "关键词都全",
    },
    {
        "id": 27,
        "name": "ID多series多样化 - 分开画",
        "query": "把广告主6下面每个广告计划四月份消耗趋势分开画出来",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "campaign",
        "prediction": "预期成功",
        "prediction_reason": "原e2e测试6，结构清晰",
    },
    {
        "id": 28,
        "name": "ID多series多样化 - 一条折线",
        "query": "广告主6，每个计划一条折线看四月份每日消耗",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "campaign",
        "prediction": "可能失败",
        "prediction_reason": "\"一条折线\"表述口语，原案例没有",
    },
    {
        "id": 29,
        "name": "ID多series多样化 - 走势",
        "query": "分开展示广告主6各广告计划四月消耗走势",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "campaign",
        "prediction": "可能失败",
        "prediction_reason": "\"走势\"是新词",
    },
    {
        "id": 30,
        "name": "ID多series多样化 - 消耗变化",
        "query": "广告主6各计划分开看四月份消耗变化",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "campaign",
        "prediction": "可能失败",
        "prediction_reason": "表述方式不同",
    },
]

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="多样化自然语言Query测试 - Part 1 (ID 1-30)")
    parser.add_argument(
        "--tests",
        type=str,
        help="指定要运行的测试ID，逗号分隔，例如 1,2,3"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="每个query最多重试次数（默认2次：1次初始+1次重试）"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="打印详细信息"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="diversified_test_results_part1.json",
        help="将结果保存到JSON文件（默认: diversified_test_results_part1.json）"
    )
    return parser.parse_args()

async def run_single_test(
    test_case: Dict[str, Any],
    max_retries: int = 2,
    verbose: bool = False
) -> Dict[str, Any]:
    """运行单个测试用例，支持最多重试max_retries次"""
    query = test_case["query"]
    total_start_time = time.time()

    last_result = None
    last_error = None

    # 最多重试 max_retries 次（用户要求：最多2次，成功就停止）
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"   第 {attempt + 1} 次尝试...")

        test_start_time = time.time()
        # 完整流程：先走 report_intent_node 进行意图识别（这里会做广告主名称→ID转换）
        state = {
            "user_input": query,
            "advertiser_ids": [],
            "conversation_history": [],
        }

        try:
            from src.graph.nodes import report_intent_node
            ri_result = await report_intent_node(state)

            # 如果需要澄清，直接记录错误
            if ri_result.get("needs_clarification"):
                last_error = "需要用户澄清"
                continue

            # 如果已经有 final_report（纯广告主列表查询），直接认为成功
            if ri_result.get("final_report"):
                elapsed_time = time.time() - total_start_time
                # 提取分析类型（从预期）
                detailed_result = {
                    "test_id": test_case["id"],
                    "test_name": test_case["name"],
                    "query": query,
                    "expected_analysis_type": test_case.get("expected_analysis_type"),
                    "expected_target_level": test_case.get("expected_target_level"),
                    "prediction": test_case.get("prediction"),
                    "prediction_reason": test_case.get("prediction_reason"),
                    "status": "success",
                    "analysis_type": test_case.get("expected_analysis_type"),
                    "target_level": test_case.get("expected_target_level"),
                    "data_points": 0,
                    "all_zero": False,
                    "type_mismatch": False,
                    "response_time": round(elapsed_time, 2),
                    "error_message": None,
                    "attempts": attempt + 1,
                }
                if verbose:
                    detailed_result["raw_response"] = ri_result
                return detailed_result

            # 从 ri_result 获取处理后的 advertiser_ids 和 report_intent_result
            advertiser_ids = ri_result.get("advertiser_ids", [])
            report_intent_result = ri_result.get("report_intent_result", {})

            # 更新状态，进入 analysis_node
            state["advertiser_ids"] = advertiser_ids
            state["report_intent_result"] = report_intent_result

            # 导入 analysis_node 并运行
            from src.graph.nodes import analysis_node
            test_result = await analysis_node(state)
            elapsed_attempt = time.time() - test_start_time

            # 解析测试结果
            status = "success"
            if test_result.get("needs_clarification"):
                status = "needs_clarification"
                last_error = "需要用户澄清"
            elif test_result.get("error"):
                status = "error"
                last_error = str(test_result.get("error"))
            else:
                # 校验成功，直接返回结果
                elapsed_time = time.time() - total_start_time

                # 提取分析类型
                analysis_type = "unknown"
                target_level = "unknown"
                if "analysis_plan" in test_result and "analysis_plan" in test_result["analysis_plan"]:
                    ap = test_result["analysis_plan"]["analysis_plan"]
                    analysis_type = ap.get("analysis_type", "unknown")
                if "analysis_plan" in test_result and "target_level" in test_result["analysis_plan"]:
                    target_level = test_result["analysis_plan"]["target_level"]

                # 提取数据点数量
                data_points = 0
                if "chart_data" in test_result:
                    if "data" in test_result["chart_data"]:
                        data_points = len(test_result["chart_data"]["data"])
                    if "data_table" in test_result["chart_data"] and "rows" in test_result["chart_data"]["data_table"]:
                        data_points = len(test_result["chart_data"]["data_table"]["rows"])

                # 检查是否所有数据点都是0
                all_zero = False
                if data_points > 0 and status == "success":
                    if "chart_data" in test_result:
                        if "data" in test_result["chart_data"]:
                            chart_data = test_result["chart_data"].get("data", [])
                            if chart_data:
                                numeric_keys = [k for k in chart_data[0].keys() if k != "date"]
                                if numeric_keys:
                                    metric_key = numeric_keys[0]
                                    all_values = [point[metric_key] for point in chart_data if metric_key in point]
                                    all_zero = all(v == 0 for v in all_values)
                                    if all_zero:
                                        last_error = "所有数据点都为0，预期应该有非零值"
                                        status = "error"
                        if "data_table" in test_result["chart_data"] and status == "success":
                            data_table = test_result["chart_data"].get("data_table", {}).get("rows", [])
                            if data_table:
                                numeric_values = []
                                for row in data_table:
                                    for key, cell in row.items():
                                        if isinstance(cell, (int, float)):
                                            numeric_values.append(cell)
                                        elif isinstance(cell, dict) and "value" in cell:
                                            val = cell["value"]
                                            if isinstance(val, (int, float)):
                                                numeric_values.append(float(val))
                                if numeric_values:
                                    all_zero = all(v == 0 for v in numeric_values)
                                    if all_zero:
                                        last_error = "表格中所有数值都为0，预期应该有非零值"
                                        status = "error"

                # 对于实体表格，额外检查至少有一行数据
                if analysis_type == "entity_table" and data_points == 0 and status == "success":
                    last_error = "实体表格期望至少返回一条数据，但结果为空"
                    status = "error"

                # 检查分析类型是否符合预期
                expected_type = test_case.get("expected_analysis_type")
                type_mismatch = False
                if expected_type and analysis_type != expected_type and status == "success":
                    last_error = f"分析类型不匹配: 预期 {expected_type}, 实际 {analysis_type}"
                    status = "error"
                    type_mismatch = True

                # 提取 request_id（如果存在）
                request_id = None
                if test_result and isinstance(test_result, dict):
                    request_id = test_result.get("request_id") or test_result.get("requestId")

                # 构建详细结果
                detailed_result = {
                    "test_id": test_case["id"],
                    "test_name": test_case["name"],
                    "query": query,
                    "expected_analysis_type": test_case.get("expected_analysis_type"),
                    "expected_target_level": test_case.get("expected_target_level"),
                    "prediction": test_case.get("prediction"),
                    "prediction_reason": test_case.get("prediction_reason"),
                    "status": status,
                    "analysis_type": analysis_type,
                    "target_level": target_level,
                    "data_points": data_points,
                    "all_zero": all_zero,
                    "type_mismatch": type_mismatch,
                    "response_time": round(elapsed_time, 2),
                    "error_message": last_error,
                    "request_id": request_id,
                    "attempts": attempt + 1,
                }

                if verbose:
                    detailed_result["raw_response"] = test_result

                return detailed_result

        except Exception as e:
            last_error = f"执行异常: {str(e)}"
            last_result = None

        last_result = test_result if 'test_result' in locals() else None

    # 所有尝试都失败了
    elapsed_time = time.time() - total_start_time
    # 提取 request_id（如果存在）
    request_id = None
    if last_result and isinstance(last_result, dict):
        request_id = last_result.get("request_id") or last_result.get("requestId")

    return {
        "test_id": test_case["id"],
        "test_name": test_case["name"],
        "query": query,
        "expected_analysis_type": test_case.get("expected_analysis_type"),
        "expected_target_level": test_case.get("expected_target_level"),
        "prediction": test_case.get("prediction"),
        "prediction_reason": test_case.get("prediction_reason"),
        "status": "error",
        "analysis_type": "unknown",
        "target_level": "unknown",
        "data_points": 0,
        "all_zero": False,
        "type_mismatch": False,
        "response_time": round(elapsed_time, 2),
        "error_message": f"{max_retries}次尝试全部失败，最后一次错误: {last_error}",
        "request_id": request_id,
        "attempts": max_retries,
        "raw_response": last_result,
    }

async def main():
    """主函数"""
    args = parse_args()

    # 筛选要运行的测试用例
    selected_tests = None
    if args.tests:
        try:
            selected_test_ids = [int(id_str.strip()) for id_str in args.tests.split(",")]
            selected_tests = [
                test for test in DIVERSIFIED_TEST_CASES
                if test["id"] in selected_test_ids
            ]
            if not selected_tests:
                print("❌ 错误: 未找到指定的测试用例")
                sys.exit(1)
        except ValueError:
            print("❌ 错误: 测试ID格式不正确，请使用逗号分隔的数字")
            sys.exit(1)
    else:
        selected_tests = DIVERSIFIED_TEST_CASES

    print(f"🚀 开始运行 多样化自然语言Query测试 - Part 1，共 {len(selected_tests)} 个测试用例")
    print(f"📋 每个query最多尝试次数: {args.max_retries}")
    print(f"📌 后端地址: 从环境变量读取")
    print("-" * 80)

    total_start_time = time.time()
    test_results: List[Dict[str, Any]] = []

    # 运行所有测试用例
    for test_case in selected_tests:
        print(f"🔹 运行测试 {test_case['id']}: {test_case['name']}")
        print(f"   查询: {test_case['query']}")

        result = await run_single_test(test_case, args.max_retries, args.verbose)

        # 打印测试结果
        print(f"   状态: {result['status']}")
        print(f"   分析类型: {result['analysis_type']} (预期: {result['expected_analysis_type']})")
        if result["status"] == "success":
            print(f"   数据点数量: {result['data_points']}")
        print(f"   尝试次数: {result['attempts']}")
        print(f"   响应时间: {result['response_time']}s")
        if result["error_message"]:
            print(f"   错误信息: {result['error_message']}")
        print("-" * 60)

        test_results.append(result)

    # 生成汇总报告
    total_time = round(time.time() - total_start_time, 2)
    success_count = sum(1 for r in test_results if r["status"] == "success")
    clarification_count = sum(1 for r in test_results if r["status"] == "needs_clarification")
    error_count = sum(1 for r in test_results if r["status"] == "error")

    # 按预测分类统计
    pred_success_correct = sum(1 for r in test_results
        if r["prediction"] == "预期成功" and r["status"] == "success")
    pred_success_total = sum(1 for r in test_results if r["prediction"] == "预期成功")
    pred_mayfail_correct = sum(1 for r in test_results
        if r["prediction"] == "可能失败" and r["status"] != "success")
    pred_mayfail_total = sum(1 for r in test_results if r["prediction"] == "可能失败")
    pred_willfail_correct = sum(1 for r in test_results
        if r["prediction"] == "很可能失败" and r["status"] != "success")
    pred_willfail_total = sum(1 for r in test_results if r["prediction"] == "很可能失败")

    print("\n=== 📊 测试汇总报告 - Part 1 ===")
    print(f"总测试用例数: {len(test_results)}")
    print(f"成功: {success_count}")
    print(f"需要澄清: {clarification_count}")
    print(f"失败: {error_count}")
    print(f"总耗时: {total_time}s")
    print()
    print("=== 🔮 预测准确性 ===")
    if pred_success_total > 0:
        print(f"预期成功: {pred_success_correct}/{pred_success_total} ({pred_success_correct/pred_success_total*100:.0f}%)")
    if pred_mayfail_total > 0:
        print(f"预测可能失败（实际失败）: {pred_mayfail_correct}/{pred_mayfail_total} ({pred_mayfail_correct/pred_mayfail_total*100:.0f}%)")
    if pred_willfail_total > 0:
        print(f"预测很可能失败（实际失败）: {pred_willfail_correct}/{pred_willfail_total} ({pred_willfail_correct/pred_willfail_total*100:.0f}%)")

    # 打印失败的测试详情
    if error_count > 0:
        print("\n=== ❌ 失败测试详情 ===")
        for result in test_results:
            if result["status"] == "error":
                print(f"测试 {result['test_id']}: {result['test_name']}")
                print(f"Query: {result['query']}")
                print(f"预测: {result['prediction']}")
                print(f"错误: {result['error_message']}")
                print("-" * 40)

    # 保存结果到文件
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存到JSON文件: {output_path.resolve()}")

    # 同时保存markdown版本方便追加到文档
    md_path = script_dir.parent / "docs/test_cases/diversified_test_results_part1.md"
    generate_markdown_report(test_results, total_time, md_path)
    print(f"✅ Markdown报告已保存: {md_path.resolve()}")

    # 设置退出码
    if error_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)

def generate_markdown_report(results: List[Dict[str, Any]], total_time: float, output_path: Path):
    """生成markdown测试报告"""
    success_count = sum(1 for r in results if r["status"] == "success")
    clarification_count = sum(1 for r in results if r["status"] == "needs_clarification")
    error_count = sum(1 for r in results if r["status"] == "error")
    total = len(results)

    md = f"# 多样化自然语言Query测试结果 - Part 1 (ID 1-30)\n\n"
    md += f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md += f"## 📊 汇总统计\n\n"
    md += f"| 指标 | 数值 | 占比 |\n"
    md += f"|------|------|------|\n"
    md += f"| 总测试用例 | {total} | 100% |\n"
    md += f"| 成功 | {success_count} | {success_count/total*100:.0f}% |\n"
    md += f"| 需要澄清 | {clarification_count} | {clarification_count/total*100:.0f}% |\n"
    md += f"| 失败 | {error_count} | {error_count/total*100:.0f}% |\n"
    md += f"| 总耗时 | {total_time:.2f}s | - |\n\n"

    md += f"## 按预测分类\n\n"
    pred_categories = {
        "预期成功": {"total": 0, "success": 0},
        "可能失败": {"total": 0, "success": 0},
        "很可能失败": {"total": 0, "success": 0},
    }
    for r in results:
        pred = r["prediction"]
        pred_categories[pred]["total"] += 1
        if r["status"] == "success":
            pred_categories[pred]["success"] += 1
    md += f"| 预测分类 | 总数量 | 成功数 | 成功率 |\n"
    md += f"|-----------|--------|--------|--------|\n"
    for cat, stats in pred_categories.items():
        if stats["total"] > 0:
            rate = stats["success"] / stats["total"] * 100
            md += f"| {cat} | {stats['total']} | {stats['success']} | {rate:.0f}% |\n"
    md += "\n"

    md += f"## 📋 详细结果\n\n"
    md += f"| ID | 状态 | 预测 | Query | 分析类型(预期/实际) | 数据点 | 错误 |\n"
    md += f"|----|------|------|-------|-------------------|--------|------|\n"
    for r in sorted(results, key=lambda x: x["test_id"]):
        status_emoji = {
            "success": "✅",
            "needs_clarification": "❔",
            "error": "❌",
        }.get(r["status"], "❌")
        query_short = r["query"][:40] + ("..." if len(r["query"]) > 40 else "")
        type_str = f"{r['expected_analysis_type']}/{r['analysis_type']}"
        error_short = r["error_message"][:30] if r["error_message"] else ""
        md += f"| {r['test_id']} | {status_emoji} {r['status']} | {r['prediction']} | {query_short} | {type_str} | {r['data_points']} | {error_short} |\n"

    md += "\n## ❌ 失败详情\n\n"
    for r in results:
        if r["status"] == "error":
            md += f"### {r['test_id']}. {r['test_name']}\n\n"
            md += f"- **Query**: {r['query']}\n"
            md += f"- **预测**: {r['prediction']}\n"
            md += f"- **预期分析类型**: {r['expected_analysis_type']}\n"
            md += f"- **实际分析类型**: {r['analysis_type']}\n"
            md += f"- **预期目标层级**: {r['expected_target_level']}\n"
            md += f"- **实际目标层级**: {r['target_level']}\n"
            md += f"- **错误信息**: {r['error_message']}\n"
            md += f"- **尝试次数**: {r['attempts']}\n"
            md += f"- **响应时间**: {r['response_time']}s\n"
            md += "\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)

if __name__ == "__main__":
    asyncio.run(main())
