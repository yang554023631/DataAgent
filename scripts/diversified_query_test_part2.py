#!/usr/bin/env python3
"""
多样化自然语言Query测试脚本 - Part 2 (ID 31-61)

运行我们构造的60个多样化query，分为两部分并行跑提高效率。
"""
import argparse
import sys
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests

# 默认后端地址
DEFAULT_BASE_URL = "http://localhost:8000"

# 定义60个多样化测试用例（来自 docs/test_cases/diversified_nl_queries.md）
# 此文件包含 Part 2: ID 31-61
DIVERSIFIED_TEST_CASES: List[Dict[str, Any]] = [
    {
        "id": 31,
        "name": "TopN 排序变化形式1",
        "query": "广告主6下面找出消耗最高的前五名广告计划",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
        "prediction": "预期成功",
        "prediction_reason": "表述清晰，接近原模板",
        "expected": {
            "has_chart_config": True,
            "min_rows": 5,
            "min_columns": 3,
            "min_non_zero_columns": 2,
        }
    },
    {
        "id": 32,
        "name": "TopN 排序变化形式2",
        "query": "广告主6，把所有广告计划按点击从高到低排，只看前3",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
        "prediction": "预期成功",
        "prediction_reason": "语序不同但关键词都在",
        "expected": {
            "has_chart_config": True,
            "min_rows": 3,
            "min_columns": 3,
            "min_non_zero_columns": 2,
        }
    },
    {
        "id": 33,
        "name": "TopN 排序变化形式3",
        "query": "帮我找出广告主6，消耗最少的五个广告计划",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
        "prediction": "可能失败",
        "prediction_reason": "\"最少\"升序，模型可能搞错排序方向",
        "expected": {
            "has_chart_config": True,
            "min_rows": 5,
            "min_columns": 3,
            "min_non_zero_columns": 2,
        }
    },
    {
        "id": 34,
        "name": "TopN 排序变化形式4",
        "query": "给我看广告主6转化率前五的广告组",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "ad_group",
        "prediction": "预期成功",
        "prediction_reason": "结构清晰",
        "expected": {
            "has_chart_config": True,
            "min_rows": 5,
            "min_columns": 3,
            "min_non_zero_columns": 2,
        }
    },
    {
        "id": 35,
        "name": "TopN 带条件 - where",
        "query": "广告主6，投放中的广告计划中，消耗前五是哪些",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
        "prediction": "可能失败",
        "prediction_reason": "where+TopN组合，需要增加一步where",
        "expected": {
            "has_chart_config": True,
            "min_rows": 1,
            "min_columns": 3,
            "min_non_zero_columns": 2,
        }
    },
    {
        "id": 36,
        "name": "TopN 带条件 - having",
        "query": "广告主6，点击量大于50的创意，转化率最高的三个",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "creative",
        "prediction": "可能失败",
        "prediction_reason": "where+having+TopN，组合非常复杂",
        "expected": {
            "has_chart_config": True,
            "min_rows": 3,
            "min_columns": 4,
            "min_non_zero_columns": 1,
        }
    },
    {
        "id": 37,
        "name": "TopN + where + having 复杂组合",
        "query": "广告主6，投放中，消耗超过100，转化率前三的广告组",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "ad_group",
        "prediction": "很可能失败",
        "prediction_reason": "多条件组合，结构复杂",
        "expected": {
            "has_chart_config": True,
            "min_rows": 3,
            "min_columns": 5,
            "min_non_zero_columns": 1,
        }
    },
    {
        "id": 42,
        "name": "对比分析 变化表达1",
        "query": "广告主6三月份比四月份消耗多了还是少了",
        "expected_analysis_type": "period_comparison",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "表述口语化，但对比很明确",
        "expected": {
            "has_chart_config": True,
            "min_non_zero_columns": [1, 2],
            "metrics": ["cost"],
        }
    },
    {
        "id": 43,
        "name": "对比分析 变化表达2",
        "query": "广告主6四月份消耗相比上一个月变化了多少",
        "expected_analysis_type": "period_comparison",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "关键词都在",
        "expected": {
            "has_chart_config": True,
            "min_non_zero_columns": [1, 2],
            "metrics": ["cost"],
        }
    },
    {
        "id": 44,
        "name": "对比分析 变化表达3",
        "query": "广告主6 四月份和三月份相比增长了多少",
        "expected_analysis_type": "period_comparison",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "相对时间对比，有一定难度但预期能识别",
        "expected": {
            "has_chart_config": True,
            "min_non_zero_columns": [1, 2],
            "metrics": ["cost"],
            "skip_title_check": True,
        }
    },
    {
        "id": 45,
        "name": "对比分析 多层级",
        "query": "对比 广告主6 下 top3消耗计划，四月份和三月份的消耗变化",
        "expected_analysis_type": "period_comparison",
        "expected_target_level": "campaign",
        "prediction": "很可能失败",
        "prediction_reason": "TopN+对比，双重复杂结构",
        "expected": {
            "has_chart_config": True,
            "min_non_zero_columns": [3, 6],
        }
    },
    {
        "id": 46,
        "name": "人群细分 表达1",
        "query": "广告主6四月份，分性别看消耗和转化率",
        "expected_analysis_type": "audience_distribution",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "结构清晰，标准表述",
        "expected": {
            "has_chart_config": True,
            "min_non_zero_columns": 2,
        }
    },
    {
        "id": 47,
        "name": "人群细分 表达2",
        "query": "广告主6各个年龄段分别花了多少钱",
        "expected_analysis_type": "audience_distribution",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "句式不同，需求清晰",
        "expected": {
            "has_chart_config": True,
            "min_non_zero_columns": 1,
        }
    },
    {
        "id": 48,
        "name": "人群细分 表达3",
        "query": "在广告主6中，苹果和安卓的点击率分别是多少",
        "expected_analysis_type": "audience_distribution",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "枚举值对比，需求清晰",
        "expected": {
            "has_chart_config": True,
            "min_non_zero_columns": 2,
        }
    },
    {
        "id": 51,
        "name": "Campaign TopN - 转化率",
        "query": "广告主6转化率最高的三个广告计划",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
        "prediction": "预期成功",
        "prediction_reason": "结构清晰，只是用转换率",
        "expected": {
            "has_chart_config": True,
            "min_rows": 3,
            "min_columns": 3,
            "min_non_zero_columns": 2,
        }
    },
    {
        "id": 52,
        "name": "Creative TopN - 转化率",
        "query": "广告主6转化率最高的三个创意",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "creative",
        "prediction": "预期成功",
        "prediction_reason": "结构清晰，数字+指标能匹配吗？",
        "expected": {
            "has_chart_config": True,
            "min_rows": 3,
            "min_columns": 3,
            "min_non_zero_columns": 2,
        }
    },
    {
        "id": 53,
        "name": "Ad_group TopN - 点击率",
        "query": "广告主6点击率最低的两个广告组是什么",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "ad_group",
        "prediction": "可能失败",
        "prediction_reason": "最低 = 升序，排序方向容易错",
        "expected": {
            "has_chart_config": True,
            "min_rows": 2,
            "min_columns": 3,
            "min_non_zero_columns": 2,
        }
    },
    {
        "id": 54,
        "name": "TopN + 过滤 having 条件",
        "query": "广告主6点击大于100的计划中点击率前五名",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "campaign",
        "prediction": "可能失败",
        "prediction_reason": "having过滤 + TopN，两步需要正确顺序",
        "expected": {
            "has_chart_config": True,
            "min_rows": 5,
            "min_columns": 4,
            "min_non_zero_columns": 2,
        }
    },
    {
        "id": 55,
        "name": "广告主名称 + 完整流程",
        "query": "广告主 digital_0 四月份按星期统计消耗",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "按星期统计消耗，模型识别为时间趋势，实际按天分组后按星期聚合是合理的",
        "expected": {
            "has_chart_config": True,
            "min_non_zero_columns": 1,
            "y_axis_field": "cost",
        }
    },
    {
        "id": 57,
        "name": "广告主名称 + 趋势简写",
        "query": "广告主 digital_0 四月 消耗曲线",
        "expected_analysis_type": "time_trend",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "名称匹配+四月，能解析时间了",
        "expected": {
            "has_chart_config": True,
            "min_non_zero_columns": 1,
            "y_axis_field": "cost",
        }
    },
    {
        "id": 59,
        "name": "混合筛选 having 两个条件",
        "query": "广告主6找出消耗大于100且转化率大于0.02的创意",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "creative",
        "prediction": "很可能失败",
        "prediction_reason": "having两个条件，需要写出两个conditions",
        "expected": {
            "has_chart_config": True,
            "min_rows": 1,
            "min_columns": 4,
            "min_non_zero_columns": 2,
        }
    },
    {
        "id": 60,
        "name": "完整复杂流程 - 名称+层级+筛选+TopN",
        "query": "广告主 digital_0下，找出四月份转化大于 1 并且转化率大于 0.01 的创意，按转化率排序，只看前 5 个",
        "expected_analysis_type": "entity_table",
        "expected_target_level": "creative",
        "prediction": "预期成功",
        "prediction_reason": "完整复杂链路：名称匹配+where+having+TopN，条件放宽后有数据",
        "expected": {
            "has_chart_config": True,
            "min_rows": 5,
            "min_columns": 5,
            "min_non_zero_columns": 3,
        }
    },
    {
        "id": 61,
        "name": "广告主名称汇总衍生指标",
        "query": "广告主 digital_0 四月份的点击率是多少",
        "expected_analysis_type": "summary",
        "expected_target_level": "advertiser",
        "prediction": "预期成功",
        "prediction_reason": "测试summary中衍生指标计算，修复后应该成功",
        "expected": {
            "has_chart_config": True,
            "min_rows": 1,
            "min_columns": 2,
        }
    },
]


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="多样化自然语言Query测试 - Part 2 (ID 31-61)")
    parser.add_argument(
        "--tests",
        type=str,
        help="指定要运行的测试ID，逗号分隔，例如 31,32,33"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="每个query最多重试次数（默认2次：1次初始+1次重试）"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="每个请求超时时间秒数（默认 300s）"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"后端服务地址（默认 {DEFAULT_BASE_URL}）"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="打印详细信息"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="diversified_test_results_part2.json",
        help="将结果保存到JSON文件（默认: diversified_test_results_part2.json）"
    )
    return parser.parse_args()


