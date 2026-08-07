# 意图识别智能化 & 查询层升级 设计文档

> **版本**: v1.0
> **日期**: 2026-08-06
> **状态**: Draft
> **范围**: 报表分析链路（不涉及知识 RAG 链路）

## 一、背景与目标

### 1.1 问题

当前报表分析链路存在两个核心痛点：

1. **意图识别不够智能**：依赖硬编码的"能力注册表"，新增指标、维度、分析能力都需要改代码，AI 无法动态发现和使用系统能力。
2. **数据查询层不完善**：缺少 Schema 元数据索引、缺少 NL→DSL 自然语言查询能力、缺少查询失败后的自反思重试机制、缺少结构化安全校验。

### 1.2 目标

- **意图层**：从"枚举式校验"升级为"理解式收集 + 动态路由"，新增数据能力不用改意图层代码。
- **查询层**：引入 Schema RAG + NL→DSL + 自反思重试，支持复杂 ad-hoc 查询，提升查询成功率和准确率。
- **安全性**：NL→DSL 多层只读防护，确保不产生写入操作。
- **可观测性**：全链路日志对齐现有规范，便于排查问题。

### 1.3 非目标（本次不做）

- 语义层 / 指标平台（长期方向，预留扩展空间，本次不落地）
- 知识 RAG 链路改造
- MySQL 数据源支持（当前业务数据全在 ES）
- 前端图表库更换（保留现有图表库和交互形式）

---

## 二、整体架构

### 2.1 架构选型

**方案二：双轨查询架构**

- **结构化快车道**：保留现有 planner + executor 链路，常见查询快、稳、零安全风险。
- **NL→DSL 自由通道**：新增 Schema RAG + NL→DSL 生成 + 自反思执行，支持复杂灵活查询。
- **意图层路由**：report_intent 节点判断走哪条路径，结构化表达不了的走 NL→DSL。

### 2.2 架构图

