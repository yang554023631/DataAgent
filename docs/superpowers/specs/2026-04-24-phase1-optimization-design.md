# 第一阶段优化：核心功能修复 设计文档

## 一、优化概述

### 1.1 背景
基于用户实际体验反馈，系统核心功能已实现基础版本，但仍有部分细节需要完善。

### 1.2 已确认的已实现功能
系统已实现以下核心能力（基于代码验证）：

| 功能模块 | 实现状态 | 说明 |
|---------|---------|------|
| **真实ES数据源** | ✅ 已实现 | 直接连接 `localhost:9200`，无mock，查询 `ad_stat_data` 和 `ad_stat_audience` 索引 |
| **广告主支持** | ✅ 已实现 | 支持查询具体广告主（单/多），用户不知广告主时可显示列表 |
| **指标支持** | ✅ 已实现 | 曝光、点击、花费、转化、CTR、CVR、ROI 等25个指标 |
| **受众维度** | ✅ 已实现 | 性别、年龄、操作系统、兴趣标签 |
| **时间粒度** | ✅ 已实现 | 分天（data_date）、分小时（data_hour） |

### 1.3 优化目标
- ✅（已实现但需验证）维度组合正确解析（性别+月、分天+分受众等多维度组合）
- ⬜ 补充分月、分周维度关键词映射
- ⬜ 时间对比查询正确执行（上个月 vs 上上个月）
- ⬜ 移除后端随机生成的 WOW_CHANGE 字段

---

## 二、已实现功能补充说明

### 2.1 真实Elasticsearch数据源

**实现位置**：`backend/src/tools/custom_report_client.py`

**核心实现**：
- ES客户端：`Elasticsearch(["http://localhost:9200"])`
- 数据索引：
  - `ad_stat_data` - 基础统计数据（按天、按活动等）
  - `ad_stat_audience` - 受众细分数据（性别、年龄、OS、兴趣）
- 支持数据类型：曝光(1)、点击(2)、花费(3)、转化(4)

**查询构建**：
```python
def build_es_query(query_request) -> tuple[str, Dict[str, Any]]:
    # 根据group_by中是否包含audience_前缀选择索引
    # 支持嵌套聚合，多维度组合
    # 受众维度需要额外过滤 audience_type
```

---

### 2.2 广告主列表与选择功能

**实现位置**：`backend/src/services/advertiser_service.py` + `backend/src/agents/nlu_agent.py`

**核心功能**：

1. **获取所有广告主列表**：`get_all_advertisers()` - 查询 `advertiser` 索引
2. **按ID/名称搜索广告主**：`get_advertiser_by_id()`, `get_advertiser_by_name()`
3. **广告主列表查询检测**：`is_advertiser_list_query(user_input)`
   - 关键词："有哪些"、"列表"、"选哪个"、"选哪些"、"可用的"
4. **从输入提取广告主**：`extract_advertiser_from_input(user_input)`
   - 支持完整名称匹配
   - 支持前缀模糊匹配（如"六一八智能"匹配"六一八智能_406"）
   - 支持ID精确匹配（带边界检查）

**NLU 输出字段**：
```json
{
  "advertiser_ids": ["123", "456"],
  "show_advertiser_list": false,
  "need_advertiser_selection": false
}
```

---

### 2.3 完整指标与维度映射

**实现位置**：`backend/src/tools/term_mapper.py`

**已支持指标（25个）**：
| 中文术语 | 标准字段 |
|---------|---------|
| 曝光、展示、展示量 | impressions |
| 点击、点击量 | clicks |
| 花费、消耗、消费、成本 | cost |
| 转化、转化数、转化量 | conversions |
| 点击率、CTR | ctr |
| 转化率、CVR | cvr |
| 投产比、ROI | roi |

