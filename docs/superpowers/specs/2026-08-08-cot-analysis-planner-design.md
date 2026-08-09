# CoT 驱动的分析规划器 设计文档

> **版本**: v1.1
> **日期**: 2026-08-09
> **状态**: Draft
> **范围**: 报表分析链路 — 从意图识别到图表数据生成的全流程重构
>
> **v1.1 更新（2026-08-09）**：补充 7 项设计决策 — 系统集成方案、错误处理与降级策略、性能与 SSE、Few-Shot 向量检索方案、跨层级筛选执行细节、派生指标筛选实现、四层测试与 Mock 策略

---

## 一、背景与目标

### 1.1 问题

当前报表分析链路存在以下核心问题：

1. **查询规划是一步式的**：LLM 一次性生成查询计划，缺乏多步推理，复杂场景（如带筛选的多实体趋势图）准确率低
2. **筛选与分析混杂**：没有明确区分"筛选哪些实体"和"对实体做什么分析"两个阶段，导致字段提取混乱、澄清逻辑不清晰
3. **图表选型与查询生成脱节**：先查数据再根据数据形态反推图表类型，而不是先确定图表再设计查询
4. **结果质量无保障**：查询结果不做质量校验（如趋势图超过20条线直接返回），用户体验差
5. **路由判断不准确**：关键词匹配的路由方式容易漏掉符号化表达（如 `>`、`<`），导致复杂查询走错路径

### 1.2 目标

- 引入 **CoT（链式思维）驱动的分析规划器**，将报表分析拆解为"筛选 → 分析"两阶段，每阶段逐步推理
- 建立结构化的**筛选计划**和**分析计划**，替代现有一步式查询规划
- 设计覆盖主要场景的 **few-shot 示例库**，每个示例均经过测试验证
- 增加**查询后质量校验**，不达标时触发 HITL 或自动修正
- 保持与现有 LangGraph 架构的兼容，平滑替换现有 report_intent + nl_dsl 链路

### 1.3 非目标

- 不引入 ToT / GoT 等更复杂的推理范式（当前阶段 CoT 足够）
- 不更换前端图表库（继续使用 ECharts）
- 不新增数据源（继续使用 ES）
- 不做语义层 / 指标平台

---

## 二、整体架构

### 2.1 核心思想

将报表分析拆解为 **筛选阶段** + **分析阶段** 两大步，每步内部通过 CoT 逐步推理，最终输出结构化的执行计划。

```
用户问题
  │
  ▼
┌──────────────────────────────────────────┐
│  Step 1: 两阶段识别 + 字段提取             │
│  ┌─────────────┐   ┌─────────────────┐   │
│  │  筛选识别     │   │   分析识别       │   │
│  │  - 类型判断   │   │  - 形态判断      │   │
│  │  - 条件提取   │   │  - 指标/维度提取 │   │
│  │  - 目标层级   │   │  - 图表类型      │   │
│  └──────┬──────┘   └────────┬────────┘   │
│         │  缺信息 → HITL澄清  │            │
└─────────┼───────────────────┼────────────┘
          ▼                   ▼
┌──────────────────────────────────────────┐
│  Step 2: 双计划生成                        │
│  - FilterPlan（筛选计划）                  │
│  - AnalysisPlan（分析计划）                │
│  - QualityChecks（质量校验规则）           │
└───────────────────┬──────────────────────┘
                      ▼
┌──────────────────────────────────────────┐
│  Step 3: 执行筛选计划                      │
│  逐步执行：DSL生成 → ES执行 → 结果校验     │
│  失败重试（最多2次）                       │
│  输出：目标实体ID列表                      │
└───────────────────┬──────────────────────┘
                      ▼
┌──────────────────────────────────────────┐
│  Step 4: 执行分析计划 + 质量校验            │
│  - 执行分析查询                             │
│  - 质量校验（条数/异常/空结果）             │
│  - 不达标 → 调整重试（最多1轮）             │
│  - 输出：chart_config + 数据表格            │
└───────────────────┬──────────────────────┘
                      ▼
                    前端渲染
```

### 2.2 在 LangGraph 中的位置（最终方案）

**全量替换**现有报表链路（`report_intent → planner/nl_dsl → reporter`），新增单个 `analysis_node` 节点。顶层 `intent_classifier` 保留，做三类意图分发（report / knowledge / out_of_domain）。

```
intent_classifier            ← 保留：顶层 3 类意图分类
       │
       ▼ report
  analysis_node              ← 新增：封装完整的 CoT 分析流水线
       │
       ▼
      END
```

**analysis_node 内部模块**（6 个，顺序执行）：

```
IntentAnalyzer → CotPlanner → FilterExecutor → AnalysisExecutor → QualityChecker → ReportFormatter
   (字段提取)    (CoT推理+计划)   (筛选执行)      (分析+图表组装)     (质量校验)       (报告包装)
```

**设计决策**：
- **不保留旧路径**：所有报表查询统一走 analysis_node，避免双路径维护成本
- **节点名称**：`analysis_node`（而非 analysis_planner / report_analyst），强调它是完整执行节点而非仅规划
- **广告主查询不做特殊短路**：即使是简单的广告主维度查询，也走完整 CoT 流程（简化架构，后续可用 P0 快速通道优化）
- **Insight 代码保留但不自动触发**：v1 中 insight/analyst 节点代码保留但不接入 graph，后续作为独立 intent（用户主动请求洞察）再设计回归方案
- **状态字段**：新增 `analysis_plan`、`field_context`、`filter_result`、`chart_data`、`cot_reasoning`、`execution_trace`、`final_report`，旧字段（`report_intent_result`、`query_plan` 等）全部废弃

---

## 三、结构化计划定义

### 3.1 FilterPlan（筛选计划）

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Any

class FilterCondition(BaseModel):
    """单个过滤条件"""
    field: str                           # 字段名，如 campaign_id、data_value、creative_name
    operator: str                        # = / != / > / < / >= / <= / contains / in / match
    value: Any                           # 条件值
    dimension_slice: Optional[dict] = None  # 受众维度切片，如 {audience_type: "gender", audience_tag: "male"}