```
┌──────────────────────────────────────────────────────────────┐
│                     LangGraph Flow                           │
│                                                              │
│  用户输入 → intent_classifier → report_intent → 路由判断      │
│                                         │                    │
│                             ┌───────────┴───────────┐        │
│                             ▼                       ▼        │
│                       结构化快车道              NL→DSL 通道    │
│                      （现有planner）        （新增模块）       │
│                             │                       │        │
│                             └───────────┬───────────┘        │
│                                         ▼                    │
│                                   结果统一格式化               │
│                                         │                    │
│                                         ▼                    │
│                                   reporter（输出呈现）        │
│                                         │                    │
│                                         ▼                    │
│                                        END                   │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 数据存储现状

| 数据类型 | 存储 | 索引/表 |
|---------|------|---------|
| 广告主元数据 | Elasticsearch | `advertiser` |
| 广告报表事实表 | Elasticsearch | `ad_stat_data`（长表模型，data_type 区分指标） |
| 受众维度数据 | Elasticsearch | `ad_stat_audience` |
| 广告单元元数据 | Elasticsearch | `adgroup` |
| RAG 知识库 | PostgreSQL + pgvector | `rag_documents` / `rag_chunks` |

**关键特点**：
- 所有业务数据在 Elasticsearch 中
- `ad_stat_data` 是长表：指标用 `data_type`（1=曝光,2=点击,3=消耗,4=转化,5=触达,6=频次）+ `data_value` 表示
- 层级 ID（advertiser_id / campaign_id / adgroup_id / creative_id）都在同一张表里

---

## 三、模块划分与职责

| 模块 | 新增/改造 | 核心职责 |
|------|----------|---------|
| **意图理解层（report_intent）** | 改造 | 分析类型识别 + 必填项提取 + 路径路由判断 |
| **Schema RAG** | 新增 | ES 索引/字段/指标/示例的元数据索引，支持语义检索 |
| **NL→DSL 生成器** | 新增 | 查询规划 + 逐步生成 ES DSL |
| **DSL 安全校验器** | 新增 | 只读校验、索引白名单、超时/行数限制 |
| **自反思执行器** | 新增 | 执行 → 结果检查 → 失败反思重试（最多 3 次） |
| **结果格式化器** | 新增 | ES 原始结果 → 统一格式 + 呈现类型判断 |
| **Reporter** | 改造 | 根据呈现类型生成不同格式的 final_report |
| **nl_dsl_node** | 新增 | LangGraph 节点，封装 NL→DSL 全流程 |
| **列表分页 API** | 新增 | 列表类查询的服务端翻页接口 |

---

## 四、意图理解层改造

### 4.1 职责变化

| 旧职责 | 新职责 | 变化 |
|--------|--------|------|
| 提取广告主/时间/指标/维度 | 提取广告主/时间/指标/维度 | 保留 |
| 校验系统能力（能力注册表） | 路由判断：走结构化 还是 NL→DSL | 去掉硬编码校验 |
| 检测澄清需求 | 检测澄清需求（必填项缺失） | 保留，简化触发条件 |
| 检测纯广告主查询 | 检测纯广告主查询 | 保留 |

### 4.2 必填项

三个必填项，缺一个澄清一个，一次只问一个问题：

| 必填项 | 缺失时的澄清方式 |
|--------|-----------------|
| 广告主（1个或多个，不允许全平台） | 推荐广告主列表（从 advertiser_service 取） |
| 时间范围 | 快捷选项：最近7天 / 最近30天 / 本月 / 上月 / 自定义 |
| 指标 | 常用指标选项（从 Schema RAG 取热门指标） |

可选项（缺了用默认值或 Schema 推断，不澄清）：
- 广告层级（默认广告主层级）
- 聚合维度（默认按天）
- 过滤条件（默认无）
- 排序 / TopN（默认按指标降序）
- 对比周期（默认不对比）

### 4.3 顶层分类器快筛规则补充

顶层分类器的规则快筛（`rule_fastpath`）新增广告主查询关键词匹配，确保纯广告主查询也能快速识别为 `report` 类别：

**广告主查询关键词**：
- 列表查询："广告主列表"、"有哪些广告主"、"所有广告主"、"全部广告主"
- ID/名称查询："广告主id"、"广告主名称"、"广告主名字"
- 组合模式："XX广告主" + "叫什么" / "ID是多少" / "名称"

命中任一 → 分类为 `report`，置信度 1.00，来源 `rule_fastpath`。

### 4.4 路径路由判断

三个必填项都齐了之后，按优先级判断：

1. **纯广告主查询** → 直接生成 final_report（已有短路逻辑）
2. **结构化可表达** → 走结构化快车道
   - 判断标准：单索引、标准指标、标准维度、简单过滤、无 having、无跨层级关联、无多步
3. **其他情况** → 走 NL→DSL 通道

**安全网**：结构化路径失败时 fallback 到 NL→DSL，路由判断错了也不会挂。

### 4.5 输出到 State 的字段

```python
{
    "report_intent_result": { ... },   # 保留旧格式（结构化路径用）
    "analysis_type": "trend",          # 分析类型：trend/comparison/ranking/list/qa/audience/detail
    "query_route": "structured",       # 路由结果：structured / nl_dsl
    "route_reason": "...",             # 路由判断依据（日志用）
    "user_input_original": "..."       # 原始用户问题（NL→DSL 要用）
}
```

### 4.6 上下文继承与 State 序列化

**上下文继承策略**：当用户追问或澄清后重新进入 report_intent 时，从上一轮的 `report_intent_result` 中继承部分字段：
- ✅ 继承：广告主（advertiser_ids）、时间范围（time_range）、广告层级（ad_level）
- ❌ 不继承：指标（metrics）、维度（group_by）、过滤条件（filters）—— 每轮重新提取

**State 序列化兼容**：
`report_intent_result` 通过 `model_dump()` 序列化为 dict 存入 LangGraph state。从 state 中恢复时，`time_range` 等嵌套对象会变成 plain dict 而非 Pydantic 对象。在上下文继承阶段需要做兼容转换：

```python
if isinstance(existing_time_range, dict):
    existing_time_range = ReportTimeRange(
        start_date=existing_time_range.get("start_date", ""),
        end_date=existing_time_range.get("end_date", ""),
        unit=existing_time_range.get("unit", "day"),
        is_lifetime=existing_time_range.get("is_lifetime", False),
    )
