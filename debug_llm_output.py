#!/usr/bin/env python3
"""
Debug: 直接看LLM返回的JSON是什么
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
from src.intent.llm_client import get_intent_llm_client
from src.intent.prompts import REPORT_INTENT_SYSTEM_PROMPT
from datetime import date

async def debug_llm(query: str):
    """直接调用LLM看输出"""
    llm_client = get_intent_llm_client()

    today_str = str(date.today())
    system_prompt = REPORT_INTENT_SYSTEM_PROMPT.format(today_date=today_str)

    print(f"Calling LLM with query: {query}")
    print()

    response_text = await llm_client.call(
        system_prompt=system_prompt,
        user_prompt=f"用户输入：{query}",
        json_mode=True,
        schema=None,
    )

    print("=== LLM RAW RESPONSE ===")
    print(response_text[:2000])
    print("=== END RAW RESPONSE ===")
    print()

    try:
        data = json.loads(response_text)
        print("=== PARSED JSON ===")
        print(f"advertiser_ids: {data.get('advertiser_ids')}")
        print(f"advertiser_names: {data.get('advertiser_names')}")
        print(f"time_range: {data.get('time_range')}")
        print(f"filters: {data.get('filters')}")
        print(f"top_n: {data.get('top_n')}")
        print(f"sort: {data.get('sort')}")
        print(f"metrics: {data.get('metrics')}")
        print(f"group_by: {data.get('group_by')}")
        print(f"ad_level: {data.get('ad_level')}")
    except Exception as e:
        print(f"JSON parse error: {e}")

queries = [
    "找出 digital_0 名称带 digital 的广告计划，按消耗排序",
]

async def main():
    for q in queries:
        print("\n" + "="*80)
        await debug_llm(q)

if __name__ == "__main__":
    asyncio.run(main())
