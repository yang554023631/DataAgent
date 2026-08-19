# 筛选、模糊匹配、排序TopN功能增强设计

## 背景

第二轮多样化自然语言Query测试发现，8个失败case中有三类问题：

1. **排序 + TopN**：完全没有指导，LLM不知道如何结构化输出
2. **模糊匹配**：名称包含搜索，写法不明确
3. **多条件组合筛选**：where/having混合，写法不明确

这些问题不是功能不支持，而是：
- Prompt缺乏明确的写法指导和示例
- 后端对 `like` (模糊匹配) 和 `between` (区间) 操作符没有支持
- 后端不支持 `sort` + `top_n` 对聚合结果排序截断

## 设计目标

- 增强Prompt指导，给LLM明确的写法示例
- 补齐后端缺失的操作符支持
- 支持排序 + TopN，满足"找出消耗前三"这类常见查询
- 保持向后兼容，不破坏已有功能

## 方案设计

### 1. 操作符体系规范

重新规范筛选操作符：

| 操作符 | 含义 | 使用场景 | 对应ES实现 |
|--------|------|---------|-----------|
| `eq` | 精确等于 | 属性精确匹配某个值 | `term` 查询 |
| `like` | 模糊包含 | 名称模糊搜索（广告计划/组/创意名称） | `wildcard` 查询 `*value*` |
| `gt` / `gte` | 大于 / 大于等于 | 数值过滤 | `range` 查询 |
| `lt` / `lte` | 小于 / 小于等于 | 数值过滤 | `range` 查询 |
| `between` | 区间 | 数值在两个值之间 | 两个 `range` (gt + lt) |
| `in` | 列表包含 | 字段值等于列表中任意一个 | `terms` 查询 |

### 2. Schema 变更

`ReportIntentResult` 增加 `sort` 可选字段：

```python
# 文件: backend/src/intent/models.py
top_n: Optional[int] = None
sort: Optional[Dict[str, Any]] = Field(
    default=None,
    description="排序规则: {field: 排序字段名, order: desc 降序 / asc 升序}，配合 top_n 使用"
)
chart_type: Optional[str] = None
```

### 3. Prompt 增强

在 `REPORT_INTENT_SYSTEM_PROMPT` 中新增完整章节 **"筛选条件、排序、TopN写法指南"**，包含：

- 筛选条件基本结构说明
- 各操作符说明
- 单条件示例
- 多条件组合示例（双where / where + having）
- 排序 + TopN示例
- 最终输出格式示例更新

关键示例覆盖我们的失败场景：

| 用户说 | 正确写法 |
|--------|---------|
| "名称包含 mini 的广告计划" | `[{"field": "campaign_name", "operator": "like", "value": "mini", "type": "where"}]` |
| "投放中且名称包含 best 的广告计划" | 双条件 `eq` + `like` 放数组 |
| "名称包含 mini 且点击量大于 50 的创意" | `where` + `having` 混合 |
| "找出名称包含六一八的所有广告组，按消耗降序排列前三" | `top_n: 3` + `sort: {field: "cost", order: "desc"}` + `like` 过滤 |

### 4. 后端代码修改 (`build_es_query`)

#### 4.1 新增操作符支持

```python
# 在遍历filters的循环中增加：
elif op == "like":
    # 模糊匹配，名称包含子串
    bool_must.append({
        "wildcard": {
            field: f"*{value}*"
        }
    })
elif op == "between" and isinstance(value, list) and len(value) == 2:
    # 区间查询，转换为gt + lt
    min_val, max_val = value
    bool_must.append({"range": {field: {"gt": min_val}}})
    bool_must.append({"range": {field: {"lt": max_val}}})
```

#### 4.2 支持 `top_n` + `sort` 聚合排序

在构建terms聚合时：

```python
# 获取top_n和sort配置
top_n = model_dict.get("top_n")
sort_info = model_dict.get("sort")

# 基础terms配置
terms_config = {
    "field": actual_field,
    "size": top_n if (top_n and isinstance(top_n, int)) else 1000,
}

# 如果是最后一层分组且有排序要求，配置排序
if sort_info and i == len(group_by) - 1:
    sort_field = sort_info.get("field")
    sort_order = sort_info.get("order", "desc")
    # ES terms聚合按聚合指标值排序
    terms_config["order"] = {
        f"sum_{sort_field}.value": sort_order
    }

current[agg_name] = {
    "terms": terms_config,
    "aggs": {}
}
```

**说明：**
- 只对最后一层分组做排序，这符合用户直觉："按X分组后，对分组结果排序"
- 利用ES原生聚合排序，性能好，不需要后端内存排序
- 如果没有 `top_n`，默认还是返回1000条保持兼容

## 修改范围

| 文件 | 修改类型 | 改动量 |
|------|----------|--------|
| `backend/src/intent/models.py` | 新增`sort`字段 | +5行 |
| `backend/src/intent/prompts.py` | 新增写法指南+示例 | ~100行文字 |
| `backend/src/tools/custom_report_client.py` | 新增操作符+排序支持 | ~25行代码 |

## 测试验证

修改完成后，重新运行那8个失败case，预期：

| 测试ID | 查询内容 | 预期结果 |
|--------|---------|---------|
| 9 | 名称带digital，按消耗排序 | 成功生成结构化筛选+排序 |
| 12 | 名称包含六一八，按消耗降序前三 | 成功 |
| 15 | 名称含尊享的所有创意 | 成功 |
| 18 | 投放中 + 名称含best | 成功 |
| 19 | 名称含mini + 点击大于50 | 成功 |
| 50 | 点击率前五的广告组 | 成功 |
| 52 | 转化率最高的三个创意 | 成功 |
| 54 | 按不同操作系统看消耗占比 | 成功（结构已支持，置信度提升） |

## 风险评估

- **向后兼容**：新增字段都是可选，不影响已有查询 ✅
- **性能影响**：ES原生聚合排序，top_n减小返回条数，性能更好 ✅
- **模糊匹配性能**：`wildcard` 查询 `*value*` 在ES中性能不算特别好，但广告层级数据量不大，可接受 ✅

## 变更记录

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-08-16 | 初始设计 | Claude |
