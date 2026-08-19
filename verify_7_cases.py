#!/usr/bin/env python3
"""
验证修复后的7个失败案例
"""

import sys
import os
import json
import asyncio
from pathlib import Path

# 添加 backend 目录到 Python 路径
script_dir = Path(__file__).parent
backend_dir = script_dir / "backend"
sys.path.insert(0, str(backend_dir.resolve()))

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("警告: python-dotenv 未安装，将使用系统环境变量")

from src.intent.report_intent import get_report_intent_analyzer
from src.tools.custom_report_client import CustomReportClient
from src.models import QueryRequest

# 7个测试用例
TEST_CASES = [
    {
        "id": 9,
        "name": "模糊名称查询 - 包含digital + 排序",
        "query": "找出 digital_0 名称带 digital 的广告计划，按消耗排序",
    },
    {
        "id": 12,
        "name": "模糊查询 + 排序 + TopN - ad_group",
        "query": "在 digital_0 中找出名称包含六一八的所有广告组，按消耗降序排列前三",
    },
    {
        "id": 15,
        "name": "模糊名称查询 - creative",
        "query": "列出 digital_0 名称含尊享的所有创意及消耗",
    },
    {
        "id": 18,
        "name": "混合筛选 - status + 名称contains",
        "query": "digital_0 投放中的广告计划，名称含有 best，列出消耗和点击",
    },
    {
        "id": 19,
        "name": "混合筛选 - 名称 + having点击",
        "query": "找出 digital_0 下名称含 mini 的创意，点击量大于50的",
    },
    {
        "id": 50,
        "name": "Ad Group TopN - 点击率前五",
        "query": "列出广告主6点击率从高到低排前五的广告组",
    },
    {
        "id": 52,
        "name": "Creative TopN - 转化率前三",
        "query": "广告主6转化率最高的三个创意",
    },
]

async def run_test(test_case):
    """运行单个测试"""
    print(f"\n{'='*60}")
    print(f"🔹 测试 {test_case['id']}: {test_case['name']}")
    print(f"查询: {test_case['query']}")

    analyzer = get_report_intent_analyzer()
    result, clarification, final_report, route_info = await analyzer.analyze(
        test_case['query'],
        conversation_history=[],
        existing_advertiser_ids=[],
    )

    if clarification:
        print(f"❌ 需要澄清: {clarification.question}")
        return {
            "test_id": test_case['id'],
            "status": "clarification",
            "error": clarification.question,
        }

    print(f"✓ 意图解析成功，不触发澄清")
    print(f"  advertiser_ids: {result.advertiser_ids}")
    print(f"  advertiser_names: {result.advertiser_names}")
    print(f"  time_range.is_lifetime: {result.time_range.is_lifetime}")
    print(f"  top_n: {result.top_n}")
    print(f"  sort: {result.sort}")
    print(f"  filters: {len(result.filters)} 个筛选条件")
    for f in result.filters:
        print(f"    - {f.get('field')} {f.get('operator')} {f.get('value')}")

    # 执行查询
    client = CustomReportClient()
    # 需要转换为dict，因为QueryRequest期望dict
    query_request = QueryRequest(
        advertiser_ids=result.advertiser_ids,
        advertiser_names=result.advertiser_names,
        time_range=result.time_range.model_dump(),
        metrics=result.metrics,
        ad_level=result.ad_level,
        group_by=result.group_by,
        filters=result.filters,
        is_comparison=result.is_comparison,
        top_n=result.top_n,
        sort=result.sort,
    )

    result_es = await client.execute_query(query_request)

    if not result_es.success:
        print(f"❌ ES查询失败: {result_es.message}")
        return {
            "test_id": test_case['id'],
            "status": "es_error",
            "error": result_es.message,
            "data_rows": 0,
        }

    print(f"✓ ES查询成功，返回 {result_es.total_rows} 行数据")
    if result_es.data:
        for i, row in enumerate(result_es.data[:5]):
            print(f"  [{i+1}] {row}")
        if len(result_es.data) > 5:
            print(f"  ... 还有 {len(result_es.data) - 5} 行")

    return {
        "test_id": test_case['id'],
        "status": "success" if result_es.total_rows > 0 else "empty",
        "data_rows": result_es.total_rows,
        "data": result_es.data,
    }

async def main():
    print(f"🚀 开始验证修复后的7个失败案例")
    print(f"当前修复: like查询改为match, 衍生指标排序路径修正")
    print()

    results = []
    for tc in TEST_CASES:
        result = await run_test(tc)
        results.append(result)

    print("\n" + "="*60)
    print("📊 验证结果汇总")
    print("="*60)

    success = sum(1 for r in results if r['status'] == 'success')
    empty = sum(1 for r in results if r['status'] == 'empty')
    errors = sum(1 for r in results if r['status'] not in ['success', 'empty'])

    print(f"总测试: {len(results)}")
    print(f"✅ 成功返回数据: {success}")
    print(f"⚠️  仍然为空: {empty}")
    print(f"❌ 错误: {errors}")
    print()

    for r in results:
        status_emoji = {
            'success': '✅',
            'empty': '⚠️',
            'clarification': '❔',
            'es_error': '❌',
        }.get(r['status'], '❌')
        name = next(tc['name'] for tc in TEST_CASES if tc['id'] == r['test_id'])
        msg = r.get('error', f"{r.get('data_rows', 0)} rows")
        print(f"{status_emoji} {r['test_id']}: {name} -> {msg}")

if __name__ == "__main__":
    asyncio.run(main())
