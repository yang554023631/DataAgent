#!/usr/bin/env python3
"""
测试 8 个原始query（不添加四月份），检查是否还触发澄清
"""

import argparse
import sys
import os
import json
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

# 添加 backend 目录到 Python 路径
script_dir = Path(__file__).parent
backend_dir = script_dir / "backend"
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

from src.intent.report_intent import get_report_intent_analyzer
from src.intent.models import ReportIntentResult, ClarificationInfo

# 8个测试用例（原始query，不带四月份）
TEST_CASES = [
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
        "query": "找出 digital_0 下名称含 mini 的创意，点击量大于50的",
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

async def run_single_test(
    test_case: Dict[str, Any],
    max_retries: int = 2,
) -> Dict[str, Any]:
    """运行单个测试用例"""
    query = test_case["query"]
    total_start_time = time.time()

    analyzer = get_report_intent_analyzer()

    for attempt in range(max_retries):
        if attempt > 0:
            print(f"   第 {attempt + 1} 次尝试...")

        result, clarification, final_report, route_info = await analyzer.analyze(
            query,
            conversation_history=[],
            existing_advertiser_ids=[],
        )

        if clarification:
            print(f"   ❌ 需要澄清: {clarification.question}")
            continue

        if final_report:
            # 纯广告主查询，不需要后续
            elapsed_time = time.time() - total_start_time
            print(f"   ✓ 成功! (纯广告主查询)")
            return {
                "test_id": test_case["id"],
                "test_name": test_case["name"],
                "query": query,
                "status": "success",
                "analysis_type": "advertiser_lookup",
                "error_message": None,
                "attempts": attempt + 1,
                "response_time": round(elapsed_time, 2),
            }

        # 信息齐全，成功
        elapsed_time = time.time() - total_start_time
        analysis_type = test_case.get("expected_analysis_type")

        # 打印关键结构
        print(f"   ✓ 成功! advertiser_ids={result.advertiser_ids}, "
              f"advertiser_names={result.advertiser_names}, "
              f"metrics={result.metrics}, "
              f"top_n={result.top_n}, "
              f"sort={result.sort}, "
              f"time_range.is_lifetime={result.time_range.is_lifetime if result.time_range else None}")

        return {
            "test_id": test_case["id"],
            "test_name": test_case["name"],
            "query": query,
            "status": "success",
            "analysis_type": analysis_type,
            "error_message": None,
            "attempts": attempt + 1,
            "response_time": round(elapsed_time, 2),
        }

    # 所有尝试都失败
    elapsed_time = time.time() - total_start_time
    return {
        "test_id": test_case["id"],
        "test_name": test_case["name"],
        "query": query,
        "status": "needs_clarification",
        "analysis_type": "unknown",
        "error_message": clarification.question if clarification else "未知错误",
        "attempts": max_retries,
        "response_time": round(elapsed_time, 2),
    }

async def main():
    print(f"🚀 开始运行 8个测试用例（原始query，不添加时间）")
    print(f"📋 每个query最多尝试次数: 2")
    print("-" * 80)

    total_start_time = time.time()
    test_results: List[Dict[str, Any]] = []

    for test_case in TEST_CASES:
        print(f"🔹 运行测试 {test_case['id']}: {test_case['name']}")
        print(f"   查询: {test_case['query']}")

        result = await run_single_test(test_case, 2)

        # 打印结果
        status_emoji = "✅" if result["status"] == "success" else "❔"
        print(f"   {status_emoji} {result['status']}")
        if result["error_message"]:
            print(f"   错误: {result['error_message']}")
        print("-" * 60)

        test_results.append(result)

    # 汇总
    total_time = round(time.time() - total_start_time, 2)
    success_count = sum(1 for r in test_results if r["status"] == "success")
    clarification_count = sum(1 for r in test_results if r["status"] == "needs_clarification")

    print("\n=== 📊 测试汇总报告 ===")
    print(f"总测试用例数: {len(test_results)}")
    print(f"成功: {success_count}")
    print(f"需要澄清: {clarification_count}")
    print(f"总耗时: {total_time}s")

    # 保存结果
    output_path = Path("test_8_original_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存到: {output_path.resolve()}")

    if clarification_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