class FilterStep(BaseModel):
    """单个筛选步骤"""
    step_id: str                         # step_1, step_2 ...
    step_type: str                       # where_filter / having_filter / cross_level_up / cross_level_down
    level: str                           # 本步操作的实体层级：advertiser / campaign / ad_group / creative
    index: str                           # 查询的索引：ad_stat_data / ad_stat_audience / campaign / adgroup / creative
    conditions: List[FilterCondition] = Field(default_factory=list)
    output_field: str                    # 输出的ID字段，如 campaign_id

class FilterPlan(BaseModel):
    """筛选计划"""
    filter_type: str                     # none / where / having / cross_level / mixed
    target_level: str                    # 最终目标实体层级
    steps: List[FilterStep] = Field(default_factory=list)
    entity_ids: Optional[List[str]] = None  # 预定义的实体ID（用户直接指定时）
```

### 3.2 AnalysisPlan（分析计划）

```python
class QualityCheck(BaseModel):
    """质量校验规则"""
    check_type: str                      # max_series_count / min_data_points / all_zero / max_rows
    threshold: Any                       # 阈值
    action: str                          # hitl / trim / warn / fail

class AnalysisPlan(BaseModel):
    """分析计划"""
    analysis_type: str                   # entity_table / period_comparison / audience_distribution / time_trend / summary
    chart_type: str                      # bar / line / pie / kpi_card / table
    metrics: List[str] = Field(default_factory=list)
    time_range: dict                     # {start_date, end_date}
    compare_time_range: Optional[dict] = None  # 周期对比用
    time_granularity: str = "day"        # day / week / month（趋势图用）
    audience_dimension: Optional[str] = None  # 受众分布用：gender / age / region ...
    group_by: Optional[str] = None       # 分组维度（多系列趋势等）
    quality_checks: List[QualityCheck] = Field(default_factory=list)
```

### 3.3 AnalysisPlan（顶层计划）

```python
class AnalysisPlan(BaseModel):
    """完整的分析计划 = 筛选计划 + 分析计划"""
    target_level: str                    # 目标实体层级
    filter_plan: FilterPlan
    analysis_plan: AnalysisPlan
```

---

## 四、筛选模型详解

### 4.1 筛选类型总览

| 类型 | 说明 | 步骤数 | 典型例子 |
|---|---|---|---|
| **none** | 不筛选，全量实体 | 0步（直接用层级条件） | "所有广告计划" |
| **where** | 属性/维度过滤（行级） | 1步 | "状态为投放中的计划" |
| **having** | 指标聚合后过滤 | 1步 | "消耗>10的计划" |
| **cross_level** | 跨层级筛选（自上而下或自下而上） | 1~2步 | "创意名包含XX的计划" |
| **mixed** | 混合筛选（where + having + 跨层级组合） | 多步 | "移动端的、消耗>10的计划" |

### 4.2 Where 型筛选

**特点**：行级过滤，直接加在 query.bool.filter 里
**索引选择**：
- 实体属性过滤 → 查维度表（campaign / adgroup / creative）
- 时间/指标维度过滤 → 查事实表（ad_stat_data）

**示例**：
- `campaign.status = enabled` → campaign 维度表 where
- `create_time >= 2026-01-01` → campaign 维度表 where
- `data_date in [4月]` → ad_stat_data where（时间范围，已作为全局过滤）

### 4.3 Having 型筛选

**特点**：先聚合再过滤，使用 bucket_selector pipeline agg
**数据源**：
- 普通指标 → ad_stat_data
- 受众维度限定指标 → ad_stat_audience（加 audience_type + audience_tag_value 过滤）

**示例**：
- "消耗>10的campaign" → ad_stat_data + terms(campaign_id) + sum + bucket_selector
- "男性受众消耗>10的campaign" → ad_stat_audience + audience_type=gender + tag=男 + terms(campaign_id) + sum + bucket_selector

### 4.4 跨层级筛选

两个方向：

#### 自下而上（cross_level_up）
低层级条件 → 高层级实体
- 例："creative_name 包含 XX 的 campaign"
- 路径：creative 表 match 查询 → terms(campaign_id) 聚合 → 去重的 campaign_id 列表

#### 自上而下（cross_level_down）
高层级条件 → 低层级实体
- 例："campaign_name 包含 XX 的 ad_group"
- 路径选择：
  - 低层级表有冗余字段 → 一步：直接在 adgroup 表过滤 campaign_name
  - 无冗余字段 → 两步：先查 campaign 表拿 ID → 再查 adgroup 表 where campaign_id in (...)

### 4.5 混合筛选

多种筛选条件组合时，查询计划的构造规则：

1. **全局过滤**（advertiser_id + data_date + data_type）：所有步骤都带上
2. **Where 条件**：能合并到同一步的就合并，不能合并的分别处理
3. **Having 条件**：需要独立步骤（因为要聚合）
4. **跨层级步骤**：放在最前面，拿到目标层级 ID 后，后续步骤都用 ID 过滤

**执行顺序**：跨层级筛选 → where 过滤 → having 过滤 → 得到最终实体ID列表

---

## 五、分析形态详解

### 5.1 五种分析形态

| 形态 | analysis_type | 图表类型 | 核心特征 |
|---|---|---|---|
| 实体指标表 | entity_table | bar / table | 每行一个实体，多列指标 |
| 周期对比 | period_comparison | bar / line | 两时间段对比 |
| 受众分布 | audience_distribution | pie / ring | 按受众维度的占比 |
| 时间趋势 | time_trend | line | 按时间粒度的变化曲线 |
| 单值汇总 | summary | kpi_card | 几个汇总数字 |

### 5.2 各形态必填信息与默认值

| 形态 | 必填（缺了澄清） | 可选（有默认值） |
|---|---|---|
| entity_table | 指标列表 | 排序（按首指标降序）、Top N（默认20） |
| period_comparison | 对比期时间、指标列表 | 实体层级（默认整体） |
| audience_distribution | 受众维度 | 指标（默认消耗） |
| time_trend | 指标 | 时间粒度（智能推断）、系列维度（默认整体） |
| summary | — （全有默认） | 指标集（默认核心指标集：消耗/曝光/点击/CTR） |

公共必填（所有形态都需要）：
- **广告主**（缺了澄清）
- **时间范围**（缺了澄清）

### 5.3 衍生指标计算

部分指标不是 ES 中直接存储的，需要从基础指标推导：

| 衍生指标 | 公式 | 依赖的基础指标 | 计算位置 |
|---|---|---|---|
| CTR（点击率） | click / impression | click + impression | 分析执行器后处理阶段 |
| CVR（转化率） | conversion / click | conversion + click | 分析执行器后处理阶段 |
| ROI（投资回报率） | conversion_value / cost | conversion_value + cost | 分析执行器后处理阶段 |
| 环比变化率 | (本期 - 对比期) / 对比期 | 本期值 + 对比期值 | 周期对比形态的后处理 |

**计算规则**：
- 分母为 0 时，结果记为 `null`，前端显示 "-"
- 百分比类指标统一保留 2 位小数
- 衍生指标出现在用户请求中时，分析规划器自动把依赖的基础指标加入查询计划

### 5.4 质量校验规则

| 校验项 | 适用形态 | 默认阈值 | 不达标动作 |
|---|---|---|---|
| max_series_count | time_trend（多系列） | 20 | HITL：提示用户缩小范围 |
| max_rows | entity_table | 100 | trim_top：截取 Top N（按首指标降序）+ 提示 |
| max_categories | audience_distribution | 8 | trim_others：截取 Top N-1，其余合并为"其他" |
| min_data_points | time_trend | 2 | 降级为单值显示 |
| all_zero | 所有 | — | warn：提示"无数据" |
| empty_result | 所有 | — | warn：提示查询条件 |

**动作类型说明**：
- `hitl`：中断，返回澄清提示，等用户确认后再执行
- `trim_top`：截取前 N 条，丢弃后面的，加警告
- `trim_others`：保留前 N-1 条，其余合并为"其他"类别
- `warn`：不中断，在结果中加警告提示
- `fail`：返回失败，引导用户调整查询

---

## 六、CoT 推理流程

### 6.1 Prompt 结构

```
【System Prompt】
- 角色定义：广告数据分析规划师
- 任务：根据用户问题，按步骤推理出筛选计划和分析计划
- 输出格式：先推理过程（文字），再结构化 JSON
- 可用工具：场景库说明、筛选模型说明、指标映射、维度映射

