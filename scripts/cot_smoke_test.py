#!/usr/bin/env python3
"""
CoT 分析流水线冒烟测试脚本

## 功能
该脚本用于对 CoT (Chain of Thought) 分析流水线进行端到端冒烟测试，使用真实的 Elasticsearch 和 LLM 服务，验证整个分析流程是否正常工作。

## 环境配置
需要在 .env 文件或系统环境变量中配置以下参数:
- ES_URL: Elasticsearch 服务地址
- ES_USER: Elasticsearch 用户名
- ES_PASSWORD: Elasticsearch 密码
- LLM_API_KEY: LLM 服务 API 密钥
- LLM_ENDPOINT: LLM 服务接口地址
- LLM_MODEL: LLM 模型名称 (可选，默认值为 gpt-4o)

## 使用方法
1. 安装依赖:
   pip install python-dotenv

2. 配置环境变量:
   复制 .env.example 为 .env，并填写相关参数

3. 运行脚本:
   # 运行所有测试用例
   python scripts/cot_smoke_test.py

   # 运行指定的测试用例
   python scripts/cot_smoke_test.py --tests 1,2,3

   # 指定广告主ID
   python scripts/cot_smoke_test.py --advertiser-id 123

   # 打印详细信息
   python scripts/cot_smoke_test.py --verbose

   # 将结果保存到JSON文件
   python scripts/cot_smoke_test.py --output results.json

## 测试用例
1. Simple time trend: 无过滤条件的单指标时间趋势分析
2. Entity table with where filter: 带where过滤条件的实体表格分析
3. Entity table with having filter: 带having过滤条件的实体表格分析
4. Period comparison: 周期对比分析
5. Audience distribution: 受众分布分析
6. Multi-series trend with having filter: 带having过滤的多序列时间趋势分析
7. Summary (KPI cards): 核心KPI汇总分析

## 结果说明
每个测试用例的结果包含:
- 测试ID和名称
- 查询语句
- 状态: success/needs_clarification/error
- 分析类型
- 数据点数量
- 是否包含图表配置
- 响应时间
- 错误信息(如果有)
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
# ES_USER 和 ES_PASSWORD 是可选的（本地开发 ES 通常不需要认证）
optional_env_vars = [
    "ES_USER",
    "ES_PASSWORD",
]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    print("❌ 错误: 缺少必要的环境变量:")
    for var in missing_vars:
        print(f"  - {var}")
    print("请设置这些环境变量或在 .env 文件中配置")
    sys.exit(2)

# 加载配置
config = {
    "es_url": os.getenv("ES_URL"),
    "es_user": os.getenv("ES_USER"),
    "es_password": os.getenv("ES_PASSWORD"),
    "llm_api_key": os.getenv("LLM_API_KEY"),
    "llm_endpoint": os.getenv("LLM_ENDPOINT"),
    "llm_model": os.getenv("LLM_MODEL", "gpt-4o")
}

# 定义测试场景
DEFAULT_TEST_CASES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "Simple time trend (April)",
        "query_template": "id为{advertiser_id}的广告主4月份的消耗趋势",
        "description": "4月份单指标时间趋势分析，预期返回一条非全零趋势线"
    },
    {
        "id": 2,
        "name": "Entity table with where filter",
        "query_template": "广告主6下未删除的广告计划4月份的消耗和点击",
        "description": "带where过滤条件的实体表格分析，预期返回campaign列表，含名称/ID、消耗、点击汇总，不全为0"
    },
    {
        "id": 3,
        "name": "Entity table with having filter",
        "query_template": "广告主{advertiser_id}4月份消耗大于10的广告计划有哪些",
        "description": "带having过滤条件的实体表格分析"
    },
    {
        "id": 4,
        "name": "Period comparison",
        "query_template": "广告主{advertiser_id}4月的消耗和3月比怎么样",
        "description": "周期对比分析"
    },
    {
        "id": 5,
        "name": "Audience distribution",
        "query_template": "广告主{advertiser_id}4月份的消耗按性别分布",
        "description": "受众分布分析"
    },
    {
        "id": 6,
        "name": "Multi-series trend with having filter",
        "query_template": "广告主{advertiser_id}4月份消耗>10的广告计划的消耗趋势图",
        "description": "带having过滤的多序列时间趋势分析"
    },
    {
        "id": 7,
        "name": "Summary (KPI cards)",
        "query_template": "广告主{advertiser_id}4月份的核心数据",
        "description": "核心KPI汇总分析"
    }
]

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="CoT 分析流水线冒烟测试脚本")
    parser.add_argument(
        "--tests",
        type=str,
        help="指定要运行的测试ID，逗号分隔，例如 1,2,3"
    )
    parser.add_argument(
        "--advertiser-id",
        type=str,
        default="6",
        help="指定广告主ID，默认值为 6"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="打印详细的计划和响应信息"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="将结果保存到JSON文件"
    )
    return parser.parse_args()

async def run_single_test(test_case: Dict[str, Any], advertiser_id: str, verbose: bool = False) -> Dict[str, Any]:
    """运行单个测试用例"""
    query = test_case["query_template"].format(advertiser_id=advertiser_id)
    test_start_time = time.time()

    # 构建分析节点的输入状态
    state = {
        "user_input": query,
        "advertiser_ids": [advertiser_id],
        "conversation_history": [],
        "report_intent": {},
    }

    try:
        # 导入 analysis_node 并运行
        from src.graph.nodes import analysis_node

        test_result = await analysis_node(state)
        elapsed_time = time.time() - test_start_time

        # 解析测试结果
        status = "success"
        if test_result.get("needs_clarification"):
            status = "needs_clarification"
        elif test_result.get("error"):
            status = "error"

        # 提取分析类型
        analysis_type = "unknown"
        if "analysis_plan" in test_result and "analysis_plan" in test_result["analysis_plan"]:
            ap = test_result["analysis_plan"]["analysis_plan"]
            analysis_type = ap.get("analysis_type", "unknown")

        # 提取数据点数量
        # - 趋势分析: chart_data 包含 chart_data.data (data points list)
        # - 实体表格: chart_data 包含 data_table.rows (table rows list)
        # test_result: analysis_node output
        # test_result['chart_data'] = AnalysisResult.model_dump()
        data_points = 0
        if "chart_data" in test_result:
            if "data" in test_result["chart_data"]:
                data_points = len(test_result["chart_data"]["data"])
            if "data_table" in test_result["chart_data"] and "rows" in test_result["chart_data"]["data_table"]:
                data_points = len(test_result["chart_data"]["data_table"]["rows"])

        # 检查是否有图表配置 - chart_config directly in chart_data for trend
        has_chart_config = False
        if "chart_data" in test_result:
            if "chart_config" in test_result["chart_data"]:
                has_chart_config = test_result["chart_data"]["chart_config"] is not None

        # 收集错误信息
        error_msg = None
        if test_result.get("error"):
            error_msg = str(test_result["error"])

        # 检查是否所有数据点都是0
        all_zero = False
        if data_points > 0 and status == "success":
            # 趋势分析：检查趋势数据（在 chart_data.data）
            if "data" in test_result["chart_data"]:
                chart_data = test_result["chart_data"].get("data", [])
                if chart_data:
                    # 检查第一个metric是否全为0
                    first_point = chart_data[0]
                    # 获取第一个数值key（排除date）
                    numeric_keys = [k for k in first_point.keys() if k != "date"]
                    if numeric_keys:
                        metric_key = numeric_keys[0]
                        all_values = [point[metric_key] for point in chart_data if metric_key in point]
                        all_zero = all(v == 0 for v in all_values)
                        if all_zero:
                            error_msg = "所有数据点都为0，预期应该有非零值"
                            status = "error"
            # 实体表格：检查数据不全为0（在 data_table.rows）
            # test_result["chart_data"] = AnalysisResult.model_dump()
            # data_table 直接在 chart_data 下
            if "data_table" in test_result["chart_data"]:
                data_table = test_result["chart_data"].get("data_table", {}).get("rows", [])
                if data_table:
                    # 获取所有数值单元格的值
                    # 每行是 dict: {column_key: cell_value}
                    # cell_value can be:
                    # - int/float (直接值)
                    # - {"value": int/float} (对指标值)
                    numeric_values = []
                    for row in data_table:
                        for key, cell in row.items():
                            if isinstance(cell, (int, float)):
                                numeric_values.append(cell)
                            elif isinstance(cell, dict) and "value" in cell:
                                val = cell["value"]
                                if isinstance(val, (int, float)):
                                    numeric_values.append(val)
                    if numeric_values:
                        all_zero = all(v == 0 for v in numeric_values)
                        if all_zero:
                            error_msg = "表格中所有数值都为0，预期应该有非零值"
                            status = "error"

        # 对于实体表格，额外检查至少有一行数据
        if analysis_type == "entity_table" and data_points == 0 and status == "success":
            error_msg = "实体表格期望至少返回一条数据，但结果为空"
            status = "error"

        # 构建详细结果
        detailed_result = {
            "test_id": test_case["id"],
            "test_name": test_case["name"],
            "query": query,
            "status": status,
            "analysis_type": analysis_type,
            "data_points": data_points,
            "has_chart_config": has_chart_config,
            "all_zero": all_zero,
            "response_time": round(elapsed_time, 2),
            "error_message": error_msg,
        }

        if verbose:
            detailed_result["raw_response"] = test_result

        if verbose:
            detailed_result["raw_response"] = test_result

        return detailed_result

    except Exception as e:
        elapsed_time = time.time() - test_start_time
        return {
            "test_id": test_case["id"],
            "test_name": test_case["name"],
            "query": query,
            "status": "error",
            "analysis_type": "unknown",
            "data_points": 0,
            "has_chart_config": False,
            "response_time": round(elapsed_time, 2),
            "error_message": f"执行异常: {str(e)}"
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
                test for test in DEFAULT_TEST_CASES
                if test["id"] in selected_test_ids
            ]
            if not selected_tests:
                print("❌ 错误: 未找到指定的测试用例")
                sys.exit(1)
        except ValueError:
            print("❌ 错误: 测试ID格式不正确，请使用逗号分隔的数字")
            sys.exit(1)
    else:
        selected_tests = DEFAULT_TEST_CASES

    print(f"🚀 开始运行 CoT 分析冒烟测试，共 {len(selected_tests)} 个测试用例")
    print(f"📌 广告主ID: {args.advertiser_id}")
    print("-" * 80)

    total_start_time = time.time()
    test_results: List[Dict[str, Any]] = []

    # 运行所有测试用例
    for test_case in selected_tests:
        print(f"🔹 运行测试 {test_case['id']}: {test_case['name']}")
        print(f"   查询: {test_case['query_template'].format(advertiser_id=args.advertiser_id)}")

        result = await run_single_test(test_case, args.advertiser_id, args.verbose)

        # 打印测试结果
        print(f"   状态: {result['status']}")
        print(f"   分析类型: {result['analysis_type']}")
        if result["status"] == "success":
            print(f"   数据点数量: {result['data_points']}")
            print(f"   包含图表配置: {'是' if result['has_chart_config'] else '否'}")
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

    print("\n=== 📊 测试汇总报告 ===")
    print(f"总测试用例数: {len(test_results)}")
    print(f"成功: {success_count}")
    print(f"需要澄清: {clarification_count}")
    print(f"失败: {error_count}")
    print(f"总耗时: {total_time}s")

    # 打印失败的测试详情
    if error_count > 0:
        print("\n=== ❌ 失败测试详情 ===")
        for result in test_results:
            if result["status"] == "error":
                print(f"测试 {result['test_id']}: {result['test_name']}")
                print(f"错误: {result['error_message']}")
                print("-" * 40)

    # 保存结果到文件
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(test_results, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 结果已保存到文件: {output_path.resolve()}")

    # 设置退出码
    if error_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())