**已支持维度**：
| 维度类型 | 中文术语 | 标准字段 |
|---------|---------|---------|
| 时间 | 日期、按天、每天 | data_date |
| 时间 | 小时、分时、时段 | data_hour |
| 受众 | 性别、按性别 | audience_gender |
| 受众 | 年龄段、年龄、按年龄 | audience_age |
| 受众 | 系统、平台、操作系统、按平台、按系统、OS | audience_os |
| 受众 | 兴趣、兴趣标签、按兴趣 | audience_interest |
| 广告结构 | 渠道、广告活动、活动 | campaign_id |
| 广告结构 | 广告组、组 | adgroup_id |
| 广告结构 | 创意、素材 | creative_id |

---

## 三、问题1：维度组合解析修复

### 2.1 问题描述
用户查询"看广告主 电商家居_40_new 最近5个月的转化数的性别按月细分分析"，系统没有正确识别"性别 + 月"的多维度组合。

### 2.2 根因分析
- NLU Agent 可能只识别了第一个维度，没有正确解析多维度组合
- Planner Agent 可能没有正确处理 `group_by` 数组
- 与后端 CustomReport 接口的参数传递可能有误

### 2.3 修复方案

#### 2.3.1 NLU Agent 优化
在 `nlu.py` 的 prompt 中明确强调多维度组合识别：
```
用户可能请求多个维度组合，例如：
- "按性别和月份" → group_by: ["gender", "month"]
- "分天+分受众" → group_by: ["date", "audience"]
- "按地区、设备、年龄段" → group_by: ["region", "device", "age_group"]

请将所有维度都解析到 group_by 数组中，不要遗漏。
```

#### 2.3.2 Planner Agent 增强
在 `planner.py` 中增加多维度校验和处理逻辑：
```python
def validate_multi_dimension(group_by: List[str]) -> Tuple[bool, List[str]]:
    """校验多维度组合的合法性"""
    # 检查维度数量限制（最多支持几个维度）
    if len(group_by) > 3:
        return False, ["最多支持3个维度组合，请减少查询维度"]
    
    # 检查维度之间的兼容性
    # 例如：date 和 month 不能同时出现（冗余）
    if "date" in group_by and "month" in group_by:
        group_by.remove("month")  # 保留更细粒度的date
    
    return True, []
```

#### 2.3.3 数据层适配
确保 `custom_report_client.py` 正确传递多维度参数：
```python
# 确认接口是否支持多维度，参数格式是否正确
params = {
    "group_by": ",".join(group_by)  # 或数组形式，根据接口要求
}
```

### 2.4 涉及文件
- `backend/src/agents/nlu.py` - prompt优化
- `backend/src/agents/planner.py` - 多维度校验逻辑
- `backend/src/tools/custom_report_client.py` - 参数传递确认
- `backend/src/models/intent.py` - 确认字段定义

---

## 三、问题2：时间对比查询修复

### 3.1 问题描述
用户查询"上个月和上上个月的点击数对比"，系统没有返回两个月的对比数据，可能只返回了一个时间范围的数据。

### 3.2 根因分析
- 当前 QueryIntent 只支持单个 time_range，不支持对比查询
- NLU 没有识别"对比"语义
- 整个流程没有处理多次查询合并的逻辑

### 3.3 修复方案

#### 3.3.1 模型扩展
在 `backend/src/models/intent.py` 中扩展：
```python
class QueryIntent(BaseModel):
    # 原有字段...
    time_range: TimeRange
    
    # 新增对比查询支持
    is_comparison: bool = False
    compare_time_range: Optional[TimeRange] = None
    compare_type: Optional[str] = None  # "period_over_period" | "dimension_compare"
```

#### 3.3.2 NLU Agent 对比语义识别
在 NLU prompt 中增加对比查询识别规则：
```
对比查询识别：
- "A和B对比" / "A与B比较" / "对比A和B" → is_comparison: true
- "上个月和上上个月" → time_range: {上个月}, compare_time_range: {上上个月}
- "今天和昨天" → time_range: {今天}, compare_time_range: {昨天}
- "本周 vs 上周" → time_range: {本周}, compare_time_range: {上周}
```