【Few-Shot 示例】
- 8 个精简示例（见下一节）
- 每个示例：用户问题 + 推理摘要 + FilterPlan + AnalysisPlan

【User Prompt】
- 用户问题
- 已有上下文（广告主、时间范围等）
- 可用广告主列表
- 今天日期
```

### 6.2 推理步骤（CoT 链条）

LLM 按以下顺序逐步推理（输出到 reasoning 字段）：

```
Step 1: 问题理解
  - 用一句话概括用户想做什么
  - 识别关键词

Step 2: 筛选识别
  - 有没有筛选？是哪种类型？（where / having / 跨层级 / 混合）
  - 筛选条件有哪些？（逐一列出）
  - 目标实体层级是什么？
  - 筛选需要几步？每步做什么？

Step 3: 分析识别
  - 这是什么分析形态？（5种里面选）
  - 图表类型是什么？
  - 需要哪些指标？
  - 时间粒度 / 受众维度 / 对比期？

Step 4: 信息完整性检查
  - 哪些信息齐了？哪些缺了？
  - 缺的是必填还是可选？
  - 必填缺失 → 列出需要澄清的问题（一次一个）

Step 5: 质量校验规划
  - 这种分析需要哪些质量校验？
  - 阈值设多少？
  - 不达标怎么办？

Step 6: 生成结构化计划
  - 输出 FilterPlan JSON
  - 输出 AnalysisPlan JSON
