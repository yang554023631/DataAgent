#!/usr/bin/env python3
"""
Run the specified 8 e2e test cases after fixing test 19.
"""

import asyncio
import json
import time
from typing import List, Dict, Any

# 添加 backend 目录到 Python 路径
import sys
from pathlib import Path
script_dir = Path(__file__).parent
backend_dir = script_dir / "backend"
sys.path.insert(0, str(backend_dir.resolve()))

# 指定的8个测试用例
SPECIFIED_TESTS = [
    {
        "id": 9,
        "name": "模糊名称查询 - 包含digital + 排序",
        "query": "找出 digital_0 名称带 digital 的广告计划，按消耗排序",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
    },
    {
        "id": 12,
        "name": "模糊查询 + 排序 + TopN - ad_group",
        "query": "在 digital_0 中找出名称包含六一八的所有广告组，按消耗降序排列前三",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "ad_group",
    },
    {
        "id": 15,
        "name": "模糊名称查询 - creative",
        "query": "列出 digital_0 名称含尊享的所有创意及消耗",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "creative",
    },
    {
        "id": 18,
        "name": "混合筛选 - status + 名称contains",
        "query": "digital_0 投放中的广告计划，名称含有 best，列出消耗和点击",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
    },
    {
        "id": 19,
        "name": "混合筛选 - 名称 + having点击",
        "query": "找出 digital_0 下名称含 mini 的创意，点击量大于50",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "creative",
    },
    {
        "id": 50,
        "name": "Ad Group TopN - 点击率前五",
        "query": "列出广告主6点击率从高到低排前五的广告组",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "ad_group",
    },
    {
        "id": 52,
        "name": "Creative TopN - 转化率前三",
        "query": "广告主6转化率最高的三个创意",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "creative",
    },
    {
        "id": 54,
        "name": "受众分布 - 操作系统占比",
        "query": "广告主6按不同操作系统看消耗占比",
        "expected_analysis_type": "audience_distribution",
        "expected_target_level": "advertiser",
    },
]


async def run_single_test(test_case: Dict[str, Any], advertiser_id: str = "6", max_retries: int = 2) -> Dict[str, Any]:
    """运行单个测试用例"""
    query = test_case["query"]
    total_start_time = time.time()

    from src.graph.nodes import analysis_node

    # 构建分析节点的输入状态
    state = {
        "user_input": query,
        "advertiser_ids": [advertiser_id],
        "conversation_history": [],
        "report_intent": {},
    }

    last_result = None
    last_error = None

    # 最多重试 max_retries 次
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"      第 {attempt + 1} 次重试...")

        test_start_time = time.time()

        try:
            test_result = await analysis_node(state)
            elapsed_attempt = time.time() - test_start_time

            # 解析测试结果
            status = "success"
            if test_result.get("needs_clarification"):
                status = "needs_clarification"
                last_error = "需要澄清"
            elif test_result.get("error"):
                status = "error"
                last_error = str(test_result.get("error"))
            else:
                # 校验成功
                elapsed_time = time.time() - total_start_time

                # 提取分析类型
                analysis_type = "unknown"
                target_level = "unknown"
                if ("analysis_plan" in test_result and
                    test_result.get("analysis_plan") and
                    "analysis_plan" in test_result["analysis_plan"]):
                    ap = test_result["analysis_plan"]["analysis_plan"]
                    analysis_type = ap.get("analysis_type", "unknown")
                    if ap.get("filter_plan"):
                        target_level = ap["filter_plan"].get("target_level", "unknown")

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
                    if "data_table" in test_result["chart_data"]:
                        data_table = test_result["chart_data"].get("data_table", {}).get("rows", [])
                        if data_table:
                            numeric_values = []
                            for row in data_table:
                                for _, cell in row.items():
                                    if isinstance(cell, (int, float)):
                                        numeric_values.append(cell)
                                    elif isinstance(cell, dict) and "value" in cell:
                                        val = cell["value"]
                                        if isinstance(val, (int, float)):
                                            numeric_values.append(val)
                            if numeric_values:
                                all_zero = all(v == 0 for v in numeric_values)
                                if all_zero:
                                    status = "error"
                                    last_error = "表格中所有数值都为0，预期应该有非零值"

                # 对于实体表格，额外检查至少有一行数据
                type_mismatch = False
                if (test_case["expected_analysis_type"] == "entity_table" and
                    analysis_type != "entity_table" and
                    status == "success"):
                    type_mismatch = True
                    status = "error"
                    last_error = f"分析类型不匹配: 预期 {test_case['expected_analysis_type']}, 实际 {analysis_type}"

                if analysis_type != test_case["expected_analysis_type"] and status == "success":
                    type_mismatch = True

                # 构建详细结果
                detailed_result = {
                    "test_id": test_case["id"],
                    "test_name": test_case["name"],
                    "query": query,
                    "status": status,
                    "expected_analysis_type": test_case["expected_analysis_type"],
                    "actual_analysis_type": analysis_type,
                    "expected_target_level": test_case["expected_target_level"],
                    "actual_target_level": target_level,
                    "data_points": data_points,
                    "all_zero": all_zero,
                    "type_mismatch": type_mismatch,
                    "response_time": round(elapsed_time, 2),
                    "error_message": last_error,
                    "retries": attempt,
                }

                return detailed_result

        except Exception as e:
            last_error = f"执行异常: {str(e)}"

        last_result = test_result if 'test_result' in locals() else None

    # 所有重试都失败了
    elapsed_time = time.time() - total_start_time
    return {
        "test_id": test_case["id"],
        "test_name": test_case["name"],
        "query": query,
        "status": "error",
        "expected_analysis_type": test_case["expected_analysis_type"],
        "actual_analysis_type": "unknown",
        "expected_target_level": test_case["expected_target_level"],
        "actual_target_level": "unknown",
        "data_points": 0,
        "all_zero": False,
        "type_mismatch": False,
        "response_time": round(elapsed_time, 2),
        "error_message": f"{max_retries}次重试全部失败，最后一次错误: {last_error}",
        "retries": max_retries,
        "raw_response": last_result,
    }