```

不兼容会导致 `time_range.start_date` 报 `'dict' object has no attribute 'start_date'` 错误。

### 4.7 日志

| 事件 | 级别 | 日志内容 |
|------|------|---------|
| 开始识别 | INFO | `开始报表意图识别: 用户输入='{truncate(input,100)}', 已有广告主={ids}` |
| 提取完成 | INFO | `报表意图提取完成: 广告主={ids}, 时间={range}, 指标={metrics}, 分析类型={type}` |
| 路由判断 | INFO | `报表意图路由判断: 路径={route}, 原因={reason}` |
| 触发澄清 | INFO | `报表意图触发澄清: 缺失字段={field}, 类型={clarify_type}` |
| 完成 | INFO | `报表意图识别完成: 路径={route}, 广告主={ids}, 时间={range}, 指标={metrics}` |

---

## 五、Schema RAG 设计

### 5.1 存储层级

三级元数据文档，向量化存储：

#### 第一级：索引（Index）级别
每个 ES 索引一篇文档：
- `index_name`：索引名
- `description`：索引用途、支持的分析类型
- `supported_analysis_types`：支持的分析类型列表
- `hierarchy_fields`：层级字段及上下关系
- `time_field`：时间字段名
- `metric_field` / `metric_type_field`：指标值字段 / 指标类型字段

#### 第二级：字段（Field）级别
重要字段单独成篇：
- `field_name`：字段名
- `index`：所属索引
- `field_type`：字段类型
- `description`：字段含义
- `enumeration`：枚举值映射（含 label + alias 同义词 + note 注意事项）

#### 第三级：查询示例（Query Pattern）级别
常见查询模式作为 few-shot 示例：
- `pattern_name`：模式名称
- `description`：适用场景
- `user_query_example`：示例用户问题
- `index`：涉及的索引
- `dsl_template`：对应的 ES DSL 模板

### 5.2 存储方式

复用现有 PostgreSQL + pgvector RAG 基础设施，通过 `doc_type = 'schema'` 区分，不与业务知识库混用。

### 5.3 检索方式

两轮检索：

1. **索引级检索**：用户问题 → 最相关的索引文档 → 确定查哪个（或哪几个）索引
2. **字段 + 示例检索**：用户问题 + 索引名 → 相关字段定义 + 查询示例 → 组装 prompt 上下文

### 5.4 更新方式

- **手动注册**：YAML 配置文件 + 同步脚本，生成 embedding 并存入 Schema RAG
- **自动扫描（后续优化）**：扫描 ES mapping 自动提取字段，人工补充描述和别名

---

## 六、NL→DSL 生成器 + 自反思执行器

### 6.1 整体流程

```
用户问题 + 约束信息 + Schema RAG 结果
  ↓
Step 1: 查询规划（多步规划，每步输入输出明确）
  ↓
Step 2: 逐步执行
  ┌─ 生成 DSL
  ├─ 安全校验 → 失败 → 反思重试
  ├─ 执行查询 → 失败 → 反思重试
  ├─ 结果检查 → 异常 → 反思重试
  └─ 保存结果，进入下一步
  ↓
Step 3: 结果汇总 + 格式化
  ↓