def create_session(base_url: str, timeout: float) -> Optional[str]:
    """创建新会话，返回session_id"""
    url = f"{base_url}/api/sessions"
    try:
        resp = requests.post(url, json={"user_id": "diversified-test-part2"}, timeout=timeout)
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
        data = resp.json()
        # 从响应头提取 request_id，放到返回数据中
        request_id = resp.headers.get("X-Request-ID")
        if request_id:
            data["request_id"] = request_id
        return data
    except Exception:
        return None


def _is_non_zero_value(val) -> bool:
    """检查一个值是否非零，处理字符串格式化的数值"""
    if val is None or val == "":
        return False
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        # 处理格式化字符串如 "466,529.0" → 去掉逗号 → 转浮点数
        try:
            cleaned = val.replace(",", "").strip()
            num = float(cleaned)
            return num != 0
        except (ValueError, TypeError):
            # 不是数字，视为非零（有内容就算非零）
            return True
    return False


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
    # 这里 diversified 测试预期已经在外部比较，不用重复校验了
    # 只需要校验 chart_type 和 has_chart_config

    # 3. 列数校验
    expected_cols = expected.get("columns_len")
    min_cols = expected.get("min_columns", 0)
    data_table = data["data_table"]
    rows = data_table.get("rows", [])

    if expected_cols is not None:
        if not rows:
            return False, f"data_table.rows 为空，期望 columns_len 是 {expected_cols}"
        first_row = rows[0]
        got_cols = len(first_row)
        if got_cols not in expected_cols:
            return False, f"columns长度错误: 期望 {expected_cols} 其中之一，得到 {got_cols}"
    elif min_cols > 0:
        if not rows:
            return False, f"data_table.rows 为空，期望至少 {min_cols} 列"
        first_row = rows[0]
        got_cols = len(first_row)
        if got_cols < min_cols:
            return False, f"columns长度不足: 期望至少 {min_cols} 列，得到 {got_cols}"

    # 4. 行数校验（min_rows 和 max_rows）
    if "min_rows" in expected:
        # min_rows 始终是数字，最少 N 行
        if len(rows) < expected["min_rows"]:
            return False, f"data_table.rows 行数不足: 期望至少 {expected['min_rows']} 行，得到 {len(rows)} 行"
    if "max_rows" in expected:
        if len(rows) > expected["max_rows"]:
            return False, f"data_table.rows 行数过多: 期望最多 {expected['max_rows']} 行，得到 {len(rows)} 行"

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
                        if _is_non_zero_value(v):
                            numeric_values.append(float(v) if isinstance(v, (int, float)) else 0)

        if data_table and rows:
            for row in rows:
                if isinstance(row, dict):
                    for key, cell in row.items():
                        if _is_non_zero_value(cell):
                            if isinstance(cell, (int, float)):
                                numeric_values.append(cell)
                            elif isinstance(cell, dict) and "value" in cell:
                                val = cell["value"]
                                if isinstance(val, (int, float)):
                                    numeric_values.append(float(val))
                elif isinstance(row, list):
                    for cell in row:
                        if _is_non_zero_value(cell):
                            if isinstance(cell, (int, float)):
                                numeric_values.append(cell)
                            elif isinstance(cell, dict) and "value" in cell:
                                val = cell["value"]
                                if isinstance(val, (int, float)):
                                    numeric_values.append(float(val))

        if numeric_values:
            all_zero = all(v == 0 for v in numeric_values if v is not None)
            if all_zero and not expected.get("allow_all_zero", True):
                return False, "所有数值都为0，预期应该有非零值"

    # 5. 检查至少有 min_non_zero_columns 列包含非零值
    min_non_zero_cols = expected.get("min_non_zero_columns")
    if min_non_zero_cols is not None and data_table and rows:
        # 对于每一列，统计有多少非零值
        # columns_info 可能是:
        # - [{"key": "date", "label": "日期"}, ...] (dict 格式行时)
        # - ["日期", "campaign ID", ...] (list 格式行时，label 直接作为字符串)
        columns_info = data_table.get("columns", [])
        if not columns_info:
            if rows and len(rows) > 0:
                num_cols = len(rows[0])
            else:
                num_cols = 0
        else:
            num_cols = len(columns_info)

        # 统计每列非空值数量
        non_empty_count_per_col = [0] * num_cols
        for row in rows:
            # row 可能是 dict 也可能是 list
            if isinstance(row, dict):
                i = 0
                for col in columns_info:
                    key = col.get("key") if isinstance(col, dict) else col
                    val = row.get(key)
                    if _is_non_zero_value(val):
                        non_empty_count_per_col[i] += 1
                    i += 1
            elif isinstance(row, list):
                for i, val in enumerate(row):
                    if i < len(non_empty_count_per_col) and _is_non_zero_value(val):
                        non_empty_count_per_col[i] += 1

        cols_with_non_empty = sum(1 for cnt in non_empty_count_per_col if cnt > 0)
        # 处理 min_non_zero_cols 可能是数组（允许多个值中的任意一个）
        if isinstance(min_non_zero_cols, list):
            if not any(cols_with_non_empty >= m for m in min_non_zero_cols):
                expected_min = " or ".join(str(m) for m in min_non_zero_cols)
                return False, (
                    f"非空列数量不足: 期望至少 {expected_min} 列包含非零值，"
                    f"实际只有 {cols_with_non_empty} 列有非空。各列非空计数: {non_empty_count_per_col}"
                )
        else:
            if cols_with_non_empty < min_non_zero_cols:
                return False, (
                    f"非空列数量不足: 期望至少 {min_non_zero_cols} 列包含非零值，"
                    f"实际只有 {cols_with_non_empty} 列有非空。各列非空计数: {non_empty_count_per_col}"
                )

    # 6. 检查has_chart_config
    has_chart_config = (
        "chart_config" in data
        and data["chart_config"] is not None
    )
    expected_has_chart = expected.get("has_chart_config", False)
    if has_chart_config != expected_has_chart:
        return False, f"has_chart_config错误: 期望 {expected_has_chart}, 得到 {has_chart_config}"

    # 7. 检查 chart data 结构
    if "data" in data and expected.get("has_chart_config"):
        chart_data = data["data"]
        if not isinstance(chart_data, list):
            return False, f"chart data 不是数组: 得到 {type(chart_data)}"
        # 对于趋势图/对比图，data 不能为空；对于表格图，data 本来就是空
        # 只有当 data_empty 不为 True，并且 data 不是表格类型时，才检查非空
        # 如果 chart_config.type 是 table 或者 chart_config 为空 → entity_table，允许 data 为空
        expected_data_empty = expected.get("data_empty", False)
        is_table_chart = False
        if "chart_config" in data and data["chart_config"]:
            chart_type = data["chart_config"].get("type")
            is_table_chart = (chart_type is None or chart_type == "table")
        else:
            # chart_config 不存在或者为空，也是表格
            is_table_chart = True
        if is_table_chart:
            # 表格类型，数据在 data_table 中，data 可以为空
            pass
        elif not expected_data_empty and len(chart_data) == 0:
            return False, "chart data 为空数组"
        # require_non_null 只检查指定的 y_axis_field 或者 value 不为 null
        if expected.get("require_non_null"):
            y_field = expected.get("y_axis_field")
            for i, point in enumerate(chart_data):
                if not isinstance(point, dict):
                    continue
                # 如果指定了 y_axis_field，检查那个字段不为 null
                if y_field:
                    if y_field not in point:
                        return False, f"chart data[{i}] 缺少 y_axis_field '{y_field}'"
                    if point[y_field] is None:
                        return False, f"chart data[{i}].{y_field} 为 null，预期应该有值"
                # 如果没指定 y_axis_field，回退到检查 value 字段（兼容对比图格式）
                elif "value" in point and point["value"] is None:
                    return False, f"chart data[{i}].value 为 null，预期应该有值"

            # 对于多系列趋势（测试6），检查补零完整性：每个日期点都应该包含所有系列
            # 如果第一个点有 N 个非 date 键，那么所有点都应该有 N 个非 date 键
            min_non_zero_cols = expected.get("min_non_zero_columns")
            # min_non_zero_cols is now always an array (per user requirement)
            # Check if any of the allowed min values > 1 to trigger this check
            need_series_check = False
            if min_non_zero_cols is not None and chart_data:
                if isinstance(min_non_zero_cols, list):
                    # If any required minimum > 1, we need the check
                    need_series_check = any(m > 1 for m in min_non_zero_cols)
                else:
                    need_series_check = min_non_zero_cols > 1
            if need_series_check and chart_data:
                # 获取第一个点的非 date 键数量，这个应该等于预期的系列数量
                first_point = chart_data[0]
                if isinstance(first_point, dict):
                    expected_series_count = len([k for k in first_point.keys() if k != "date"])
                    # 检查每个点都有相同数量的系列（补零保证每个日期都包含所有系列）
                    for i, point in enumerate(chart_data):
                        if not isinstance(point, dict):
                            continue
                        actual_count = len([k for k in point.keys() if k != "date"])
                        if actual_count != expected_series_count:
                            return False, (
                                f"chart data[{i}] 系列数量不匹配: 期望 {expected_series_count} 个系列，"
                                f"实际 {actual_count} 个。补零不完整，某些系列在该日期缺失。"
                            )

    # 8. 检查 chart_config.title 是否包含正确的指标名称（可选校验）
    if "chart_config" in data and data["chart_config"] and "metrics" in expected and not expected.get("skip_title_check"):
        # 使用第一个指标来判断
        metrics = expected["metrics"]
        if metrics and len(metrics) > 0:
            first_metric = metrics[0]
            # 指标名称映射（和后端保持一致）
            metric_display_map = {
                "cost": "消耗",
                "impressions": "曝光量",
                "clicks": "点击量",
                "ctr": "点击率",
                "cvr": "转化率",
                "spend": "花费",
                "conv": "转化",
            }
            expected_display = metric_display_map.get(first_metric, first_metric)
            actual_title = data["chart_config"].get("title", "")
            if expected_display not in actual_title:
                return False, f"chart_config.title 错误: 期望包含 '{expected_display}', 实际标题是 '{actual_title}'"

    return True, None