#### 3.3.3 Planner Agent 对比查询规划
```python
def plan_comparison_query(intent: QueryIntent) -> List[QueryRequest]:
    """生成对比查询的多个请求"""
    queries = []
    
    # 第一个查询：主时间范围
    queries.append(build_query(intent.time_range, intent))
    
    # 第二个查询：对比时间范围
    if intent.compare_time_range:
        queries.append(build_query(intent.compare_time_range, intent))
    
    return queries
```

#### 3.3.4 Executor Node 并行执行
支持执行多个查询：
```python
async def execute_multiple_queries(queries: List[QueryRequest]) -> List[QueryResult]:
    """并行执行多个查询"""
    tasks = [execute_single_query(q) for q in queries]
    results = await asyncio.gather(*tasks)
    return results
```

#### 3.3.5 Reporter Agent 对比格式化
```python
def format_comparison_report(results: List[QueryResult]) -> FinalReport:
    """将多个查询结果格式化为对比报告"""
    result1, result2 = results
    
    # 计算变化率
    change_rate = (result2.total - result1.total) / result1.total * 100
    
    return {
        "title": f"{result1.period} vs {result2.period} 对比",
        "key_metrics": [
            {"name": f"{result1.period} 点击", "value": result1.total},
            {"name": f"{result2.period} 点击", "value": result2.total},
            {"name": "变化", "value": f"{change_rate:+.1f}%"}
        ],
        "comparison_data": {
            "period1": result1.data,
            "period2": result2.data
        }
    }
```

#### 3.3.6 State 扩展
在 `AdReportState` 中增加：
```python
class AdReportState(BaseModel):
    # ... 原有字段
    is_comparison: bool = False
    query_requests: List[Dict] = []  # 支持多个查询请求
    query_results: List[Dict] = []   # 支持多个查询结果
```

#### 3.3.7 对比图表可视化设计

**Reporter Agent 输出图表配置**：
```python
def format_comparison_report(results: List[QueryResult]) -> FinalReport:
    # ... 原有逻辑
    
    return {
        "title": f"{result1.period} vs {result2.period} 对比",
        "key_metrics": [...],
        "comparison_data": {
            "period1": {"name": result1.period, "color": "#10b981", "data": result1.data},
            "period2": {"name": result2.period, "color": "#3b82f6", "data": result2.data}
        },
        "chart_config": {
            "type": "line",  # 趋势对比用折线图
            "x_axis": "date",
            "y_axis": "clicks",
            "series": [
                {"name": result1.period, "dataKey": "period1", "color": "#10b981"},
                {"name": result2.period, "dataKey": "period2", "color": "#3b82f6"}
            ]
        }
    }
```

**前端 ChartRenderer 对比图表支持**：
```typescript
const renderComparisonChart = (config: ChartConfig, data: any) => {
    // 根据配置渲染对比图表
    if (config.type === 'line') {
        // 双折线图：两个时间周期的趋势对比
        return (
            <LineChart>
                {config.series.map((s, i) => (
                    <Line 
                        key={i}
                        dataKey={s.dataKey}
                        name={s.name}
                        stroke={s.color}
                    />
                ))}
            </LineChart>
        );
    } else if (config.type === 'bar') {
        // 分组柱状图：对比各维度数据
        return (
            <BarChart>
                {config.series.map((s, i) => (
                    <Bar 
                        key={i}
                        dataKey={s.dataKey}
                        name={s.name}
                        fill={s.color}
                    />
                ))}
            </BarChart>
        );
    }
};

// 自动判断图表类型
const autoSelectChartType = (isComparison: boolean, groupBy: string[]) => {
    if (isComparison) {
        if (groupBy.includes('date') || groupBy.includes('day') || groupBy.includes('hour')) {
            return 'line';  // 时间维度对比用折线图
        }
        return 'bar';  // 分类维度对比用柱状图
    }
    // 非对比查询沿用原有逻辑
};
```

**对比图表类型规则**：
| 场景 | 推荐图表类型 | 示例 |
|------|-------------|------|
| 时间趋势对比（按天/按月） | 双折线图（不同颜色） | 3月 vs 4月的日点击趋势 |
| 分类维度对比 | 分组柱状图 | 男 vs 女的各指标对比 |
| 占比对比 | 双饼图 或 100%堆叠柱状图 | 两个时期的渠道占比对比 |

