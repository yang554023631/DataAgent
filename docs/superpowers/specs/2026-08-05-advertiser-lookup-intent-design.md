# 广告主查询功能设计 - 新意图识别架构

## 需求背景

在新意图识别架构中，顶层分类器已经能够识别广告主查询（列表查询/ID查名称/名称查ID），并归类为 `report` 类别。但 `report_intent` 阶段缺少对这种特殊查询的处理，导致错误地进入常规报表流程，触发不必要的澄清。

本文档设计在新意图识别架构中补全**纯广告主查询**功能支持。

## 功能范围

支持三种纯广告主查询场景：

| 场景 | 用户问句示例 | 预期响应 |
|------|-------------|---------|
| 1. 查询所有广告主列表 | "有哪些广告主"、"广告主列表"、"所有广告主" | 返回表格展示所有广告主的 ID 和名称，用户点击可选择进入后续查询 |
| 2. 根据 ID 查询名称 | "123广告主叫什么"、"广告主123的名称" | 返回该 ID 对应的广告主名称 |
| 3. 根据名称关键词搜索ID | "ABC广告主的ID是多少"、"搜索叫ABC的广告主" | 返回模糊匹配的广告主列表（ID+名称） |

## 设计方案

### 架构修改

**方案选择：在 `report_intent` 阶段检测并直接处理（方案一）**

优点：
- 简洁高效，不需要新增 Graph 节点
- 复用现有的 `advertiser_service` 查询函数
- 复用现有的 `final_report` 数据格式，前端展示无需修改

数据流向：

```
用户输入
  ↓
intent_classifier → 识别为 report 类别
  ↓
report_intent → 检测到是"纯广告主查询"
  ↓
  直接调用 advertiser_service 查询
  ↓
  生成 final_report 写入 state
  ↓
route_after_report_intent → 检测到 final_report 已存在，直接跳转到 reporter
  ↓
reporter → 输出响应 → END
```

### 具体修改点

#### 1. `src/intent/report_intent.py` - ReportIntentAnalyzer.analyze()

在方法**最开头**增加广告主查询检测逻辑：

1. **检测列表查询**：调用 `is_advertiser_list_query(user_input)` → 命中则生成所有广告主列表的 `final_report`
2. **检测ID查名称**：正则匹配 `r'(\d+)\s*(叫什么|名字|名称)'` 或 `r'广告主\s*(\d+)'` + 名称关键词 → 提取ID，调用 `get_advertiser_by_id` → 生成结果
3. **检测名称查ID**：匹配 `id|ID|编号` + 名称关键词 → 提取名称片段，调用 `get_advertiser_by_name` → 生成结果列表
4. 如果命中任一情况，将 `final_report` 写入返回结果，`result` 返回 `None`

#### 2. `src/graph/nodes.py` - report_intent_node()

修改：如果 `report_intent_result` 返回 `None` 但 `final_report` 存在，需要将 `final_report` 写入 state。

#### 3. `src/graph/builder.py` - route_after_report_intent()

增加判断：如果 `state.get("final_report")` 已存在，直接返回 `"reporter"`，跳过 planner。

路由逻辑更新：

```python
def route_after_report_intent(state: dict) -> str:
    """
    report_intent 之后的条件路由：
    - needs_clarification → clarify
    - final_report 已存在 → reporter（直接返回广告查询结果）
    - 信息完整 → planner
    """
    if state.get("needs_clarification", False):
        return "clarify"
    if state.get("final_report"):
        return "reporter"
    return "planner"
```

### 响应格式

复用现有的 `final_report` 格式，与 `advertiser_handle_node` 保持一致：

```python
{
  "title": "xxx",
  "time_range": {"start": "", "end": ""},
  "metrics": [],
  "highlights": [...],
  "data_table": {
    "columns": ["广告主ID", "广告主名称"],
    "rows": [[id, name], ...]
  },
  "next_queries": [...]  // 示例查询推荐
}
```

### 边界情况处理

1. **查询ID不存在** → 返回"未找到ID为xxx的广告主"提示
2. **搜索名称无匹配** → 返回"未找到匹配的广告主"提示 + 可选展示全列表
3. **多个名称匹配** → 返回全部匹配结果供选择
4. **LLM提取错误** → 不影响，规则检测优先

## 代码依赖

复用现有代码：
- `src/services/advertiser_service.py` - 所有查询函数已实现
- `src/graph/nodes.py` - `_generate_suggested_queries` 已存在可复用

### 4. 澄清回填机制（补充功能）

**问题**：当系统触发 `missing_advertiser` 类型的澄清后，用户选择/输入了广告主，系统会把用户反馈当作新的 `user_input` 重新丢给 LLM 解析。如果用户只输入了一个数字（如"6"），LLM 无法正确识别这是广告主ID，导致再次触发澄清。

**解决方案**：在 `report_intent_node` 开头增加澄清回填逻辑：

- 如果上一轮澄清类型是 `missing_advertiser`，且 `pending_clarification_input` 有值
- 调用 `_resolve_advertiser_from_feedback(feedback)` 解析用户反馈：
  - 纯数字 → 直接当作广告主ID
  - 非纯数字 → 当作名称搜索，调用 `get_advertiser_by_name` 匹配
- 解析出的广告主ID追加到 `existing_advertiser_ids`，传给 `analyze()`
- LLM 解析时会继承上下文的广告主，不会再问"选哪个广告主"

**修改文件**：
- `src/graph/nodes.py` - 新增 `_resolve_advertiser_from_feedback` 工具函数 + `report_intent_node` 开头回填逻辑

## 测试要点

1. ✅ 用户问"有哪些广告主" → 返回完整列表
2. ✅ 用户问"广告主123叫什么名字" → 返回正确名称
3. ✅ 用户问"ABC的ID是多少" → 返回匹配的广告主
4. ✅ 用户问"昨天的数据"（正常报表查询）→ 不影响原有流程
5. ✅ 用户问"帮我看看ABC广告主昨天的数据" → 正常报表流程，不触发广告查询
6. ✅ 缺广告主澄清后，用户选择ID=6 → 广告主回填成功，不会重复问广告主
7. ✅ 缺广告主澄清后，用户输入名称 → 名称匹配后回填，不会重复问广告主

## 实施记录

1. 修改 `builder.py` 路由逻辑（支持 `final_report` 直接跳 reporter）
2. 在 `report_intent.py` 增加纯广告主查询检测和响应生成逻辑
3. 修改 `report_intent_node` 处理 `final_report`
4. 在 `reporter_node` 增加已有 `final_report` 直接返回的短路逻辑
5. 增加 `missing_advertiser` 澄清回填机制
6. 更新测试适配新返回值签名