def run_single_test(
    test_case: Dict[str, Any],
    base_url: str,
    timeout: float,
    verbose: bool = False,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """运行单个测试用例，支持最多重试max_retries次，有一次成功就算成功"""
    start_time = time.time()
    query = test_case["query"]
    expected = test_case.get("expected", {})

    last_result = None
    last_error = None

    # 最多重试 max_retries 次，总共有 max_retries + 1 次尝试
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"   第 {attempt + 1} 次尝试...")

        # 1. 创建会话（每次重试都新建会话，避免状态污染）
        session_id = create_session(base_url, timeout)
        if not session_id:
            last_error = "创建会话失败，后端服务可能不可用"
            continue

        # 2. 发送消息
        api_result = send_message(base_url, session_id, query, timeout)
        if not api_result:
            last_error = "发送消息失败，无响应"
            continue

        # 3. 解析和校验
        last_result = api_result

        if api_result.get("status") != "completed":
            last_error = f"API返回状态异常: {api_result.get('status')}"
            continue

        result_data = api_result.get("result", {})
        final_report = result_data.get("final_report")

        if not final_report:
            last_error = "没有生成 final_report"
            continue

        # 解开 final_report
        if isinstance(final_report, dict) and "type" in final_report and "data" in final_report:
            data = final_report.get("data")
        else:
            data = final_report

        # 提取分析类型
        analysis_type = "unknown"
        target_level = "unknown"
        if data and "metadata" in data:
            metadata = data["metadata"]
            analysis_type = metadata.get("analysis_type", "unknown")
            target_level = metadata.get("target_level", "unknown")

        # 提取数据点数量
        data_points = 0
        if "data" in data:
            data_points += len(data.get("data", []))
        if "data_table" in data:
            data_points += len(data["data_table"].get("rows", []))

        # 检查是否所有数据都是零
        all_zero = False
        if data_points > 0:
            numeric_values: List[float] = []
            if "data" in data:
                for point in data.get("data", []):
                    for k, v in point.items():
                        if k != "date" and _is_non_zero_value(v):
                            numeric_values.append(float(v) if isinstance(v, (int, float)) else 0)
            if "data_table" in data:
                for row in data["data_table"].get("rows", []):
                    if isinstance(row, dict):
                        for key, cell in row.items():
                            if _is_non_zero_value(cell):
                                if isinstance(cell, (int, float)):
                                    numeric_values.append(cell)
                                elif isinstance(cell, dict) and "value" in cell:
                                    val = cell["value"]
                                    if isinstance(val, (int, float)):
                                        numeric_values.append(float(val))
                    elif isinstance(row, list):
                        for cell in row:
                            if _is_non_zero_value(cell):
                                if isinstance(cell, (int, float)):
                                    numeric_values.append(cell)
                                elif isinstance(cell, dict) and "value" in cell:
                                    val = cell["value"]
                                    if isinstance(val, (int, float)):
                                        numeric_values.append(float(val))
            if numeric_values:
                all_zero = all(v == 0 for v in numeric_values if v is not None)

        # 检查类型匹配
        expected_type = test_case.get("expected_analysis_type")
        type_mismatch = False
        if expected_type and analysis_type != expected_type:
            last_error = f"分析类型不匹配: 预期 {expected_type}, 实际 {analysis_type}"
            type_mismatch = True
            if attempt == max_retries:
                break
            continue

        # 校验结果结构
        if expected:
            ok, err_msg = validate_result(api_result, expected)
            if not ok:
                last_error = err_msg
                continue

        # 校验成功，直接返回结果
        elapsed_time = time.time() - start_time

        # 提取 request_id
        request_id = None
        if last_result and isinstance(last_result, dict):
            request_id = last_result.get("request_id")

        detailed_result = {
            "test_id": test_case["id"],
            "test_name": test_case["name"],
            "query": query,
            "expected_analysis_type": test_case.get("expected_analysis_type"),
            "expected_target_level": test_case.get("expected_target_level"),
            "prediction": test_case.get("prediction"),
            "prediction_reason": test_case.get("prediction_reason"),
            "status": "success",
            "analysis_type": analysis_type,
            "target_level": target_level,
            "data_points": data_points,
            "all_zero": all_zero,
            "type_mismatch": type_mismatch,
            "response_time": round(elapsed_time, 2),
            "error_message": None,
            "attempts": attempt + 1,
            "request_id": request_id,
        }

        if verbose:
            detailed_result["raw_response"] = api_result

        return detailed_result

    # 所有尝试都失败了
    elapsed_time = time.time() - start_time

    # 提取 request_id
    request_id = None
    if last_result and isinstance(last_result, dict):
        request_id = last_result.get("request_id")

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
        "error_message": f"{max_retries + 1}次尝试全部失败，最后一次错误: {last_error}",
        "request_id": request_id,
        "attempts": max_retries + 1,
        "raw_response": last_result,
    }