### 3.4 涉及文件
- `backend/src/models/intent.py` - 扩展模型
- `backend/src/graph/state.py` - 扩展State
- `backend/src/agents/nlu.py` - 对比语义识别
- `backend/src/agents/planner.py` - 对比查询规划
- `backend/src/agents/executor.py` - 多查询并行执行
- `backend/src/agents/reporter.py` - 对比结果格式化 + 图表配置输出
- `frontend/src/components/ChartRenderer.tsx` - 对比图表渲染（双折线、分组柱状）

---

## 五、问题3：移除WOW_CHANGE字段

### 5.1 问题描述
后端在 `custom_report_client.py:260` 随机生成了 `wow_change` 字段：
```python
row["wow_change"] = random.uniform(-0.3, 0.3)
```
这个随机生成的环比数据没有实际业务意义，建议从数据源移除。

### 5.2 修复方案

**方案：后端直接不生成该字段**
删除 `custom_report_client.py` 中第 258-260 行代码：
```python
# 计算环比变化（模拟）
if result and len(result) > 0:
    for row in result:
        row["wow_change"] = random.uniform(-0.3, 0.3)
```

**优势**：
- 从源头解决问题，前端无需额外处理
- 减少不必要的数据传输
- 代码更简洁

### 5.3 涉及文件
- `backend/src/tools/custom_report_client.py` - 删除 wow_change 生成逻辑

---

## 六、问题4：补充分月、分周维度映射

### 6.1 问题描述
ES查询逻辑中已有 `data_month` 和 `data_week` 的处理（`build_es_query` 函数中第151-152行），但 `term_mapper.py` 缺少对应的关键词映射，用户输入"按月"、"按周"时无法识别。

### 6.2 修复方案

在 `backend/src/tools/term_mapper.py` 的 `DIMENSION_MAPPING` 中添加：
```python
DIMENSION_MAPPING = {
    # ... 原有映射
    "月份": "data_month",
    "按月": "data_month",
    "每月": "data_month",
    "周": "data_week",
    "按周": "data_week",
    "每周": "data_week",
}
```

### 6.3 涉及文件
- `backend/src/tools/term_mapper.py` - 添加月份、周度关键词映射

---

## 七、实施顺序

1. **优先级最高**：移除WOW_CHANGE字段（最简单，最快验证）
2. **优先级高**：补充分月、分周维度映射
3. **优先级高**：维度组合解析修复
4. **优先级中**：时间对比查询修复（改动较大，需要扩展多个模块）
5. **优先级中**：对比图表可视化

---

## 八、测试要点

### 6.1 维度组合测试用例
- [ ] "按性别和月份" → group_by: ["gender", "month"]
- [ ] "分天+分受众" → group_by: ["date", "audience"]
- [ ] "按地区、设备" → group_by: ["region", "device"]
- [ ] 超过3个维度 → 给出警告提示

### 8.2 维度映射测试用例
- [ ] "按月" → 映射为 data_month
- [ ] "按周" → 映射为 data_week
- [ ] "每月统计" → 映射为 data_month
- [ ] "每周汇总" → 映射为 data_week

### 8.3 对比查询测试用例
- [ ] "上个月和上上个月的点击数对比" → 识别为对比查询
- [ ] "今天和昨天的曝光" → 识别为对比查询
- [ ] "本周 vs 上周的转化" → 识别为对比查询
- [ ] "三月和四月的点击趋势对比" → 输出双折线图配置
- [ ] 普通查询（非对比）→ 正常执行

### 8.4 对比图表测试用例
- [ ] 时间趋势对比 → 渲染双折线图（不同颜色区分）
- [ ] 分类维度对比 → 渲染分组柱状图
- [ ] 图表图例正确显示两个周期名称
- [ ] 鼠标hover显示两个周期的具体数值对比

### 8.5 数据输出测试用例
- [ ] 查询结果中不包含 wow_change 字段
- [ ] 其他字段正常输出不受影响
