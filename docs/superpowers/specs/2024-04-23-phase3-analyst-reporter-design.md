# 广告报表多Agent系统 - 第三阶段设计文档

## 一、阶段目标

打通完整的数据流：**用户输入 → NLU 解析 → Planner 规划 → Executor 查数 → Analyst 分析 → Reporter 生成报告 → 前端展示**

重点实现 Analyst Agent 和 Reporter Agent 的业务逻辑。

---

## 二、Analyst Agent 详细设计

### 2.1 职责

输入：查询结果数据 (`query_result`)
输出：分析洞察 (`analysis_result`)
- 异常检测（大幅涨跌）
- 贡献度分析
- Top/Bottom 排名
- 趋势判断

### 2.2 核心分析算法

#### 算法 1：环比变化检测
```
对于每个维度项：
  current_value = 本期值
  previous_value = 上期值
  change_rate = (current - previous) / previous
  if |change_rate| > 0.2:
    标记为异常
    severity = high if |change_rate| > 0.4 else medium
```

#### 算法 2：离群点检测 (Z-score)
```
mean = 所有项的均值
std = 标准差

对于每个维度项：
  z_score = (value - mean) / std
  if |z_score| > 2:
    标记为离群点
```

#### 算法 3：贡献度计算
```
总变化 = Σ(当前 - 上期)

对于每个维度项：
  contribution = (该项变化) / 总变化 × 100%
  positive = contribution > 0
```

### 2.3 AnalysisResult 数据结构

```typescript
interface AnalysisResult {
  summary: string;                    // 一句话总结
  anomalies: Array<{
    type: 'sudden_change' | 'outlier';
    metric: string;                   // 哪个指标
    dimension_key: string;            // 哪个维度
    dimension_value: string;          // 维度值
    current_value: number;            // 当前值
    change_percent?: number;          // 变化率
    z_score?: number;                 // z-score
    severity: 'low' | 'medium' | 'high';
  }>;
  insights: Array<string>;            // 洞察列表
  rankings: {
    top: Array<{ name: string; value: number }>;
    bottom: Array<{ name: string; value: number }>;
  };
  recommendations: Array<string>;    // 建议
}
```

---

## 三、Reporter Agent 详细设计

### 3.1 职责

输入：`query_intent` + `query_result` + `analysis_result`
输出：`final_report`（友好的报告格式）

### 3.2 报告结构

```typescript
interface FinalReport {
  title: string;
  time_range: { start: string; end: string };
  metrics: Array<{
    name: string;
    value: number | string;
    change?: number;        // 环比变化率
    trend: 'up' | 'down' | 'flat';
  }>;
  highlights: Array<{
    type: 'positive' | 'negative' | 'info';
    text: string;
  }>;
  data_table: {
    columns: string[];
    rows: any[][];
  };
  next_queries: Array<string>;      // 推荐查询
}
```

### 3.3 数值格式化规则
- 曝光/点击：千分位（1,234,567）
- CTR/CVR：保留 2 位小数（2.34%）
- 花费：人民币格式（¥12,345.67）
- 环比：带方向符号（+23.4%、-15.2%）

---

## 四、Graph 节点更新

### 4.1 Analyst Node 实现
```python
async def analyst_node(state: dict) -> dict:
    query_result = state.get("query_result", {})
    query_request = state.get("query_request", {})
    
    # 1. 运行检测算法
    anomalies = detect_anomalies(query_result)
    rankings = calculate_rankings(query_result)
    
    # 2. 生成洞察
    insights = generate_insights(anomalies, rankings)
    
    # 3. 生成建议
    recommendations = generate_recommendations(insights)
    
    return {
        "analysis_result": {
            "summary": generate_summary(anomalies, rankings),
            "anomalies": anomalies,
            "insights": insights,
            "rankings": rankings,
            "recommendations": recommendations
        }
    }
```