统一格式输出
```

### 6.2 查询规划器

**输入**：用户问题 + 提取的结构化信息 + Schema RAG 检索结果

**输出**：结构化查询计划
```json
{
  "steps": [
    {
      "step_id": "step_1",
      "description": "找出4月消耗>10的ad_group列表",
      "index": "ad_stat_data",
      "output_fields": ["adgroup_id"],
      "purpose": "筛选符合条件的ad_group_id"
    }
  ],
  "final_output": "step_1.output"
}
```

**最大步数**：5 步

### 6.3 DSL 生成器

每个步骤独立生成 ES DSL。Prompt 包含：
1. 本步骤目标描述
2. 输入参数（初始参数 或 上一步结果）
3. 相关 Schema 信息（索引、字段、枚举值）
4. 相关查询示例（few-shot）
5. 安全约束（只读、白名单、行数限制等）
6. 重试时附加上次失败信息 + 反思结论

### 6.4 自反思重试机制

- **最多 3 次尝试**（首次 + 2 次重试）
- 每次失败触发反思：把失败信息返回给 LLM，分析原因并修改
- 反思内容计入日志

#### 失败类型与处理

| 失败类型 | 触发条件 | 处理方式 |
|---------|---------|---------|
| 校验失败 | DSL 命中安全规则 | 告诉 LLM 哪条规则不通过，修改后重试 |
| 执行失败 | ES 返回错误 | 把 ES 错误信息给 LLM，修改后重试 |
| 空结果 | 返回 0 条数据 | 自查一轮（过滤条件/字段名/索引/编码），有问题则修正重试；没问题则停止重试，返回空结果提示 |
| 结果异常 | 数据量过大 / 数值异常 / 信息不全 | 让 LLM 检查并修正后重试 |

#### 空结果特殊处理

- 第 1 次空结果：自查修正，有明显问题则重试（算 1 次重试）
- 第 2 次还是空 / 自查没问题：不强行重试，返回"未查询到满足条件的数据"+ 当前查询条件 + 调整建议

#### 最终失败

3 次尝试均失败后，生成失败引导报告：
- 查询失败提示
- 可能的原因（根据最后一次失败类型推断）
- 建议重新组织语言的方向
- 附可用指标 / 维度列表（从 Schema RAG 取）

#### 计划执行容错

**final_output 不匹配容错**：
- 若 `plan.final_output`（如 `step_2.output`）匹配不到任何步骤 ID，降级使用最后一步的结果
- 记录 WARN 日志，不视为失败

**空结果降级返回**：
- 空结果（0 条命中且聚合为空）经过 2 次尝试后，返回空结果而非失败
- metadata 中标记 `is_empty_result: true` 和 `empty_reason`
- 下游可据此展示"未查询到数据"的友好提示

**size 截断执行时保护**：
- 执行前检查 DSL 的 size 参数，超过 max_size（1000）自动截断
- 在校验层之外再加一道执行层保护，防止校验遗漏

### 6.5 日志

| 环节 | 级别 | 日志内容 |
|------|------|---------|
| 规划开始 | INFO | `NL→DSL查询规划开始: 用户问题='{truncate(input,100)}', 候选索引={indices}` |
| 规划完成 | INFO | `NL→DSL查询规划完成: 步骤数={n}, 步骤=[{desc1}, {desc2}]` |
| DSL 生成 | INFO | `NL→DSL生成(步骤{id}): 索引={index}, DSL={truncate(dsl,500)}` |
| 安全校验通过 | INFO | `NL→DSL安全校验通过(步骤{id})` |
| 安全校验失败 | INFO | `NL→DSL安全校验失败(步骤{id}): 原因={reason}` |
| 执行成功 | INFO | `NL→DSL执行成功(步骤{id}): 结果行数={n}, 耗时={ms}ms` |
| 执行失败 | ERROR | `NL→DSL执行失败(步骤{id}): 错误={truncate(error,200)}` |
| 重试 | INFO | `NL→DSL第{n}次重试(步骤{id}): 失败类型={type}, 反思={truncate(reflection,200)}` |
| 结果检查 | INFO | `NL→DSL结果检查(步骤{id}): 空结果={bool}, 异常={reason}` |
| 最终失败 | ERROR | `NL→DSL最终失败(步骤{id}): 重试{n}次, 最终错误={error}` |
| 全部完成 | INFO | `NL→DSL查询完成: 总步骤={n}, 总耗时={ms}ms, 最终行数={rows}` |

长文本用 `truncate_log()` 截断。

---

## 七、安全防护设计

四层防护，逐层加固：

### 第 1 层：Prompt 约束
在 DSL 生成的 system prompt 中明确：
- 只能生成只读查询 DSL（_search / _count / _msearch）
- 只能查询 Schema RAG 登记的索引
- 必须包含 advertiser_id 过滤
- 必须包含时间范围过滤
- 不允许使用 script / painless 脚本
- 查询结果数不超过上限

### 第 2 层：DSL 结构校验（核心）
执行前必须通过 `DslValidator`：

| 校验规则 | 说明 | 违规处理 |
|---------|------|---------|
| 索引白名单 | 只能查 Schema RAG 登记的索引 | 拒绝 + 重试 |
| 广告主必填 | 必须有 advertiser_id term 过滤 | 拒绝 + 重试 |
| 时间范围必填 | 必须有 data_date range 过滤 | 拒绝 + 重试 |
| 结果数上限 | size ≤ 1000，agg size ≤ 500 | 自动截断 + 告警 |
| 禁用脚本 | 不允许 script / script_fields | 拒绝 + 重试 |
| 禁用写入端点 | 只允许 _search / _count / _msearch | 拒绝 + 报错 |
| 禁用管理操作 | 不允许 _cluster / _settings / _mapping | 拒绝 + 报错 |
| JSON 合法性 | 必须是合法 JSON | 拒绝 + 重试 |

### 第 3 层：ES 只读账号
- NL→DSL 模块使用独立 ES 只读角色
- 权限：`read` + `view_index_metadata`（仅限白名单索引）
- 无 `write` / `manage` / `create_index` 权限

### 第 4 层：执行时防护

| 防护 | 默认值 |
|------|--------|
| 查询超时 | 30 秒 |
| 最大结果数（size） | 1000 条 |
| 聚合桶数上限（agg size） | 500 |
| 最大查询步数 | 5 步 |

---

## 八、澄清交互机制

三层澄清，统一走 `clarify` 中断节点：

### 第 1 层：意图层澄清
**触发**：必填项（广告主/时间/指标）缺失或歧义
**澄清后回跳**：`continue_report` → `report_intent`

### 第 2 层：查询层澄清
**触发**：NL→DSL 阶段发现信息不足，但知道缺什么（指标歧义、维度粒度不明确、过滤条件缺少定义等）
**澄清后回跳**：`continue_nl_dsl` → `nl_dsl_node`

设计原则：
- 给出具体选项（从 Schema 来的真实选项），不让用户填空
- 一次只问一件事

### 第 3 层：失败引导（不是澄清）
**触发**：NL→DSL 执行 3 次失败，或空结果且自查没问题
**处理**：生成失败引导报告，直接返回给用户，不中断等待
**内容**：失败原因 + 建议的提问方式 + 可用指标/维度列表

### LangGraph 路由变更

`route_after_clarify` 新增回跳点：
```python
if clarify_next == "continue_nl_dsl":
    return "nl_dsl"