def generate_markdown_report(results: List[Dict[str, Any]], total_time: float, output_path: Path):
    """生成markdown测试报告"""
    success_count = sum(1 for r in results if r["status"] == "success")
    clarification_count = sum(1 for r in results if r["status"] == "needs_clarification")
    error_count = sum(1 for r in results if r["status"] == "error")
    total = len(results)

    md = f"# 多样化自然语言Query测试结果 - Part 2 (ID 31-61)\n\n"
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


def main():
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

    print(f"🚀 开始运行 多样化自然语言Query测试 - Part 2，共 {len(selected_tests)} 个测试用例")
    print(f"📋 每个query最多尝试次数: {args.max_retries + 1}")
    print(f"📌 后端地址: {args.base_url}")
    print(f"⌛ 单次请求超时: {args.timeout}s")
    print("-" * 80)

    # 检查后端是否连通
    try:
        resp = requests.get(f"{args.base_url}/health", timeout=5)
        if resp.status_code != 200:
            print(f"❌ 错误: 后端服务不健康，HTTP {resp.status_code}")
            sys.exit(1)
    except Exception:
        print(f"❌ 错误: 无法连接到后端服务 {args.base_url}，请确认服务已启动")
        sys.exit(1)
    print("✅ 后端连接正常\n")

    total_start_time = time.time()
    test_results: List[Dict[str, Any]] = []

    # 运行所有测试用例
    for test_case in selected_tests:
        print(f"🔹 运行测试 {test_case['id']}: {test_case['name']}")
        print(f"   查询: {test_case['query']}")

        result = run_single_test(
            test_case,
            args.base_url,
            args.timeout,
            args.verbose,
            args.max_retries,
        )

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

    print("\n=== 📊 测试汇总报告 - Part 2 ===")
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
    script_dir = Path(__file__).parent
    md_path = script_dir.parent / "docs/test_cases/diversified_test_results_part2.md"
    generate_markdown_report(test_results, total_time, md_path)
    print(f"✅ Markdown报告已保存: {md_path.resolve()}")

    # 设置退出码
    if error_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