### 4.2 Reporter Node 实现
```python
async def reporter_node(state: dict) -> dict:
    query_request = state.get("query_request", {})
    query_result = state.get("query_result", {})
    analysis_result = state.get("analysis_result", {})
    
    # 1. 格式化指标
    formatted_metrics = format_metrics(query_result, query_request)
    
    # 2. 生成亮点/告警
    highlights = generate_highlights(analysis_result)
    
    # 3. 准备表格数据
    data_table = prepare_data_table(query_result)
    
    # 4. 推荐后续查询
    next_queries = suggest_next_queries(query_request, analysis_result)
    
    return {
        "final_report": {
            "title": generate_title(query_request),
            "time_range": query_request.get("time_range"),
            "metrics": formatted_metrics,
            "highlights": highlights,
            "data_table": data_table,
            "next_queries": next_queries
        }
    }
```

---

## 五、前端展示升级

### 5.1 新增组件
- **MetricCard**：指标卡片，显示数值 + 环比
- **HighlightList**：亮点/告警列表
- **DataTable**：数据表格
- **ChartRenderer**：图表渲染（基于 query_request 选择）

### 5.2 消息内容增强
Assistant 消息不再只显示 JSON，而是富文本卡片组件。

### 5.3 页面布局优化
```
页面宽度优化：
- 主容器宽度：max-w-4xl → max-w-7xl（翻倍）
- Assistant 消息宽度：max-w-[80%] → max-w-full（报表全屏展示）
- 用户消息宽度：max-w-[80%] → max-w-[60%]（保持居右）
```

### 5.4 DataTable 分页增强
```
分页功能完整实现：
- 页面大小选择器：固定选项 [10, 20, 50, 100]
- 页码跳转输入框：支持直接跳转到指定页 + Enter 快捷键
- 完整分页控制：首页 / 上一页 / 页码按钮 / 下一页 / 末页
- 响应式布局：flex-wrap 适配小屏幕
- 页码按钮最多显示 5 个，超出时自动调整范围
```

### 5.5 ChartRenderer 图表可视化增强
```
双周期对比图表支持：
- 双折线图：时间趋势对比（data_date, data_hour 等时间维度）
- 分组柱状图：分类维度对比（gender, audience 等分类维度）
- 两个周期不同颜色区分：period1=绿色(#10b981), period2=蓝色(#3b82f6)
- 图表类型自动选择：auto_select_chart_type_for_comparison()

视觉优化：
- 容器高度：h-96(384px) → h-[520px]
- ECharts 内部高度：240px → 420px
- Grid 布局优化：top: '10%', bottom: '15%' 最大化绘图区域
```

---

## 三（补充）、对比报告设计

### C.1 对比报告数据结构
```typescript
interface FinalReport {
  // ... 原有字段
  is_comparison?: boolean;
  chart_config?: {
    type: 'line' | 'bar' | 'pie';
    series: Array<{ name: string; color: string }>;
    metrics?: string[];
    comparison_data?: {
      period1: { name: string; color: string; data: any[] };
      period2: { name: string; color: string; data: any[] };
    };
  };
}
```

### C.2 对比报告生成逻辑
```
format_comparison_report() 功能：
1. 双周期总指标对比（求和/平均值计算）
2. 变化率计算（+23.4% 格式）
3. 趋势判断（up/down/flat）
4. 维度项逐一对比表格
5. 对比专用 chart_config 生成
```

---

## 七、数据验证要求

### 7.1 空数据/错误处理验证

**强制要求：所有数据报表返回不能是告知报错或者告知查询完成但没有数据**

验证规则：
1. ✅ 查询成功但无数据时，必须返回友好的空数据提示（如"未查询到符合条件的数据"）
2. ✅ 查询失败时，必须返回具体的错误原因和解决建议
3. ✅ 禁止返回"查询完成"但没有任何数据内容
4. ✅ Reporter Agent 必须对空数据场景做特殊处理，返回有意义的提示
5. ✅ 前端必须对 error 场景做友好展示，不展示原始错误堆栈

---

## 八、Bug 修复记录

### 8.1 TypeError: '>' not supported between instances of 'NoneType' and 'int'
```
位置：backend/src/agents/reporter_agent.py:191

修复前：
change_percent = anomaly.get("change_percent", 0)

修复后：
change_percent = anomaly.get("change_percent", 0) or 0

原因：anomaly.change_percent 可能为 None，导致 TypeError
```