```

---

## 七、Few-Shot 示例库

> 每个示例均为测试用例，已通过端到端验证。
> 格式：用户问题 → 推理摘要 → 结构化计划（精简版）

---

### 示例 1：单指标时间趋势（无筛选）

**用户问题**：广告主6最近7天的消耗趋势

**推理摘要**：
- 筛选：无（广告主6，目标层级为整体汇总）
- 分析：时间趋势，折线图，单系列（整体），指标消耗，按天粒度
- 质量：数据点 ≥ 2

```json
{
  "filter_plan": {
    "filter_type": "none",
    "target_level": "advertiser",
    "steps": []
  },
  "analysis_plan": {
    "analysis_type": "time_trend",
    "chart_type": "line",
    "metrics": ["cost"],
    "time_range": {"start_date": "2026-08-01", "end_date": "2026-08-07"},
    "time_granularity": "day",
    "group_by": null,
    "quality_checks": [
      {"check_type": "min_data_points", "threshold": 2, "action": "warn"}
    ]
  }
}
```

---

### 示例 2：实体指标表 + Where 筛选

**用户问题**：广告主6下，创建时间在2026年之后的广告计划，4月份的消耗和点击

**推理摘要**：
- 筛选：where 型，campaign 层级，条件 create_time >= 2026-01-01
- 分析：实体指标表，柱状图 + 表格，指标消耗和点击
- 质量：行数 ≤ 100

```json
{
  "filter_plan": {
    "filter_type": "where",
    "target_level": "campaign",
    "steps": [
      {
        "step_id": "step_1",
        "step_type": "where_filter",
        "level": "campaign",
        "index": "campaign",
        "conditions": [
          {"field": "advertiser_id", "operator": "=", "value": 6},
          {"field": "create_time", "operator": ">=", "value": "2026-01-01"}
        ],
        "output_field": "campaign_id"
      }
    ]
  },
  "analysis_plan": {
    "analysis_type": "entity_table",
    "chart_type": "bar",
    "metrics": ["cost", "click"],
    "time_range": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
    "group_by": "campaign_id",
    "quality_checks": [
      {"check_type": "max_rows", "threshold": 100, "action": "trim"}
    ]
  }
}
```

---

### 示例 3：实体指标表 + Having 筛选

**用户问题**：广告主6 4月份消耗大于10的广告计划有哪些？

**推理摘要**：
- 筛选：having 型，campaign 层级，消耗 > 10
- 分析：实体指标表，柱状图 + 表格，指标消耗
- 质量：行数 ≤ 100

```json
{
  "filter_plan": {
    "filter_type": "having",
    "target_level": "campaign",
    "steps": [
      {
        "step_id": "step_1",
        "step_type": "having_filter",
        "level": "campaign",
        "index": "ad_stat_data",
        "conditions": [
          {"field": "data_value", "operator": ">", "value": 10,
           "metric": "cost"}
        ],
        "output_field": "campaign_id"
      }
    ]
  },
  "analysis_plan": {
    "analysis_type": "entity_table",
    "chart_type": "bar",
    "metrics": ["cost"],
    "time_range": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
    "group_by": "campaign_id",
    "quality_checks": [
      {"check_type": "max_rows", "threshold": 100, "action": "trim"}
    ]
  }
}
```

---

### 示例 4：带 Having 的多实体趋势图 ⭐

**用户问题**：id为6的广告主下4月份消耗>10的广告计划的4月份的消耗的趋势图

**推理摘要**：
- 筛选：having 型，campaign 层级，消耗 > 10
- 分析：时间趋势，多系列折线图，指标消耗，按天，系列=campaign
- 质量：系列数 ≤ 20（超了 HITL）

```json
{
  "filter_plan": {
    "filter_type": "having",
    "target_level": "campaign",
    "steps": [
      {
        "step_id": "step_1",
        "step_type": "having_filter",
        "level": "campaign",
        "index": "ad_stat_data",
        "conditions": [
          {"field": "data_value", "operator": ">", "value": 10, "metric": "cost"}
        ],
        "output_field": "campaign_id"
      }
    ]
  },
  "analysis_plan": {
    "analysis_type": "time_trend",
    "chart_type": "line",
    "metrics": ["cost"],
    "time_range": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
    "time_granularity": "day",
    "group_by": "campaign_id",
    "quality_checks": [
      {"check_type": "max_series_count", "threshold": 20, "action": "hitl"},
      {"check_type": "min_data_points", "threshold": 2, "action": "warn"}
    ]
  }
}
```

---

### 示例 5：跨层级筛选（自下而上）+ 实体表

**用户问题**：广告主6下，创意名包含"618"的广告计划，4月份的消耗

**推理摘要**：
- 筛选：跨层级（自下而上），条件在 creative 层级，目标层级 campaign
- 路径：creative 表 name 模糊匹配 → 聚合去重 campaign_id
- 分析：实体指标表，柱状图 + 表格，指标消耗

```json
{
  "filter_plan": {
    "filter_type": "cross_level",
    "target_level": "campaign",
    "steps": [
      {
        "step_id": "step_1",
        "step_type": "cross_level_up",
        "level": "creative",
        "index": "creative",
        "conditions": [
          {"field": "advertiser_id", "operator": "=", "value": 6},
          {"field": "creative_name", "operator": "contains", "value": "618"}
        ],
        "output_field": "campaign_id"
      }
    ]
  },
  "analysis_plan": {
    "analysis_type": "entity_table",
    "chart_type": "bar",
    "metrics": ["cost"],
    "time_range": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
    "group_by": "campaign_id",
    "quality_checks": [
      {"check_type": "max_rows", "threshold": 100, "action": "trim"}
    ]
  }
}
```

---

### 示例 6：周期对比（整体汇总）

**用户问题**：广告主6 4月的消耗和3月比怎么样？

**推理摘要**：
- 筛选：无（整体汇总）
- 分析：周期对比，双柱状图，指标消耗，本期4月 vs 对比期3月
- 质量：两期都不能全为0

```json
{
  "filter_plan": {
    "filter_type": "none",
    "target_level": "advertiser",
    "steps": []
  },
  "analysis_plan": {
    "analysis_type": "period_comparison",
    "chart_type": "bar",
    "metrics": ["cost"],
    "time_range": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
    "compare_time_range": {"start_date": "2026-03-01", "end_date": "2026-03-31"},
    "quality_checks": [
      {"check_type": "all_zero", "threshold": 0, "action": "warn"}
    ]
  }
}
```

---

### 示例 7：受众分布

**用户问题**：广告主6 4月份的消耗按性别分布

**推理摘要**：
- 筛选：无（全量）
- 分析：受众分布，饼图/环形图，指标消耗，受众维度=性别
- 质量：分类数 ≤ 8（超了合并"其他"）

```json
{
  "filter_plan": {
    "filter_type": "none",
    "target_level": "advertiser",
    "steps": []
  },
  "analysis_plan": {
    "analysis_type": "audience_distribution",
    "chart_type": "pie",
    "metrics": ["cost"],
    "time_range": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
    "audience_dimension": "gender",
    "quality_checks": [
      {"check_type": "max_categories", "threshold": 8, "action": "trim"}
    ]
  }
}
```

---

### 示例 8：单值汇总（核心指标）

**用户问题**：广告主6 4月份的核心数据

**推理摘要**：
- 筛选：无（整体汇总）
- 分析：单值汇总，KPI卡片，使用默认核心指标集
- 质量：全为0则提示无数据

```json
{
  "filter_plan": {
    "filter_type": "none",
    "target_level": "advertiser",
    "steps": []
  },
  "analysis_plan": {
    "analysis_type": "summary",
    "chart_type": "kpi_card",
    "metrics": ["cost", "impression", "click", "ctr"],
    "time_range": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
    "quality_checks": [
      {"check_type": "all_zero", "threshold": 0, "action": "warn"}
    ]
  }
}
```

### 7.9 向量检索方案

**不使用硬编码在 prompt 中的方式**，改为从向量库动态检索 few-shot 示例，复用现有 RAG 基础设施（PostgreSQL + pgvector）。

**存储方式**：
- 表结构复用 RAG 系统，`doc_type = 'cot_example'`
- 每个示例独立存储：问题嵌入向量 + 示例完整内容（推理 + JSON 计划）
- 示例源文件：YAML 格式，版本管理，通过同步脚本批量写入向量库

**检索流程**：
```
用户问题 → 向量检索 Top 5-6 → 规则重排 → Top 3 正面 + Top 1-2 负面 → 注入 prompt
```

**重排规则**：
- 优先同分析类型（time_trend → time_trend）
- 优先同筛选复杂度（having → having）
- 优先跨层级示例（如果查询涉及跨层级）
- 负面示例独立取 1-2 个

**初始示例规模**：
- 正面示例：~10 个（覆盖 6 种筛选 × 5 种分析的核心组合）
- 负面示例：3 个（where/having 混淆、跨层级方向错误、趋势图直接筛选错误）

**失败闭环**：
```
线上失败案例 → 日志采集 → 失败案例池 → 人工审核 → 转化为负面/正面示例 → 同步向量库 → 回归验证
```

**示例格式**：
- **Prompt 中呈现**：用户问题 + 中文推理过程（6-7 步）+ 精简 JSON 计划
- **负面示例额外标注**：错误点说明 + 正确做法提示

---

## 八、错误处理与降级策略

### 8.1 重试策略

**全局规则：所有 LLM 调用最多 1 次重试（共 2 次尝试）。**

- LLM 推理本身耗时较长（~10-15s），过多重试严重影响用户体验
- 失败原因通常是 prompt 问题或模型输出格式问题，重试未必能解决
- 超过重试次数 → 进入全局兜底流程

### 8.2 空结果自查

在执行分析查询前，先做一轮空结果自查，提前发现问题，避免用户看到"数据为 0"的假阴性结果。

**两组并行检查**：

1. **静态校验组**（纯规则，毫秒级）：
   - 时间范围是否合法（start ≤ end）
   - 指标与维度是否兼容
   - 实体 ID 列表是否为空

2. **ES 轻量查询组**（轻量 count/sum 查询，< 500ms）：
   - 在筛选条件下，数据总条数是否为 0
   - 核心指标（消耗/曝光）总和是否为 0

两组并行执行，任一检查命中空结果 → 直接返回空结果友好提示，不执行完整分析查询。

### 8.3 全局兜底

当 analysis_node 内部任何环节失败且重试无效时，**不自动降级分析形态**（用户要的是趋势图，就不该给他们表格），而是返回结构化的错误报告：

```python
{
    "report_type": "error",
    "error_type": "query_failed",           # query_failed / intent_unclear / data_empty / system_error
    "message": "未能生成有效的分析结果",       # 人类可读的友好错误信息
    "reason": "筛选条件过严，未找到符合条件的广告计划",  # 具体原因
    "suggestions": [                        # 3 条行动建议
        "尝试放宽筛选条件（如降低消耗阈值）",
        "检查时间范围是否正确",
        "查看该广告主下所有广告计划的消耗情况"
    ],
    "recommended_queries": [                # 2-3 条推荐查询
        "广告主6下所有广告计划的消耗排行",
        "广告主6最近7天的消耗趋势"
    ]
}
```

- HTTP 状态码：**200**（业务层错误，非系统错误）
- CoT 推理失败 → 静默降级为基于规则的模板匹配（用户无感知），只有当规则匹配也失败时才走错误报告

---

## 九、性能优化与 SSE 进度推送

### 9.1 P0 模板快速通道（延期）

**概念**：对于高频简单查询（如"广告主X最近7天消耗趋势"），用关键词规则直接匹配模板，跳过 CoT 推理，将延迟从 ~15s 降至 ~1-2s。

**当前决策**：**MVP 阶段不做**。先把完整 CoT 流程跑通，上线后根据实际查询分布数据再决定是否实现。

### 9.2 SSE 进度推送

采用 **SSE（Server-Sent Events）** 推送分析过程中的步骤进度，让用户在等待 ~15s 的过程中有明确的进度感知。

**方案**：步骤级事件（Plan A），不流式传输 LLM 推理过程。

**事件类型**：

| 事件 | 说明 | payload |
|---|---|---|
| `step_start` | 某步骤开始执行 | `{step: "intent_analyze", label: "理解查询意图"}` |
| `step_end` | 某步骤执行完成 | `{step: "cot_planner", label: "生成分析计划", status: "success"}` |
| `final_result` | 最终结果（报告或错误） | 完整的 final_report 对象 |

**步骤枚举**：`intent_analyze` → `cot_planner` → `filter_execute` → `analysis_execute` → `quality_check` → `report_format`

**连接管理**：
- 前端使用 EventSource API 建立连接
- 连接携带 `session_id` 和 `request_id`
- 收到 `final_result` 后前端自动关闭连接
- 断线重连：3s 内自动重连，携带上次收到的事件 ID

---

## 十、执行引擎设计

### 10.1 筛选计划执行器

**职责**：按 FilterPlan 逐步执行，输出目标实体 ID 列表

**每步执行流程**：
```
FilterStep → 生成 DSL → 安全校验 → ES 执行 → 结果提取 → 提取目标ID列表
                     ↑ 失败 ↓        ↑ 异常 ↓
                   重试（最多1次）
