#!/usr/bin/env python3
"""
Debug 为什么 filters 没解析出来
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

async def debug_single(query: str):
    analyzer = get_report_intent_analyzer()
    result, clarification, final_report, route_info = await analyzer.analyze(
        query,
        conversation_history=[],
        existing_advertiser_ids=[],
    )

    if clarification:
        print(f"❌ 需要澄清: {clarification.question}")
        return

    print(f"✓ 意图解析成功")
    print(f"  advertiser_ids: {result.advertiser_ids}")
    print(f"  advertiser_names: {result.advertiser_names}")
    print(f"  time_range.is_lifetime: {result.time_range.is_lifetime}")
    print(f"  top_n: {result.top_n}")
    print(f"  sort: {result.sort}")
    print(f"  filters: {result.filters}")
    print(f"  metrics: {result.metrics}")
    print(f"  group_by: {result.group_by}")
    print(f"  ad_level: {result.ad_level}")
    if result.filters:
        print("\nfilters 详情:")
        for i, f in enumerate(result.filters):
            print(f"  [{i+1}] {f}")

# 测试几个
queries = [
    "找出 digital_0 名称带 digital 的广告计划，按消耗排序",
    "digital_0 投放中的广告计划，名称含有 best，列出消耗和点击",
    "找出 digital_0 下名称含 mini 的创意，点击量大于50的",
]

async def main():
    for q in queries:
        print("\n" + "="*60)
        print(f"Query: {q}")
        print("-"*60)
        await debug_single(q)

if __name__ == "__main__":
    asyncio.run(main())