### 8.2 DataTable 分页条在单页时消失 Bug
```
位置：frontend/src/components/DataTable.tsx

问题：当数据行数刚好等于 pageSize（如 50 条）时，totalPages = 1，
      整个分页条（包括页面大小选择器）都消失了，用户无法切换页面大小。

修复前：
{totalPages > 1 && (...)}  // 只有多页才显示整个分页条

修复后：
{rows.length > 0 && (...)}  // 只要有数据就显示分页条
{totalPages > 1 && (...)}   // 但只有多页时才显示页码导航按钮

影响：选择 50 条/页时，页面大小选择器消失，用户无法改回 10 条/页
```

---

## 九、前端单元测试要求

### 9.1 测试框架选型
```
- Vitest - Vite 原生测试框架，速度快，配置简单
- React Testing Library - 用户行为导向的组件测试
- jsdom - 浏览器环境模拟
```

### 9.2 必须覆盖的测试场景

#### DataTable 组件
| 测试用例 | 优先级 | 说明 |
|---------|--------|------|
| 正确渲染列名和数据行 | 高 | 基础渲染功能 |
| 分页按钮功能正常 | 高 | 首页/上一页/下一页/末页 |
| 页面大小选择器工作 | 高 | 10/20/50/100 选项切换 |
| 页码跳转功能 | 中 | 输入页码直接跳转 |
| 空数据场景处理 | 中 | 没有数据时的显示 |
| 响应式布局 | 低 | flex-wrap 在小屏幕正常 |

#### ChartRenderer 组件
| 测试用例 | 优先级 | 说明 |
|---------|--------|------|
| 分类维度渲染柱状图 | 高 | 自动图表类型选择 |
| 时间维度渲染折线图 | 高 | 自动图表类型选择 |
| 对比查询渲染双周期图 | 高 | 两个周期数据对比 |
| 空数据不渲染图表 | 中 | 没有数据时返回 null |
| chart_config 参数正确解析 | 中 | 配置正确传递到 ECharts |

#### ChatMessage 组件
| 测试用例 | 优先级 | 说明 |
|---------|--------|------|
| 用户消息右对齐 | 高 | max-w-[60%] 样式 |
| Assistant 消息左对齐 | 高 | max-w-full 样式 |
| FinalReport 指标卡片渲染 | 高 | MetricCard 正确显示 |
| FinalReport 数据表格渲染 | 高 | DataTable 集成 |
| FinalReport 图表渲染 | 中 | ChartRenderer 集成 |
| 推荐查询点击事件 | 中 | onClick 回调正常触发 |

#### chatStore 状态管理
| 测试用例 | 优先级 | 说明 |
|---------|--------|------|
| 初始化 session | 高 | initSession 动作 |
| 发送消息追加到历史 | 高 | sendMessage 动作 |
| 澄清模态框显示/隐藏 | 中 | 状态正确切换 |
| 加载状态正确更新 | 中 | isLoading 状态 |

### 9.3 测试覆盖率要求
- **组件测试覆盖率：** ≥ 70%
- **核心组件（DataTable, ChartRenderer）：** ≥ 80%
- **状态管理：** ≥ 90%

---

## 十、实施任务分解

### Task 12：Analyst Agent 核心算法
- 异常检测算法（环比、Z-score）
- 排名分析
- 洞察生成
- 单元测试

### Task 13：Reporter Agent 实现
- 数值格式化工具
- 报告文案生成
- 亮点/告警生成
- 推荐查询
- 单元测试

### Task 14：Graph 节点完善
- 实现 analyst_node
- 实现 reporter_node
- 测试完整 Graph 流程

### Task 15：Mock 数据查询
- Mock CustomReport 客户端（无需真实服务）
- 支持前端直接测试完整流程

### Task 16：前端结果展示组件
- MetricCard 组件
- HighlightList 组件
- DataTable 组件
- 集成到 ChatMessage

### Task 17：端到端测试
- 完整流程测试
- 多场景用例验证