```

### 澄清反馈合并策略

用户提交澄清后，反馈信息需要合并回 `user_input`，供下游 `report_intent` 重新解析使用。

**合并策略（优化后）**：
- 不替换原始输入，而是**追加到末尾**，保证 LLM 重新提取时上下文完整
- 按澄清类型加**语义前缀**，帮助 LLM 正确理解反馈含义：
  - `missing_time_range` → "时间范围：{反馈}"
  - `missing_advertiser` → "广告主：{反馈}"
  - `missing_metrics` → "指标：{反馈}"
  - `missing_ad_level` → "层级：{反馈}"

**示例**：
- 原始输入："消耗>10的广告计划有哪些"
- 澄清类型：missing_time_range
- 用户反馈："4月份"
- 合并后："消耗>10的广告计划有哪些，时间范围：4月份"

**修改文件**：`src/intent/clarify_node.py`

### 前端澄清弹窗 UX 优化

**问题**：用户点击确认后，弹窗一直等到 API 完全返回才关闭，体验卡顿。

**优化方案**：

1. **立即关闭弹窗**：点击确认后立刻 `showClarification: false`，不等待 API 响应
2. **立即追加用户消息**：将用户的澄清选择作为一条 user message 追加到聊天历史
3. **显示全局 loading**：`isLoading: true`，表示正在处理
4. **按钮防重复提交**：点击后按钮 disabled，显示"处理中..."，防止重复点击

**修改文件**：
- `frontend/src/stores/chatStore.ts` - `submitClarification` 立即关闭弹窗 + 添加用户消息
- `frontend/src/components/ClarificationModal.tsx` - `submitting` 状态

---

## 九、呈现类型与结果格式化

### 9.1 呈现类型分类

| 类型 | display_type | 典型查询 | 展示方式 |
|------|-------------|---------|---------|
| 数值问答 | `qa` | "消耗是多少？" | 大数字卡片 + 简短说明 |
| 实体列表 | `list` | "消耗>10的campaign列表" | 数据表格 + 分页 |
| 趋势分析 | `trend` | "最近7天消耗趋势" | 折线图 + 数据表格 |
| 横向对比 | `comparison` | "各ad_group消耗对比" | 柱状图 / 条形图 + 排名表 |
| 排名分析 | `ranking` | "消耗Top 10计划" | 条形图 + 排行榜 |
| 受众分布 | `audience` | "性别分布" | 饼图 / 环形图 + 占比表 |
| 受众对比 | `audience_comparison` | "近两周性别分布对比" | 双环形图并排 / 分组柱状图 + 对比表 |
| 明细数据 | `detail` | "每天消耗点击明细" | 多列数据表格 |

### 9.2 呈现类型确定

两步确认：
1. 意图层给出 `analysis_type` 建议
2. 结果格式化器根据实际返回数据形态做二次确认

### 9.3 结果统一格式

NL→DSL 查询结果统一成中间格式，再交给 reporter 生成 final_report：

```python
{
    "display_type": "trend",          # 呈现类型
    "columns": ["日期", "消耗", "点击"],  # 列名
    "rows": [[...], [...]],            # 数据行
    "metadata": {                      # 元数据
        "total_rows": 100,
        "index_used": "ad_stat_data",
        "query_steps": 2,
        "retries": 0,
        "execution_time_ms": 1500
    }
}
```

### 9.4 ResultFormatter 设计要点

`ResultFormatter`（`src/nl_dsl/result_formatter.py`）负责将 ES 原始响应转换为统一中间格式。

**聚合 vs Hits 判断逻辑**：
- 聚合查询（size=0 或 size>0 但有 aggs）和明细查询（hits 文档）需要不同的格式化逻辑
- 判断优先级：如果有聚合结果且没有实际命中文档（`len(hits.hits) == 0`），按聚合结果格式化
- 注意：不能仅用 `hits.total > 0` 判断，因为 size=0 的纯聚合查询 `hits.total` 可能有值但 `hits.hits` 为空数组

**format() 入口逻辑**：
```python
has_hit_docs = len(response.get("hits", {}).get("hits", [])) > 0
has_aggs = bool(response.get("aggregations"))
if has_aggs and not has_hit_docs:
    return _format_aggregations(response, display_type_hint)
