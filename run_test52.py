#!/usr/bin/env python3
"""Run test 52 specifically to see the actual execution plan"""

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

from src.graph.nodes import analysis_node

# 测试52
TEST_CASE = {
    "id": 52,
    "name": "Creative TopN - 转化率前三",
    "query": "广告主6转化率最高的三个创意",
    "expected_analysis_type": "entity_table",
    "expected_target_level": "creative",
}

async def run_test():
    """运行测试52并打印详细执行流程"""
    query = TEST_CASE["query"]
    print(f"🔹 测试 {TEST_CASE['id']}: {TEST_CASE['name']}")
    print(f"   查询: {query}")
    print()

    start_time = time.time()

    state = {
        "user_input": query,
        "advertiser_ids": ["6"],
        "conversation_history": [],
        "report_intent": {},
    }

    try:
        result = await analysis_node(state)
        elapsed = time.time() - start_time

        print(f"⏱️  响应时间: {elapsed:.2f}s")
        print()

        if "error" in result and result["error"]:
            print(f"❌ 错误: {result['error']}")
            print()

        if "raw_response" in result:
            result = result["raw_response"]

        # 打印执行追踪
        if "execution_trace" in result:
            print("📋 执行追踪:")
            for step in result["execution_trace"]:
                status = step["status"]
                step_name = step["step"]
                duration = step.get("duration_ms", 0) / 1000
                print(f"  • {step_name}: {status} ({duration:.2f}s)")
                # 如果提取了字段，打印出来
                if "extracted_fields" in step:
                    print(f"    提取字段: {json.dumps(step['extracted_fields'], indent=2, ensure_ascii=False)}")
            print()

        # 打印分析计划
        if "analysis_plan" in result and result["analysis_plan"]:
            ap = result["analysis_plan"]
            print("📐 完整分析计划:")
            print(json.dumps(ap, indent=2, ensure_ascii=False))
            print()

        # 打印最终结果
        if "chart_data" in result and result["chart_data"]:
            print("📊 最终数据:")
            if "data_table" in result["chart_data"]:
                dt = result["chart_data"]["data_table"]
                # Print columns
                col_names = []
                for c in dt['columns']:
                    if isinstance(c, dict) and 'name' in c:
                        col_names.append(c['name'])
                    elif isinstance(c, str):
                        col_names.append(c)
                    else:
                        col_names.append(str(c))
                print(f"  列: {col_names}")
                print(f"  行数: {len(dt['rows'])}")
                for i, row in enumerate(dt['rows'][:10]):
                    if isinstance(row, dict):
                        values = []
                        for k, cell in row.items():
                            if isinstance(cell, dict) and 'value' in cell:
                                values.append(str(cell['value']))
                            else:
                                values.append(str(cell))
                        print(f"  {i+1}. {', '.join(values)}")

        return result

    except Exception as e:
        print(f"💥 执行异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(run_test())
