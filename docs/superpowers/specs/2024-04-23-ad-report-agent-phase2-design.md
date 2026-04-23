# 广告报表多Agent系统 第二阶段设计文档

## 一、第二阶段目标

实现完整的 **自然语言理解 → 人机澄清 → 查询规划** 流程，让用户可以通过自然语言查询数据。

---

## 二、核心流程

```
用户输入自然语言
    ↓
🧠 NLU Agent 解析意图
    ↓
有歧义？ ──是──→ ❓ HITL 生成澄清选项 → 暂停Graph
    ↓否                          ↓用户回答后恢复
📋 Planner Agent 生成 QueryRequest
    ↓
进入数据执行流程（第一阶段已完成）
```

---

## 三、NLU Agent（意图理解）详细设计

### 3.1 职责
输入：用户自然语言 + 会话历史
输出：结构化的 `QueryIntent` + 歧义标记

### 3.2 能力范围

**支持的查询类型：**
1. **基础指标查询** - "看上周的曝光和点击"
2. **维度分组查询** - "按渠道看 CTR"
3. **过滤条件查询** - "看安卓端的花费"
4. **时间范围查询** - "近30天"、"上个月"、"2024年4月"
5. **对比查询** - "对比上周和上上周"
6. **归因分析** - "看花费增加来自哪里"

**需要解析的字段：**
- `time_range` - 时间范围
- `metrics` - 指标列表
- `group_by` - 分组维度
- `filters` - 过滤条件
- `is_incremental` - 是否增量修改（基于上一个查询）
- `intent_type` - 查询类型

### 3.3 Tools

```python
# tool 1: parse_time_range
@tool
def parse_time_range(text: str) -> TimeRange:
    """
    解析自然语言时间范围
    
    支持：
    - 今天、昨天
    - 本周、上周、上上周
    - 本月、上个月
    - 近N天、近N周、近N月
    - 2024年4月、4月15日到4月21日
    """

# tool 2: map_metrics
@tool
def map_metrics(text: str) -> List[str]:
    """
    将业务术语映射为标准指标名
    
    曝光、展示量 → impressions
    点击、点击量 → clicks
    花费、消耗 → cost
    点击率、CTR → ctr
    转化率、CVR → cvr
    投产比、ROI → roi
    """

# tool 3: map_dimensions
@tool
def map_dimensions(text: str) -> List[str]:
    """
    将业务术语映射为维度名
    
    渠道 → campaign_id
    广告组 → adgroup_id
    创意 → creative_id
    性别 → audience_gender
    年龄段 → audience_age
    系统、平台 → audience_os
    兴趣 → audience_interest
    """

# tool 4: parse_filters
@tool
def parse_filters(text: str) -> List[Filter]:
    """
    解析过滤条件
    
    "安卓端" → {"field": "audience_os", "op": "=", "value": 2}
    "非iOS" → {"field": "audience_os", "op": "!=", "value": 1}
    "花费大于1万" → {"field": "cost", "op": ">", "value": 10000}
    """
```

### 3.4 Prompt 设计

```python
NLU_PROMPT = """
你是广告报表意图理解专家。

你的任务是分析用户的自然语言输入，转换成结构化的查询意图。

已知指标映射：
{metric_mapping}

已知维度映射：
{dimension_mapping}

已知过滤操作符：
{filter_operators}

请分析用户输入，输出 JSON 格式的 QueryIntent：
{{
    "time_range": {{
        "start_date": "YYYY-MM-DD",
        "end_date": "YYYY-MM-DD",
        "unit": "day|week|month"
    }},
    "metrics": ["指标1", "指标2"],
    "group_by": ["维度1"],
    "filters": [
        {{"field": "字段名", "op": "=", "value": 值}}
    ],
    "is_incremental": true|false,
    "intent_type": "query|compare|attribution",
    "ambiguity": {{
        "has_ambiguity": true|false,
        "type": "metric|dimension|time|advertiser|other",
        "reason": "需要澄清的原因",
        "options": [
            {{"value": "xxx", "label": "xxx"}}
        ]
    }}
}}

上下文会话历史：
{conversation_history}

当前查询：
{user_input}

重要：
1. 如果是增量修改（基于上一个查询调整），is_incremental = true
2. 如果有歧义，必须标记并提供澄清选项
3. 时间范围如果不明确，标记为歧义
4. 指标或维度不明确时，提供可能的选项
"""
```