```

**多步数据流转**：
- 上一步输出的 ID 列表 → 作为下一步的 `terms` 过滤条件
- 每步的 output_field 决定提取哪个字段作为下一步输入

### 10.2 跨层级筛选执行细节

跨层级筛选（上钻/下钻）是筛选阶段的核心难点之一。以下为已确认的实现方案：

**查询方式：terms + ID 列表（非 terms lookup）**

- 使用普通的 `terms` 查询，传入实体 ID 列表
- **不使用 ES terms lookup**（跨索引查询）：数据量不大，terms 查询足够；terms lookup 需要维护父子索引关系，增加复杂度

**去重策略**：
- 当从低层实体 ID 向上汇总到高层（如 creative → campaign），必须去重
- ES terms aggregation 天然去重，但代码层仍需显式 `list(set(ids))` 做双重保险
- 从高层向下钻取（campaign → creative）不需要去重

**ID 数量软上限：500**
- 超过 500 个 ID 时，取 Top 500（按消耗排序），并在报告中提示"结果已截断"
- 避免 terms 查询过长导致 ES 性能问题

**执行示例（campaign → creative 下钻）**：
```
Step 1 (having at campaign level): 筛选消耗>10的campaign → [campaign_id_1, campaign_id_2, ...]
Step 2 (cross_level_down): 以 campaign_id 列表为条件，查 creative 层级 → [creative_id_1, creative_id_2, ...]
```

### 10.3 派生指标筛选实现

筛选阶段支持基于派生指标（CTR / CVR / CPC / CPM / ROI）的 having 条件，通过 Elasticsearch 的 `bucket_script` + `bucket_selector` pipeline aggregation 实现。

**实现原理**：
1. 先用 `filter` + `sum` 聚合计算派生指标依赖的基础指标（如 CTR 需要 clicks 和 impressions）
2. 用 `bucket_script` 管道聚合计算派生指标值
3. 用 `bucket_selector` 管道聚合按阈值筛选 bucket

**DSL 结构示例（CTR > 5% 的广告计划）**：
```python
{
    "size": 0,
    "query": { "bool": { "filter": [...] } },
    "aggs": {
        "by_campaign": {
            "terms": { "field": "campaign_id", "size": 1000 },
            "aggs": {
                "sum_clicks": {
                    "filter": { "term": { "data_type": 2 } },
                    "aggs": { "value": { "sum": { "field": "data_value" } } }
                },
                "sum_impressions": {
                    "filter": { "term": { "data_type": 1 } },
                    "aggs": { "value": { "sum": { "field": "data_value" } } }
                },
                "ctr": {
                    "bucket_script": {
                        "buckets_path": {
                            "clicks": "sum_clicks>value",
                            "impressions": "sum_impressions>value"
                        },
                        "script": { "source": "params.clicks / params.impressions", "lang": "painless" }
                    }
                },
                "having_filter": {
                    "bucket_selector": {
                        "buckets_path": { "value": "ctr" },
                        "script": { "source": "params.value > 0.05", "lang": "painless" }
                    }
                }
            }
        }
    }
}
```

**关键约定**：
- 百分比指标存储为小数（CTR 0.05 = 5%），乘以 100 的格式化仅在展示层
- 公式以 painless script 字符串形式存储（而非 Python lambda），确保可序列化
- 所有派生指标的定义集中在 `DERIVED_METRICS` 字典中，包含 formula、depends_on、unit

### 10.4 分析计划执行器

**职责**：按 AnalysisPlan 执行查询，生成图表数据

**流程**：
```
AnalysisPlan → 生成查询DSL → ES 执行 → 组装图表数据 → 质量校验
                                                     │
                                          ┌──────────┴──────────┐
                                          ▼                     ▼
                                      达标                 不达标
                                       │                  调整重试（最多1轮）
                                       │                        │
                                       ▼                        ▼
                                输出 chart_config          仍不达标 → HITL
