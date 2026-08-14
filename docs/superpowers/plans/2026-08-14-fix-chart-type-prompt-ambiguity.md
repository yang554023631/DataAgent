# 修复图表类型选择歧义问题 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修改prompt中的图表类型适用场景描述，消除歧义，让LLM能够正确为audience_distribution选择pie图表。

**Architecture:** 只修改prompt文本，不涉及代码逻辑改动。保持现有架构不变，只是优化LLM的指导说明。

**Tech Stack:** 现有Python/FastAPI/LLM架构不变，只修改字符串内容。

## Global Constraints

- 只修改 `backend/src/analysis/prompts.py` 中的 `COT_SYSTEM_PROMPT`
- 保持其他代码完全不变
- 修改后运行e2e测试5，验证LLM现在能正确选择pie

---

## 文件修改

| 文件 | 操作 | 改动范围 |
|------|------|----------|
| `backend/src/analysis/prompts.py` | 修改 | 第83-107行（可用图表类型）+ 新增分析类型推荐图表小节 |

---

### Task 1: 修改prompt中的图表类型说明和新增推荐表格

**Files:**
- Modify: `backend/src/analysis/prompts.py:83-107`

**Interfaces:**
- Consumes: 无（纯文本修改）
- Produces: 更新后的 `COT_SYSTEM_PROMPT`

- [ ] **Step 1: 替换原有的图表类型说明**

找到原有内容：
```python
## 可用的图表类型（chart type）
- line: 折线图（适合时间趋势）
- bar: 柱状图（适合对比、分布）
- pie: 饼图（适合占比分布）
- table: 表格（适合明细数据）
```

替换为：

```python
## 可用的图表类型（chart type）
- line: 折线图（适合时间趋势）
- bar: 柱状图（适合**同一指标在不同类别之间的数值对比**，例如：广告主6 三四月份的消耗对比；广告主6 三四月份的消耗和点击对比（每个指标分别对比两个月份，多系列柱状图））
- pie: 饼图（适合占比分布，特别是受众分布场景，比如按性别、年龄、操作系统、系统版本、兴趣、国家、城市等受众维度的分布）
- table: 表格（适合明细数据，展示多个实体多个指标的详细数值）

### 分析类型与推荐图表
根据分析类型，请优先选择以下图表：
- time_trend（时间趋势）→ line（必须使用折线图）
- period_comparison（时期对比）→ bar（柱状图）
- audience_distribution（受众分布）→ pie（饼图，展示占比）
- entity_table（实体列表）→ table（表格，展示明细列表）
- summary（数据摘要）→ table（表格）
```

- [ ] **Step 2: 验证修改后的语法**

检查：
- 字符串引号闭合正确
- 缩进格式保持和原有一致
- 没有破坏f-string模板（今天日期的占位符 `{today_date}` 需要保持不变）

- [ ] **Step 3: Commit**

```bash
git add backend/src/analysis/prompts.py
git commit -m "docs: fix chart type prompt ambiguity - clarify audience_distribution -> pie"
```

### Task 2: 运行测试5验证修改生效

**Files:**
- Run: `scripts/e2e_smoke_test.py` 只跑测试5

**Interfaces:**
- Consumes: 修改后的prompt
- Produces: 测试结果验证LLM选择pie

- [ ] **Step 1: 运行测试5**

```bash
cd /Users/simon/AL/DataAgent
python3 scripts/e2e_smoke_test.py --timeout 120
```
（脚本会依次跑所有测试，找到测试5看其chart_type）

- [ ] **Step 2: 检查结果**

验证：测试5的返回 `chart_config.type == "pie"`

- [ ] **Step 3: Commit 如果有需要（没有变更就跳过）**