### 3.5 歧义检测场景

| 场景 | 处理 |
|------|------|
| "看一下数据" | 太泛 → 询问想看什么指标 |
| "看效果" | 效果不明确 → 提供选项（曝光点击/CTR/花费ROI） |
| "看近期数据" | 时间不明确 → 询问时间范围 |
| "看京东的数据" | 广告主不明确 → 列出匹配的广告主 |
| "按渠道看 CTR" | 维度和指标明确，无歧义 |

---

## 四、HITL Node（人机协调）详细设计

### 4.1 职责
- 接收上游传来的歧义信息或确认请求
- 生成标准化的澄清选项
- **暂停整个 Graph 执行**，等待用户输入
- 收到用户回答后，把答案写回 State
- 恢复 Graph 执行

### 4.2 特殊点：暂停-恢复机制

LangGraph 的 `interrupt_before` 机制：
```python
# 在 builder.py 中配置
graph.add_node("hitl", hitl_node)

# 在 hitl 节点之前暂停
graph.compile(interrupt_before=["hitl"])
```

**工作流程：**
1. NLU 节点发现歧义，设置 `ambiguity`
2. 条件边路由到 `hitl`
3. Graph 自动暂停（interrupt）
4. 前端展示澄清选项给用户
5. 用户选择后，调用 API 继续执行
6. hitl 节点把用户答案写入 `user_feedback`
7. 回到 NLU 节点重新解析

### 4.3 澄清选项生成 Tool

```python
@tool
def generate_clarification_options(
    ambiguity_type: str,
    context: dict
) -> ClarificationQuestion:
    """
    根据歧义类型生成澄清问题和选项
    
    ambiguity_type:
    - metric: 指标不明确
    - dimension: 维度不明确
    - time: 时间不明确
    - advertiser: 广告主不明确
    - query_too_large: 数据量太大需要确认
    - empty_data: 没有数据，询问是否调整
    """
```

### 4.4 澄清问题类型示例

```json
// 指标不明确
{
  "question": "您想查看哪些指标？",
  "options": [
    {"value": "impressions,clicks", "label": "曝光和点击"},
    {"value": "ctr,cvr", "label": "CTR和CVR"},
    {"value": "cost,roi", "label": "花费和ROI"}
  ],
  "allow_custom_input": false
}

// 广告主不明确
{
  "question": "匹配到多个广告主，请选择具体是哪一个：",
  "options": [
    {"value": "1001", "label": "京东官方旗舰店"},
    {"value": "1002", "label": "京东自营"}
  ],
  "allow_custom_input": true
}

// 数据量太大确认
{
  "question": "这个查询预计返回约 3650 条数据，可能耗时 8 秒，是否继续？",
  "options": [
    {"value": "confirm", "label": "确认查询"},
    {"value": "reduce_to_month", "label": "改成按月汇总"},
    {"value": "narrow_time", "label": "缩小到最近7天"}
  ],
  "allow_custom_input": false
}
```

---

## 五、Planner Agent（查询规划）详细设计

### 5.1 职责
输入：`QueryIntent` + `user_feedback`（如果有澄清）
输出：`QueryRequest` + `query_warnings`

### 5.2 核心功能

1. **补全默认值**
   - 没有时间 → 默认近7天
   - 没有指标 → 默认曝光、点击、CTR

2. **应用业务规则**
   - 受众维度自动切换到 audience 索引
   - 添加对应的 audience_type 过滤

3. **自动选择图表类型**
   - 时间维度 → line 折线图
   - 分类维度 < 10 → bar 柱状图
   - 分类维度 < 5 + 占比场景 → pie 饼图
   - 其他 → table 表格