```

### 10.5 图表数据输出格式

统一输出格式，前端 ChartRenderer 直接消费：

```python
{
    "chart_config": {
        "type": "line",                     # line / bar / pie / kpi_card
        "title": "消耗趋势",
        "x_axis": {"field": "date", "label": "日期"},
        "y_axis": {"field": "cost", "label": "消耗"},
        "series_field": "campaign_name",     # 多系列时的系列字段
        "series": [                          # 系列配置（颜色、名称等）
            {"name": "计划A", "color": "#3b82f6"},
            {"name": "计划B", "color": "#10b981"}
        ]
    },
    "data": [                                # 图表数据
        {"date": "2026-04-01", "计划A": 100, "计划B": 80},
        {"date": "2026-04-02", "计划A": 120, "计划B": 90}
    ],
    "data_table": {                          # 配套数据表
        "columns": ["日期", "计划名称", "消耗"],
        "rows": [...]
    }
}
```

---

## 十一、HITL 澄清机制

### 11.1 设计原则

澄清判断**分两个阶段独立进行**——先判断筛选阶段缺什么，再判断分析阶段缺什么。
每个阶段有自己的必填信息清单和澄清逻辑。一次只澄清一个问题。

```
用户问题
  │
  ▼
阶段A：筛选识别
  │
  ├─ 公共必填检查（广告主 / 时间范围）
  │    └─ 缺 → 澄清，终止后续推理
  │
  ├─ 筛选类型判断
  │
  └─ 筛选必填信息检查
       ├─ 缺目标层级 → 澄清
       ├─ 缺筛选条件 → 澄清
       ├─ 缺阈值（如"消耗高"没说多少算高）→ 澄清
       └─ 全齐 → 进入阶段B
  │
  ▼
阶段B：分析识别
  │
  ├─ 分析形态判断
  │
  └─ 分析必填信息检查
       ├─ 缺指标 → 澄清
       ├─ 缺对比期（周期对比形态）→ 澄清
       ├─ 缺受众维度（受众分布形态）→ 澄清
       └─ 全齐 → 生成完整计划
