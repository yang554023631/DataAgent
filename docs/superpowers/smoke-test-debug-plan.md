# CoT 全量冒烟测试调试计划

> 生成日期：2026-08-10

---

## Phase A：基础场景（验证主干链路）

| 测试 | 场景 | 用户输入 Prompt | 状态 |
|---|---|---|---|
| #1 | Simple time trend — 无筛选单指标趋势 | 广告主{advertiser_id}最近7天的消耗趋势 | ⏳ |
| #7 | Summary KPI — 核心数据汇总 | 广告主{advertiser_id}4月份的核心数据 | ⏳ |

---

## Phase B：筛选场景（验证筛选链路）

| 测试 | 场景 | 用户输入 Prompt | 状态 |
|---|---|---|---|
| #2 | Entity table + where filter | 广告主{advertiser_id}下状态为投放中的广告计划4月份的消耗和点击 | ⏳ |
| #3 | Entity table + having filter | 广告主{advertiser_id}4月份消耗大于10的广告计划有哪些 | ⏳ |

---

## Phase C：复杂场景（验证高级功能）

| 测试 | 场景 | 用户输入 Prompt | 状态 |
|---|---|---|---|
| #4 | Period comparison — 周期对比 | 广告主{advertiser_id}4月的消耗和3月比怎么样 | ⏳ |
| #5 | Audience distribution — 受众分布 | 广告主{advertiser_id}4月份的消耗按性别分布 | ⏳ |
| #6 | Multi-series trend + having | 广告主{advertiser_id}4月份消耗>10的广告计划的消耗趋势图 | ⏳ |

---

## 全量回归

```bash
python scripts/cot_smoke_test.py --verbose --output smoke_test_results.json
```

| 项 | 状态 |
|---|---|
| 全量 7 个测试 + 结果存档 | ⏳ |