elif has_hit_docs:
    return _format_hits(response, display_type_hint)
else:
    return empty_result
```

### 9.5 列名映射与用户友好显示

NL→DSL 返回的列名可能是聚合名（如 `by_campaign`、`total_cost`）或 ES 原始字段名（如 `data_value`），需要映射为用户可理解的中文名称。

**映射规则**：

1. **聚合名 → 实际字段**：从 DSL 的 `aggs` 结构中解析聚合名对应的实际 ES 字段
   - `terms` agg：`field` 属性即为维度字段（如 `by_campaign` → `campaign_id`）
   - `date_histogram` agg：`field` 属性即为时间字段
   - `sum/avg/min/max/value_count/cardinality` agg：`field` 属性即为度量字段

2. **字段名 → 中文显示名**：
   - 维度字段：通过维度映射表转换（`campaign_id` → "计划ID"，`data_date` → "日期" 等）
   - 度量字段：`data_value` 需要结合 `data_type` 条件判断实际指标（`data_type=3` → "消耗"）
   - 指标识别：从 DSL 的 `query.bool.filter.term.data_type` 或 filter agg 中提取

3. **实现模块**：`src/nl_dsl/field_mapping.py`
   - `extract_agg_field_mapping(dsl)`：从 DSL 提取「聚合名 → 实际字段名」映射
   - `extract_data_types_from_dsl(dsl)`：从 DSL 提取涉及的 data_type 值
   - `get_dimension_display_name(field)`：维度字段 → 中文名
   - `get_metric_display_name(data_type)`：data_type → 指标中文名

### 9.6 实体名称自动补全

对于包含 ID 列的列表结果（campaign_id、adgroup_id 等），自动查询对应维度表，补充名称列，提升可读性。

**补全规则**：

| ID 字段 | 名称列 | 查询来源 |
|---------|--------|---------|
| `advertiser_id` | 广告主名称 | advertiser 索引 |
| `campaign_id` | 计划名称 | campaign 索引 |
| `adgroup_id` | 广告组名称 | adgroup 索引 |
| `creative_id` | 创意名称 | creative 索引 |

**实现方式**：
- 工具函数 `get_entity_names(entity_type, entity_ids)`（位于 `src/tools/hierarchy_utils.py`）
- 批量从 ES 对应维度索引查询，返回 `{id: name}` 字典
- 在 `_build_nl_dsl_final_report()` 中：检测到 ID 列后批量查询名称，在 ID 列后插入名称列

### 9.7 明细查询自动聚合去重

**问题**：LLM 生成的查询有时不稳定，对"XX有哪些"这类问题可能生成 detail/hits 查询而非 terms 聚合。明细是按天存储的，同一实体会出现多条（每天一条），导致列表展示冗余且包含多余的日期列。

**自动处理逻辑**（在 `_build_nl_dsl_final_report()` 中）：

三级判断，全部满足则触发自动聚合：
1. **不是聚合结果**：结果来自 hits 明细（非 aggs）
2. **同时包含维度 ID 列和指标列**：如 campaign_id + 消耗
3. **存在重复 ID**：抽样前 N 行检测到同一 ID 出现多次

**聚合方式**：
- 按维度 ID 分组
- 指标列求和（长表结构下，明细行的 data_value 即当天该指标值，累加即总消耗/总点击等）
- 移除明细专用列（如 data_date、data_type、data_value）
- 最终输出：每个实体一行 + 维度名称补全

### 9.8 display_type 归一化

查询规划阶段输出的 `analysis_type`（如 `exploratory_query`、`comparison`、`detail`）与前端渲染的 `display_type` 不完全对应，需要归一化：

- `exploratory_query` → `list`（实体探索类查询，用列表展示）
- `detail` → `list`（明细查询，用列表/表格展示）
- `comparison` → `list`（对比查询，先以列表形式呈现数据）

归一化在 `_build_nl_dsl_final_report()` 中完成，确保下游 reporter 和前端收到的是标准 display_type 枚举值。

---

## 十、服务端分页设计

### 10.1 final_report 新增分页字段

```python
final_report = {
    "title": "...",
    "display_type": "list",
    "data_table": {
        "columns": ["ID", "名称", "消耗"],
        "rows": [...],
        "pagination": {              # 可选，无分页则不包含
            "page": 1,
            "page_size": 20,
            "total": 156,
            "total_pages": 8
        }
    },
    "query_context": {               # 不返回前端，存在 graph_state 中
        "index": "ad_stat_data",
        "base_dsl": {...},           # 去掉 from/size 的原始 DSL
        "sort": [...],
        "total": 156
    }
}
```

### 10.2 翻页 API

新增轻量 API，不走 Graph 主流程：

```
POST /api/sessions/{session_id}/list-page
body: {
  "report_id": "...",    # 标识哪个列表查询
  "page": 2,
  "page_size": 20
}
```

后端操作：
1. 根据 session + report_id 找到 query_context
2. 修改 from/size，重新执行 ES 查询
3. 返回新一页数据 + 更新后的 pagination

### 10.3 前端适配

DataTable 组件：
- 有 `pagination` 字段 → 服务端分页模式，翻页调用 API
- 无 `pagination` 字段 → 客户端分页模式（现状不变）

### 10.4 ES 分页方式

默认使用 `from + size`（简单，满足大部分场景）。深分页需求出现后再切 `search_after`。

---

## 十一、Graph 流程变更

### 11.1 新增节点

- **`nl_dsl_node`**：NL→DSL 查询节点，封装 Schema RAG 检索 + 查询规划 + DSL 生成 + 安全校验 + 自反思执行 + 结果格式化全流程。

### 11.2 路由变更

**`route_after_report_intent` 新增 nl_dsl 分支**：
```python
def route_after_report_intent(state: dict) -> str:
    if state.get("needs_clarification", False):
        return "clarify"
    if state.get("final_report"):
        return "reporter"
    if state.get("query_route") == "nl_dsl":
        return "nl_dsl"
    return "planner"