```

### 11.2 阶段 A：筛选阶段的澄清判断

#### 11.2.1 公共必填（所有筛选类型都需要）

| 字段 | 缺失时澄清 | 选项 |
|---|---|---|
| 广告主 | "请问你想查看哪个广告主的数据？" | 推荐广告主列表 |
| 时间范围 | "请问你想查看哪段时间的数据？" | 今天/昨天/近7天/近30天/本月/上月/自定义 |

> 公共必填优先检查——广告主和时间都没确定的话，不往下判断筛选和分析。

#### 11.2.2 各筛选类型的必填信息 & 澄清

| 筛选类型 | 必填信息 | 缺了怎么澄清 |
|---|---|---|
| **none（全量）** | 目标实体层级 | "你想查看哪个层级的数据？" 选项：广告计划/广告组/创意/整体汇总 |
| **where 型** | 目标层级 + 过滤条件（字段+操作符+值） | 缺层级：同上；缺条件值："你说的 XX 具体是指什么？" |
| **having 型** | 目标层级 + 指标条件（指标+操作符+阈值） | 缺层级：同上；缺指标："你说的'表现好'是指哪个指标？" 选项：消耗/点击/曝光/CTR；缺阈值："你说的 XX 高具体指多少以上？" |
| **跨层级** | 条件所在层级 + 条件内容 + 目标层级 | 缺目标层级："你想看哪个层级的实体？"；缺条件："筛选条件是什么？" |

**判断顺序**：先判断筛选类型 → 再按该类型的必填清单逐一检查 → 第一个缺的就澄清，不往下检查。

#### 11.2.3 筛选阶段的澄清示例

**场景：用户说"表现好的计划有哪些"**
1. 筛选类型判断：having 型（"表现好"= 指标好）
2. 目标层级：campaign ✅（"计划"说了）
3. 指标：未明确 ❌ → 澄清："你说的'表现好'是指哪个指标好？比如消耗高、点击多、CTR高"
4. （用户回复"消耗"后）阈值：未明确 ❌ → 澄清："消耗达到多少算高？比如 100元以上"

### 11.3 阶段 B：分析阶段的澄清判断

筛选阶段的信息齐全后，再进入分析阶段的判断。

#### 11.3.1 各分析形态的必填信息 & 澄清

| 分析形态 | 必填信息（筛选已齐，不用再问） | 还需要的信息 | 缺了怎么澄清 |
|---|---|---|---|
| **entity_table** | 实体列表 + 时间范围 + 层级 | 指标列表（至少1个） | "你想查看哪些指标？" 选项：消耗/点击/曝光/CTR/CVR/转化数 |
| **period_comparison** | 实体列表 + 本期时间 + 层级 | 对比期时间 + 指标列表 | 缺对比期："你想和哪个时间段对比？" 选项：上月/上周/去年同期/自定义；缺指标：同上 |
| **audience_distribution** | 实体列表 + 时间范围 | 受众维度 + 指标（默认消耗） | 缺受众维度："你想看哪个维度的受众分布？" 选项：性别/年龄/地域/设备/兴趣；缺指标→用默认消耗，不澄清 |
| **time_trend** | 实体列表 + 时间范围 | 指标 | "你想看哪个指标的趋势？" 选项：消耗/点击/曝光/CTR |
| **summary** | 实体列表 + 时间范围 | 指标列表（有默认核心指标集） | 一般不澄清，用默认 [消耗, 曝光, 点击, CTR] |

**时间粒度（趋势图）**：有默认值，不澄清。智能推断：时间范围 ≤ 7天→按天，≤ 3个月→按周，>3个月→按月。

#### 11.3.2 分析形态的默认推断

如果用户问题里没有明确说哪种分析形态，按以下优先级推断：
1. 有"趋势"/"走势"/"变化" → time_trend
2. 有"对比"/"比"/"环比"/"同比" → period_comparison
3. 有"分布"/"占比"/"占了多少" → audience_distribution
4. 有"哪些"/"列表"/"排名"/"Top" → entity_table
5. 有"多少"/"是多少"/"总" → summary
6. 有多个指标且按实体分组 → entity_table（默认）

推断不出来（置信度低）时，澄清问用户："你想看什么样的分析？趋势/对比/排名/分布？"

### 11.4 执行后 HITL（质量校验触发）

查询执行完后，质量校验不达标也会触发 HITL。这是第三类澄清。

| 触发条件 | 澄清话术 | 用户可选操作 |
|---|---|---|
| 多系列趋势图 > 20 条线 | "查询到 {N} 个广告计划的趋势数据，超过 20 条线不易阅读。建议增加筛选条件缩小范围，比如：<br>• 提高消耗阈值<br>• 只看 Top 20<br>• 按广告组层级查看" | 提供快捷选项："看Top 20"/"提高阈值到 XX"/"换广告组层级"/"自定义条件" |
| 实体列表 > 100 条 | "查询到 {N} 条数据，默认展示 Top 100。需要看更多可以翻页，或增加筛选条件。" | 不强制 HITL，warn 即可 |
| 空结果 | "未查询到满足条件的数据。可能的原因：... 建议调整筛选条件后重试。" | 不强制 HITL，warn 即可 |

### 11.6 去重机制：避免重复询问同一字段

#### 11.6.1 问题

筛选阶段和分析阶段虽然分开推理，但有些字段是两个阶段都可能需要的（比如时间范围、指标、广告主）。如果不做去重，用户可能会被问两遍同样的问题。

**典型例子**：
- 用户问"消耗>10的趋势"
- 筛选阶段（having）需要时间范围 → 问了用户
- 分析阶段（趋势图）也需要时间范围 → 又问一遍

#### 11.6.2 解决机制

**字段共享池（Field Context Pool）**：

CoT 推理过程中，所有已确认的字段都存入一个共享字段池。两个阶段的推理都从这个池中读取已确认的字段，只池子里没有的才需要澄清。

```
字段共享池（Field Context Pool）
  ├─ advertiser_ids        ← 公共字段，两阶段共享
  ├─ time_range            ← 公共字段，两阶段共享
  ├─ target_level          ← 筛选阶段确定，分析阶段继承
  ├─ metrics               ← 可能先在筛选阶段确定（having指标），分析阶段继承
  ├─ audience_dimension    ← 可能在筛选阶段确定（受众切片），分析阶段继承
  └─ ...
```

#### 11.6.3 字段继承规则

| 字段 | 筛选阶段 | 分析阶段 | 继承规则 |
|---|---|---|---|
| advertiser_ids | ✅ 需要 | ✅ 需要 | 筛选阶段先确认，分析阶段直接用 |
| time_range | ✅ 需要 | ✅ 需要 | 筛选阶段先确认，分析阶段直接用 |
| target_level | ✅ 需要 | ✅ 可选 | 筛选阶段确认，分析阶段默认用相同层级 |
| metrics | having型需要 | ✅ 需要 | 筛选阶段有就继承，没有分析阶段再问 |
| audience_dimension | 受众切片having需要 | 受众分布需要 | 哪边先确定都可以，另一边直接用 |
| compare_time_range | ❌ 不需要 | 周期对比需要 | 分析阶段独有 |

#### 11.6.4 冲突处理

极少数情况下，两个阶段对同一字段的理解可能不一致（比如筛选阶段的指标是 cost，分析阶段用户又说了 click）。处理规则：

- **以用户最后一次明确说的为准**
- 如果用户只说了一次，两个阶段共享同一个值
- 如果用户在澄清中明确修改了，更新字段池，重新走推理

#### 11.6.5 实现方式

在 AnalysisPlanner 的推理流程中：
1. 第一步先从用户问题 + 上下文 + 历史澄清中提取所有已知字段，填入字段池
2. 筛选阶段推理时，先看字段池里有什么，缺什么补什么
3. 分析阶段推理时，同样先看字段池，缺什么补什么
4. 每次澄清只问字段池中没有的字段

由于 LLM 是一次 CoT 推理完成两个阶段的，字段去重本质上是 prompt 设计问题——在推理指引中明确要求：
> "先汇总所有已确认的字段，再检查缺失项。已经确认的字段不要再次询问用户。"

```
用户澄清回复
  │
  ▼
追加到用户问题末尾（带语义前缀，帮助LLM理解）
  │
  ▼
重新进入 analysis_planner
  │
  ▼
重新走完整 CoT 推理
  - 已确认的信息会被正确提取
  - 继续检查下一个缺失项