4. **参数合法性校验**
   - 维度数量限制（最多3个）
   - 时间范围大小限制（最多90天）

5. **优化警告**
   - 维度太多："超过3个分组维度，图表可能难以阅读"
   - 数据量过大："预计返回超过1000行，是否确认？"

### 5.3 Tools

```python
# tool 1: apply_business_rules
@tool
def apply_business_rules(intent: QueryIntent) -> QueryIntent:
    """
    应用业务规则
    
    1. 如果包含 audience_* 维度，自动切换到 audience 索引
    2. 自动添加对应的 audience_type 过滤
    """

# tool 2: auto_select_chart_type
@tool
def auto_select_chart_type(metrics: List[str], dimensions: List[str]) -> ChartConfig:
    """
    根据指标和维度自动选择合适的图表类型
    """

# tool 3: validate_and_warn
@tool
def validate_and_warn(query_request: QueryRequest) -> List[str]:
    """
    校验参数并返回警告列表
    
    返回格式: ["warning message"]
    如果需要用户确认，消息中包含 "need_confirm" 标记
    """
```

### 5.4 Prompt 设计

```python
PLANNER_PROMPT = """
你是广告报表查询规划专家。

你的任务是把查询意图转换成合法的、可执行的 QueryRequest。

请处理以下 QueryIntent：
{query_intent}

用户澄清反馈（如果有）：
{user_feedback}

请执行以下步骤：
1. 补全缺失的默认值（时间默认近7天，指标默认曝光、点击、CTR）
2. 应用业务规则（受众维度切换索引和添加过滤）
3. 自动选择合适的图表类型
4. 校验参数合法性并生成警告

输出 JSON 格式：
{{
    "query_request": {{
        "index_type": "general|audience",
        "time_range": {...},
        "metrics": [],
        "group_by": [],
        "filters": [],
        "chart_config": {...}
    }},
    "query_warnings": ["警告1", "警告2"]
}}
"""
```

---

## 六、前端交互设计

### 6.1 澄清对话框

```
┌─────────────────────────────────┐
│ 需要澄清                        │
├─────────────────────────────────┤
│ 匹配到多个广告主，请选择：      │
│                                 │
│ ○ 京东官方旗舰店                │
│ ○ 京东自营                      │
│ ○ 京东数码专营店                │
│                                 │
│ [ 确认 ]  [ 取消 ]              │
└─────────────────────────────────┘
```

### 6.2 状态流转

```
用户输入 → 加载中... → 显示结果
              ↓
            弹出澄清对话框
              ↓
            用户选择 → 继续执行
```

---

## 七、API 接口设计

### 7.1 创建会话

```
POST /api/sessions
{
  "user_id": "xxx"
}
→ { "session_id": "xxx" }
```

### 7.2 发送消息

```
POST /api/sessions/{session_id}/messages
{
  "content": "看上周的曝光点击"
}
→ {
    "status": "completed",
    "result": {...}
  }
OR
→ {
    "status": "waiting_for_clarification",
    "clarification": {
      "question": "...",
      "options": [...]
    }
  }
```

### 7.3 提交澄清

```
POST /api/sessions/{session_id}/clarification
{
  "selected_value": "xxx"
}
→ {
    "status": "completed",
    "result": {...}
  }
```

---

## 八、实施阶段分解

### 任务 7：NLU Agent 实现
- 时间解析 Tool
- 业务术语映射 Tool
- NLU 节点实现
- Prompt 模板
- 单元测试

### 任务 8：HITL 节点实现
- Graph interrupt 机制
- 澄清选项生成 Tool
- 状态管理
- 单元测试

### 任务 9：Planner Agent 实现
- 业务规则 Tool
- 图表选择 Tool
- 参数校验 Tool
- Planner 节点实现
- 单元测试

### 任务 10：FastAPI 接口
- 会话管理 API
- 消息发送 API
- 澄清提交 API
- 集成测试

### 任务 11：前端对话界面
- 聊天消息组件
- 澄清对话框
- 状态管理
- API 对接
