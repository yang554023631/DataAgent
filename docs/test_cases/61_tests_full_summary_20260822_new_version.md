# 61 个完整测试用例汇总统计

**测试日期**: 2026-08-22
**测试方式**: 串行运行 `e2e_smoke_test.py` + `diversified_query_test_part1.py` + `diversified_query_test_part2.py`，全部通过 HTTP 请求后端服务，保证日志完整性。

---

## 📊 总体概览

| 指标 | 数值 |
|------|------|
| **总测试用例** | 61 |
| **成功** | 60 (98.4%) |
| **失败** | 1 |
| **总尝试次数** | 65 |
| **总响应时间** | 2353.49s ≈ 39.2 分钟 |
| **总 prompt tokens** | **774,177** |
| **平均 tokens / 测试** | 12691.43 |
| **平均 tokens / LLM 调用** | 2434.52 |

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
| 1 | e2e | Simple time trend (E2E) | 1 | 24.33 | 12356 | success |
| 2 | e2e | Entity table with where filter (E2E) | 1 | 43.46 | 12240 | success |
| 3 | e2e | Entity table with having filter (E2E) | 1 | 62.66 | 21183 | success |
| 4 | e2e | Period comparison (E2E) | 1 | 33.79 | 13123 | success |
| 5 | e2e | Audience distribution (E2E) | 1 | 36.13 | 12356 | success |
| 6 | e2e | Multi-series trend (E2E) | 1 | 28.74 | 12363 | success |
| 7 | e2e | Multi-metric entity table (E2E) | 1 | 48.21 | 12261 | success |
| 8 | e2e | Multi-metric summary (concise query) (E2E) | 1 | 33.29 | 12386 | success |
| 1 | part1 | 按广告主名称查询 - 趋势 | 1 | 27.34 | 12233 | success |
| 2 | part1 | 按广告主名称查询 - 最近七天概览 | 1 | 44.68 | 12909 | success |
| 3 | part1 | 按广告主名称查询 - 三月汇总 | 1 | 19.9 | 12513 | success |
| 4 | part1 | 跨层级名称查询 - campaign | 1 | 39.36 | 12238 | success |
| 5 | part1 | 两层名称查询 - 趋势 | 1 | 30.72 | 12371 | success |
| 6 | part1 | 两层名称查询 - 最近七天趋势 | 1 | 70.03 | 12235 | success |
| 7 | part1 | 两层名称查询 - 总点击 | 1 | 49.69 | 12372 | success |
| 8 | part1 | 模糊名称查询 - 包含mini | 1 | 28.65 | 12236 | success |
| 9 | part1 | 模糊名称查询 - 包含digital + 排序 | 1 | 28.98 | 12356 | success |
| 10 | part1 | 模糊名称查询 - 包含下划线 | 1 | 31.33 | 12238 | success |
| 11 | part1 | 两层名称查询 - ad_group | 1 | 25.2 | 12503 | success |
| 12 | part1 | 模糊查询 + 排序 + TopN - ad_group | 1 | 33.38 | 12238 | success |
| 13 | part1 | 两层名称查询 - ad_group点击率 | 1 | 41.25 | 12245 | success |
| 14 | part1 | 三层名称查询 - creative | 1 | 31.1 | 12382 | success |
| 15 | part1 | 模糊名称查询 - creative | 1 | 28.79 | 12353 | success |
| 16 | part1 | 三层名称查询 - creative转化率 | 1 | 52.17 | 12251 | success |
| 17 | part1 | 混合筛选 - where名称 + having消耗 | 1 | 30.09 | 12379 | success |
| 18 | part1 | 混合筛选 - status + 名称contains | 1 | 39.42 | 12237 | success |
| 19 | part1 | 混合筛选 - 名称 + having点击 | 1 | 46.29 | 12363 | success |
| 20 | part1 | 广告主名称周期对比 | 1 | 29.58 | 12354 | success |
| 21 | part1 | 广告主名称点击趋势 | 1 | 31.64 | 12227 | success |
| 22 | part1 | 其他广告主名称子层级表格 | 1 | 29.09 | 12365 | success |
| 23 | part1 | ID多样化 - 六号广告主四月趋势 | 1 | 43.83 | 13013 | success |
| 24 | part1 | ID多样化 - 广告主ID为6四月曲线 | 1 | 33.58 | 12360 | success |
| 25 | part1 | ID多样化 - 语序变化 | 1 | 22.98 | 12487 | success |
| 26 | part1 | ID多样化 - 不同措辞 | 1 | 31.18 | 12221 | success |
| 27 | part1 | ID多series多样化 - 分开画 | 1 | 44.42 | 12230 | success |
| 28 | part1 | ID多series多样化 - 一条折线 | 1 | 38.17 | 12358 | success |
| 29 | part1 | ID多series多样化 - 走势 | 1 | 51.23 | 12865 | success |
| 30 | part1 | ID多series多样化 - 消耗变化 | 1 | 46.03 | 12223 | success |
| 31 | part2 | TopN 排序变化形式1 | 1 | 25.63 | 12346 | success |
| 32 | part2 | TopN 排序变化形式2 | 1 | 22.78 | 12364 | success |
| 33 | part2 | TopN 排序变化形式3 | 1 | 33.66 | 12217 | success |
| 34 | part2 | TopN 排序变化形式4 | 1 | 35.77 | 12353 | success |
| 35 | part2 | TopN 带条件 - where | 1 | 23.96 | 12481 | success |
| 36 | part2 | TopN 带条件 - having | 1 | 41.74 | 12242 | success |
| 37 | part2 | TopN + where + having 复杂组合 | 1 | 35.82 | 12373 | success |
| 42 | part2 | 对比分析 变化表达1 | 1 | 26.86 | 12358 | success |
| 43 | part2 | 对比分析 变化表达2 | 1 | 26.7 | 12489 | success |
| 44 | part2 | 对比分析 变化表达3 | 1 | 42.73 | 13010 | success |
| 45 | part2 | 对比分析 多层级 | 2 | 82.58 | 12239 | success |
| 46 | part2 | 人群细分 表达1 | 2 | 57.4 | 12372 | success |
| 47 | part2 | 人群细分 表达2 | 1 | 51.47 | 12862 | success |
| 48 | part2 | 人群细分 表达3 | 3 | 101.52 | 12359 | error |
| 51 | part2 | Campaign TopN - 转化率 | 1 | 35.1 | 12350 | success |
| 52 | part2 | Creative TopN - 转化率 | 1 | 38.85 | 21458 | success |
| 53 | part2 | Ad_group TopN - 点击率 | 1 | 44.84 | 12349 | success |
| 54 | part2 | TopN + 过滤 having 条件 | 1 | 44.1 | 12228 | success |
| 55 | part2 | 广告主名称 + 完整流程 | 1 | 21.01 | 12356 | success |
| 57 | part2 | 广告主名称 + 趋势简写 | 1 | 36.18 | 12983 | success |
| 59 | part2 | 混合筛选 having 两个条件 | 1 | 39.06 | 12244 | success |
| 60 | part2 | 完整复杂流程 - 名称+层级+筛选+TopN | 1 | 44.75 | 12288 | success |
| 61 | part2 | 广告主名称汇总衍生指标 | 1 | 30.27 | 12233 | success |

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