```

#### 语义前缀映射

沿用现有设计，补充筛选阶段相关前缀：

| 澄清类型 | 语义前缀 | 示例 |
|---|---|---|
| 缺失广告主 | "广告主：{反馈}" | "广告主：6" |
| 缺失时间范围 | "时间范围：{反馈}" | "时间范围：4月份" |
| 缺失目标层级 | "实体层级：{反馈}" | "实体层级：广告计划" |
| 缺失 having 指标 | "筛选指标：{反馈}" | "筛选指标：消耗" |
| 缺失 having 阈值 | "筛选阈值：{反馈}" | "筛选阈值：10以上" |
| 缺失对比期 | "对比时间：{反馈}" | "对比时间：上月" |
| 缺失受众维度 | "受众维度：{反馈}" | "受众维度：性别" |
| 缺失分析指标 | "分析指标：{反馈}" | "分析指标：消耗、点击" |

### 11.7 澄清回流方案

**两种 HITL 类型都触发完整 CoT 重跑**，而非仅重执行：

| HITL 类型 | 触发时机 | 回流方式 |
|---|---|---|
| **信息缺失型 HITL** | CoT 推理阶段发现字段不全 | 追加澄清回复到用户问题 → 重新走完整 CoT 推理 |
| **质量型 HITL** | 执行后质量校验不达标 | 用户确认调整方向 → 追加调整指令 → 重新走完整 CoT 推理 |

**设计决策**：
- 简化架构：统一走完整 CoT，不区分"重推理"和"重执行"两条路径
- 用户的澄清回复可能改变筛选和分析的多个维度，重跑 CoT 最安全
- 额外开销可接受（多 ~10s），换取正确性和一致性
- 旧的分析计划和结果在重跑后丢弃，不做局部 patch

---

## 十二、测试与 Mock 策略

### 12.1 四层测试架构

| 层级 | 测试内容 | 实现方式 | 环境依赖 |
|---|---|---|---|
| **L1: 单元测试** | DSL 模板结构正确性、工具函数、结果提取逻辑 | pytest + 结构断言 | 无 |
| **L2: Schema 验证** | 生成的 DSL 能通过 ES validate API | ES validate API（轻量，不查数据） | ES 连接（无数据要求） |
| **L3: Mock 集成测试** | 执行器 + 质量校验 + 报告格式化的端到端逻辑 | Mock ES 返回固定数据，断言输出结构和计算逻辑 | 无（全部 mock） |
| **L4: 冒烟测试** | 真实 ES + 真实 LLM 的完整链路验证 | 连测试 ES 集群 + 测试 LLM，断言结果非空且格式正确 | 测试 ES + 测试 LLM |

**DSL 安全校验器**（DslValidator）作为 L2 的补充，对所有 DSL（包括模板生成的）做安全检查：
- 禁止 `script_fields`、`script_score` 等任意脚本执行
- 限制 `size` 和 `terms` 数量
- 防止深度嵌套聚合导致栈溢出

### 12.2 Few-Shot 示例验证

每个 few-shot 示例对应一个测试用例，覆盖 L1-L3：

```
tests/nl_dsl/test_cot_examples/
  ├─ test_ex1_simple_trend.py
  ├─ test_ex2_entity_table_where.py
  ├─ test_ex3_entity_table_having.py
  ├─ test_ex4_multi_series_trend.py
  ├─ test_ex5_cross_level.py
  ├─ test_ex6_period_comparison.py
  ├─ test_ex7_audience_distribution.py
  └─ test_ex8_summary.py
```

每个测试断言：
1. CoT 生成的计划结构正确（schema 通过）
2. 筛选步骤数和类型正确
3. 分析类型和图表类型正确
4. 质量校验规则正确
5. （L3 mock）执行后数据结构和预期一致

### 12.3 Mock 策略

**ES Mock**：
- 方式：Mock Elasticsearch client 的 `search()` 方法
- 返回预定义的 ES 响应结构（模拟真实 ES 的 hits/aggregations 格式）
- 用于：执行器、质量校验器、报告格式化的集成测试

**LLM Mock**：
- 方式：Mock LLM 调用，返回预设的 CoT 推理 + JSON 计划
- 用于：CoT Planner 的集成测试、analysis_node 完整流程测试
- 不同测试用例返回不同的预设输出，覆盖各种筛选+分析组合

### 12.4 新增示例流程

1. 在 YAML 中添加示例（用户问题 + 中文推理 + 精简 JSON 计划）
2. 写对应测试用例
3. 跑 L1-L3 测试验证通过
4. 运行同步脚本写入向量库
5. 跑回归测试，确保不影响其他示例

---

## 十三、实施路径

### 13.1 阶段一：核心框架（优先）
1. 定义 FilterPlan / AnalysisPlan / QualityCheck 等 Pydantic 模型
2. 实现 AnalysisPlanner 类（CoT 推理 + 结构化输出）
3. 实现筛选计划执行器
4. 实现分析计划执行器
5. 实现质量校验引擎
6. 接入 LangGraph（替换现有 nl_dsl 节点）

### 13.2 阶段二：场景覆盖
1. 逐一实现 5 种分析形态的查询生成 + 图表数据组装
2. 逐一实现 4 种筛选类型
3. 8 个 few-shot 示例 + 测试
4. HITL 澄清机制对接

### 13.3 阶段三：质量与体验
1. 质量校验规则完善
2. 错误重试与降级策略
3. 前端多系列折线图渲染支持
4. 性能优化

---

## 十四、风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| CoT 推理耗时长 | 响应延迟增加 | 1. SSE 步骤级进度推送，提升感知速度；2. P0 模板快速通道（上线后根据数据决定是否做）；3. lite 模型做规划 |
| Few-shot 示例不准 | LLM 被误导 | 1. 向量检索 + 规则重排，动态选择最相关示例；2. 失败闭环：失败案例 → 人工审核 → 示例库更新；3. 负面示例纳入 prompt |
| 筛选+分析两步查询慢 | 多步查询延迟高 | 1. 简单 where 筛选合并到分析查询一步（后续优化）；2. 缓存实体ID列表（后续优化） |
| 前端图表类型不足 | 部分分析形态渲染不了 | 1. MVP 实现 4 种（多系列折线/饼图/KPI卡片/表格）；2. 其他降级为表格展示 |
| 跨层级筛选 ID 过多 | terms 查询过大 | 500 ID 软上限 + Top N 截断 + 报告提示 |
| 质量校验 HITL 打断流程 | 用户体验差 | 1. 合理阈值（趋势图 >20 条线才触发）；2. 提供快捷选项减少用户输入成本 |

---

## 十五、附录：指标 & 维度映射参考

### 15.1 核心指标集（默认）
- cost（消耗）
- impression（曝光）
- click（点击）
- ctr（点击率，衍生计算）

### 15.2 实体层级
- advertiser（广告主）
- campaign（广告计划）
- ad_group（广告组）
- creative（创意）

### 15.3 受众维度
- gender（性别）
- age（年龄）
- region（地域）
- device（设备）
- interest（兴趣标签）