```

**`route_after_clarify` 新增 continue_nl_dsl 回跳**：
```python
def route_after_clarify(state: dict) -> str:
    clarify_next = state.get("clarify_next", "reentry_top")
    if clarify_next == "continue_nl_dsl":
        return "nl_dsl"
    # ... 其他分支不变
```

### 11.3 下游节点

- **reporter_node**：改造，支持 `display_type` 生成不同格式 final_report
- **insight_node / analyst_node**：结构化路径保持不变；NL→DSL 路径目前直接到 reporter，不经过洞察分析（后续可扩展）

---

## 十二、日志规范对齐

所有新增模块严格遵循现有日志规范：

### 日志格式
```
时间 [级别] [request_id] [session_id] [模块名] 消息内容
```

### 规范要点
- 只用 INFO / ERROR 两个级别
- request_id / session_id 通过 contextvars 自动注入
- 长文本用 `truncate_log()` 截断（默认 1000 字）
- 错误用 `logger.exception()` 打印完整堆栈
- 节点进入/离开日志通过 callbacks 自动打印

### 新增日志点汇总
见各模块设计中的日志表格（意图层、NL→DSL 生成器、自反思执行器、Schema RAG）。

---

## 十三、演进路线

### 阶段一：基础能力（本次实施）
1. Schema RAG 建设（索引+字段+示例三级文档）
2. 意图理解层改造（去掉硬编码能力校验 + 路由判断）
3. NL→DSL 单步查询（简单 ad-hoc 查询）
4. DSL 安全校验 + 自反思重试
5. 结果格式化 + 呈现类型（列表/问答/趋势/对比）
6. nl_dsl_node 接入 Graph
7. 全链路日志

### 阶段二：能力增强（后续迭代）
1. 多步查询支持（场景四类型）
2. 服务端分页 API
3. 受众分析呈现类型（饼图/环形图）
4. 受众对比呈现类型
5. 查询层澄清机制

### 阶段三：长期优化（未来）
1. 历史查询库（SQL/DSL 历史检索，越用越准）
2. Schema 自动扫描同步
3. 语义层 / 指标平台
4. NL→DSL 准确率足够高后，逐步将结构化查询迁过来

---

## 十四、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| NL→DSL 准确率不足 | 复杂查询经常失败 | 1. Schema RAG + few-shot 示例提升准确率 2. 自反思重试 3. 结构化路径作为兜底 |
| 安全漏洞 | 数据泄露 / 写入操作 | 四层防护逐层加固，ES 只读账号是最后防线 |
| Schema RAG 维护成本高 | 新增数据不及时 | 初期手动注册，后续加自动扫描工具 |
| LLM 成本增加 | 多步查询 + 重试 token 消耗大 | 1. 结构化路径优先 2. 限制最大步数和重试次数 3. 后续优化 prompt 大小 |
| 空结果误判 | 明明有数据却说没有 | 结果检查 + 一轮自查 + 如实告知查询条件让用户验证 |
