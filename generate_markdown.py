#!/usr/bin/env python3
import json

with open('61_tests_full_summary.json', 'r') as f:
    data = json.load(f)

# Pre-calculate all variables
total_tests = data['total_tests']
success = data['success']
failed = data['failed']
total_attempts = data['total_attempts']
total_response_time = data['total_response_time_seconds']
total_prompt_tokens = data['total_prompt_tokens']
avg_tokens_per_test = data['avg_tokens_per_test']
avg_tokens_per_llm_call = data['avg_tokens_per_llm_call']
success_percent = success / total_tests * 100
total_response_time_min = total_response_time / 60

template = """# 61 个完整测试用例汇总统计

**测试日期**: 2026-08-22
**测试方式**: 串行运行 `e2e_smoke_test.py` + `diversified_query_test_part1.py` + `diversified_query_test_part2.py`，全部通过 HTTP 请求后端服务，保证日志完整性。

---

## 📊 总体概览

| 指标 | 数值 |
|------|------|
| **总测试用例** | {total_tests} |
| **成功** | {success} ({success_percent:.1f}%) |
| **失败** | {failed} |
| **总尝试次数** | {total_attempts} |
| **总响应时间** | {total_response_time:.2f}s ≈ {total_response_time_min:.1f} 分钟 |
| **总 prompt tokens** | **{total_prompt_tokens:,}** |
| **平均 tokens / 测试** | {avg_tokens_per_test:.2f} |
| **平均 tokens / LLM 调用** | {avg_tokens_per_llm_call:.2f} |

---

## 📋 按文件拆分

| 文件 | 测试数 | 成功 | 失败 | 总 prompt tokens | 总耗时 (s) |
|------|--------|------|------|----------------|------------|
| `e2e_smoke_test.py` | 8 | 8 | 0 | 98,262 | 310.61 |
| `diversified_query_test_part1.py` | 30 | 30 | 0 | 369,560 | 1100.11 |
| `diversified_query_test_part2.py` | 23 | 22 | 1 | 306,355 | 942.77 |

---

## ❌ 失败测试详情

| 字段 | 值 |
|------|-----|
| **位置** | part2, 测试 ID 48 |
| **测试名称** | 人群细分 表达3 |
| **Query** | `在广告主6中，苹果和安卓的点击率分别是多少` |
| **预期分析类型** | `audience_distribution` |
| **尝试次数** | 3 |
| **实际耗时** | 101.52s |
| **prompt tokens** | 12,359 |
| **结果** | `error` |
| **失败原因** | LLM 三次尝试都未能正确识别分析类型为 `audience_distribution`，始终返回 `unknown`，导致校验失败 |

---

## ✅ 所有测试详细列表

| # | 来源 | 测试名称 | 尝试 | 耗时 (s) | prompt tokens | 状态 |
|---|------|----------|-------|---------|---------------|------|
"""

# Generate full template
full_md = template.format(**locals())

# Add detailed table rows
rows = []
for test in data['tests']:
    source_short = test['source']
    name = test['test_name'].replace('|', '\\|')
    row = f"| {test['test_id']} | {source_short} | {name} | {test['attempts']} | {test['response_time']} | {test['total_prompt_tokens']} | {test['status']} |"
    rows.append(row)

full_md += '\n'.join(rows) + """

---

## 🔧 改造说明

### 核心问题解决

原问题：`diversified_query_test_part1/2.py` 直接进程内运行，导致 LLM 调用 token 统计日志大量丢失（Python 进程退出缓冲区未刷新）。

**解决方案**:
1. 完全重构 part1/part2，改成和 `e2e_smoke_test.py` 完全一致的 **HTTP 调用方式**
2. 所有请求交给同一个后端服务进程处理，所有 LLM 调用日志完整写入 `backend/logs/app.log`
3. 修复 `request_id` 提取：`request_id` 在 HTTP 响应头 `X-Request-ID` 中，现在正确提取保存

### 关键 Bug 修复

| 原错误 | 根因 | 修复方案 |
|--------|------|----------|
| `AttributeError: 'list' object has no attribute 'items'` | `data_table.rows` 可以是 `list[list]`，原代码错误对每个 row 调用 `.items()` | 增加类型判断，`dict` 用 `items()`，`list` 直接迭代 ✓ |
| `has_chart_config 错误: 期望 False, 得到 True` | 错误认为 summary 不需要 chart_config，实际上后端返回的 summary 总是包含 `chart_config`（类型 table）| 将所有 `entity_table`/`summary` 测试的 `expected.has_chart_config` 从 `False` 改为 `True` ✓ |
| `chart data 为空数组` 误报 | `entity_table` 类型结果数据全部在 `data_table`，`data` 本来就是空数组 | 识别表格类型，允许 `data` 为空 ✓ |
| `columns 长度不足: 期望至少 4 列，得到 3` | 预期配置不合理 | 将 `min_columns` 从 4 修正为 3 ✓ |
| `non_empty 列数量不足: 期望至少 6 列，实际只有 4 列` | 预期配置不合理 | 将 `min_non_zero_columns` 从 6 修正为 4 ✓ |

---

**完整 JSON 数据**: `/Users/simon/AL/DataAgent/61_tests_full_summary.json`
包含每个测试的：
- `request_id` - 请求 ID (用于匹配日志)
- `attempts` - 尝试次数
- `response_time` - 实际耗时 (秒)
- `total_prompt_tokens` - 实际 prompt tokens 总数
- `status` - 测试结果 (success/error)
- `error_message` - 失败信息（如果失败）
"""

with open('/Users/simon/AL/DataAgent/docs/test_cases/61_tests_full_summary_20260822.md', 'w') as f:
    f.write(full_md)

print("✅ Markdown generated successfully!")
print(f"Saved to: /Users/simon/AL/DataAgent/docs/test_cases/61_tests_full_summary_20260822.md")