async def main():
    """主函数"""
    print(f"🚀 开始运行指定的 {len(SPECIFIED_TESTS)} 个 e2e 测试用例")
    print(f"📌 广告主ID: 6")
    print("-" * 100)

    total_start_time = time.time()
    test_results: List[Dict[str, Any]] = []

    for test_case in SPECIFIED_TESTS:
        print(f"\n🔹 测试 {test_case['id']}: {test_case['name']}")
        print(f"   查询: {test_case['query']}")

        result = await run_single_test(test_case, "6", max_retries=2)

        # 打印测试结果
        print(f"   状态: {result['status']}")
        print(f"   预期分析类型: {result['expected_analysis_type']}, 实际: {result['actual_analysis_type']}")
        if result["status"] == "success":
            print(f"   数据点数量: {result['data_points']}")
        print(f"   响应时间: {result['response_time']}s")
        if result["error_message"]:
            print(f"   错误信息: {result['error_message']}")
        print("-" * 80)

        test_results.append(result)

    # 生成汇总报告
    total_time = round(time.time() - total_start_time, 2)
    success_count = sum(1 for r in test_results if r["status"] == "success")
    needs_clarification_count = sum(1 for r in test_results if r["status"] == "needs_clarification")
    error_count = sum(1 for r in test_results if r["status"] == "error")

    print("\n" + "=" * 100)
    print("=== 📊 测试汇总报告 ===")
    print(f"总测试用例数: {len(test_results)}")
    print(f"✅ 成功: {success_count}")
    print(f"❓ 需要澄清: {needs_clarification_count}")
    print(f"❌ 失败: {error_count}")
    print(f"总耗时: {total_time}s")
    print("=" * 100)

    # 打印失败的测试详情
    if error_count > 0:
        print("\n=== ❌ 失败测试详情 ===")
        for result in test_results:
            if result["status"] == "error":
                print(f"测试 {result['test_id']}: {result['test_name']}")
                print(f"错误: {result['error_message']}")
                print(f"数据行数: {result['data_points']}")
                print("-" * 60)

    # 保存结果到文件
    output_path = script_dir / "specified_8_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存到: {output_path.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
