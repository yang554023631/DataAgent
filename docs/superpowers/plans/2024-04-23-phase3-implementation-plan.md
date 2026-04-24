# 广告报表多Agent系统 - 第三阶段实施计划

## Task 12：Analyst Agent 核心算法

**Files:**
- Create: `backend/src/agents/analyst_agent.py`
- Create: `backend/src/tools/anomaly_detector.py`
- Create: `backend/tests/test_anomaly_detector.py`
- Create: `backend/tests/test_analyst_agent.py`

### Step 1: Create tools/anomaly_detector.py

```python
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from dataclasses import dataclass

@dataclass
class Anomaly:
    type: str  # sudden_change, outlier
    metric: str
    dimension_key: str
    dimension_value: str
    current_value: float
    change_percent: Optional[float] = None
    z_score: Optional[float] = None
    severity: str = "medium"  # low, medium, high

@tool
def detect_sudden_change(
    data: List[Dict[str, Any]],
    metric_field: str,
    change_field: str = "wow_change",
    threshold_high: float = 0.4,
    threshold_medium: float = 0.2
) -> List[Anomaly]:
    """检测环比突变"""
    anomalies = []
    
    for row in data:
        change = row.get(change_field)
        if change is None:
            continue
        
        abs_change = abs(float(change))
        if abs_change >= threshold_medium:
            severity = "high" if abs_change >= threshold_high else "medium"
            
            anomalies.append(Anomaly(
                type="sudden_change",
                metric=metric_field,
                dimension_key=row.get("dimension", "unknown"),
                dimension_value=str(row.get("name", row.get("id", "unknown"))),
                current_value=float(row.get(metric_field, 0)),
                change_percent=float(change),
                severity=severity
            ))
    
    return anomalies

@tool
def detect_z_score_outliers(
    data: List[Dict[str, Any]],
    metric_field: str,
    threshold: float = 2.0
) -> List[Anomaly]:
    """使用 Z-score 检测离群点"""
    values = [float(row.get(metric_field, 0)) for row in data if metric_field in row]
    
    if len(values) < 3:
        return []
    
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = variance ** 0.5
    
    if std == 0:
        return []
    
    anomalies = []
    for row in data:
        value = float(row.get(metric_field, 0))
        z_score = (value - mean) / std
        
        if abs(z_score) >= threshold:
            severity = "high" if abs(z_score) >= 3 else "medium"
            anomalies.append(Anomaly(
                type="outlier",
                metric=metric_field,
                dimension_key=row.get("dimension", "unknown"),
                dimension_value=str(row.get("name", row.get("id", "unknown"))),
                current_value=value,
                z_score=z_score,
                severity=severity
            ))
    
    return anomalies

@tool
def calculate_rankings(
    data: List[Dict[str, Any]],
    metric_field: str,
    top_n: int = 5
) -> Dict[str, List[Dict[str, Any]]]:
    """计算 Top/Bottom 排名"""
    sorted_data = sorted(
        data,
        key=lambda x: float(x.get(metric_field, 0)),
        reverse=True
    )
    
    return {
        "top": [
            {"name": str(row.get("name", row.get("id", i))), "value": float(row.get(metric_field, 0))}
            for i, row in enumerate(sorted_data[:top_n])
        ],
        "bottom": [
            {"name": str(row.get("name", row.get("id", len(sorted_data)-i-1))), "value": float(row.get(metric_field, 0))}
            for i, row in enumerate(sorted_data[-top_n:])
        ]
    }
```

### Step 2: Create agents/analyst_agent.py

```python
from typing import Dict, Any, List
from src.tools.anomaly_detector import (
    detect_sudden_change,
    detect_z_score_outliers,
    calculate_rankings,
    Anomaly
)

async def analyst_agent(query_result: Dict[str, Any], query_request: Dict[str, Any]) -> Dict[str, Any]:
    """数据分析 Agent"""
    data = query_result.get("data", [])
    metrics = query_request.get("metrics", ["impressions"])
    
    all_anomalies: List[Anomaly] = []
    
    for metric in metrics:
        # 检测环比突变
        if any("wow" in key.lower() for key in data[0].keys() if data):
            changes = detect_sudden_change.func(data, metric)
            all_anomalies.extend(changes)
        
        # 检测离群点
        outliers = detect_z_score_outliers.func(data, metric)
        all_anomalies.extend(outliers)
    
    # 计算排名（取第一个指标）
    main_metric = metrics[0] if metrics else "impressions"
    rankings = calculate_rankings.func(data, main_metric)
    
    # 生成洞察
    insights = []
    if all_anomalies:
        high_count = sum(1 for a in all_anomalies if a.severity == "high")
        if high_count > 0:
            insights.append(f"发现 {high_count} 个高度异常的数据点，建议重点关注")
    
    if len(all_anomalies) == 0:
        insights.append("数据表现平稳，未发现显著异常")
    
    # 生成建议
    recommendations = []
    if rankings.get("bottom"):
        recommendations.append(f"建议重点关注表现较差的渠道：{rankings['bottom'][0]['name']}")
    
    # 总结
    summary_parts = []
    if all_anomalies:
        summary_parts.append(f"检测到 {len(all_anomalies)} 个异常点")
    else:
        summary_parts.append("整体数据表现平稳")
    summary = "，".join(summary_parts)
    
    return {
        "summary": summary,
        "anomalies": [a.__dict__ for a in all_anomalies],
        "insights": insights,
        "rankings": rankings,
        "recommendations": recommendations
    }
```

### Step 3: Create tests

```python
import pytest
from src.tools.anomaly_detector import detect_sudden_change, detect_z_score_outliers, calculate_rankings
from src.agents.analyst_agent import analyst_agent

def test_detect_sudden_change():
    data = [
        {"name": "渠道A", "impressions": 1000, "wow_change": 0.5},
        {"name": "渠道B", "impressions": 2000, "wow_change": -0.1},
    ]
    anomalies = detect_sudden_change.func(data, "impressions")
    assert len(anomalies) == 1
    assert anomalies[0].severity == "high"

def test_detect_z_score_outliers():
    data = [
        {"name": "A", "ctr": 0.01},
        {"name": "B", "ctr": 0.015},
        {"name": "C", "ctr": 0.012},
        {"name": "D", "ctr": 0.05},  # 离群点
    ]
    outliers = detect_z_score_outliers.func(data, "ctr")
    assert len(outliers) >= 1

def test_calculate_rankings():
    data = [
        {"name": "渠道A", "impressions": 1000},
        {"name": "渠道B", "impressions": 2000},
        {"name": "渠道C", "impressions": 500},
    ]
    result = calculate_rankings.func(data, "impressions")
    assert "top" in result
    assert "bottom" in result
    assert result["top"][0]["name"] == "渠道B"

@pytest.mark.asyncio
async def test_analyst_agent():
    query_result = {
        "data": [
            {"name": "渠道A", "impressions": 1000, "wow_change": 0.5},
            {"name": "渠道B", "impressions": 2000, "wow_change": -0.1},
        ]
    }
    query_request = {"metrics": ["impressions"]}
    
    result = await analyst_agent(query_result, query_request)
    assert "anomalies" in result
    assert "rankings" in result
```

---

## Task 13：Reporter Agent 实现

**Files:**
- Create: `backend/src/agents/reporter_agent.py`
- Create: `backend/src/tools/formatters.py`
- Create: `backend/tests/test_reporter_agent.py`
- Update: `backend/src/graph/nodes.py`

### Step 1: Create tools/formatters.py

```python
from typing import Any
from langchain_core.tools import tool

@tool
def format_number(value: Any, decimals: int = 0) -> str:
    """格式化数字为千分位"""
    try:
        num = float(value)
        if decimals > 0:
            return f"{num:,.{decimals}f}"
        return f"{int(num):,}"
    except (ValueError, TypeError):
        return str(value)

@tool
def format_percent(value: Any, decimals: int = 2) -> str:
    """格式化百分比"""
    try:
        num = float(value)
        return f"{num * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return str(value)

@tool
def format_currency(value: Any, symbol: str = "¥") -> str:
    """格式化货币"""
    try:
        num = float(value)
        return f"{symbol}{num:,.2f}"
    except (ValueError, TypeError):
        return str(value)

@tool
def format_change(value: Any) -> str:
    """格式化环比变化，带正负号"""
    try:
        num = float(value)
        sign = "+" if num > 0 else ""
        return f"{sign}{num * 100:.2f}%"
    except (ValueError, TypeError):
        return str(value)

# 指标名称映射
METRIC_NAMES = {
    "impressions": "曝光量",
    "clicks": "点击量",
    "cost": "花费",
    "ctr": "CTR",
    "cvr": "CVR",
    "roi": "ROI",
}

@tool
def get_metric_display_name(metric: str) -> str:
    """获取指标的中文名称"""
    return METRIC_NAMES.get(metric, metric)
```

### Step 2: Create agents/reporter_agent.py

```python
from typing import Dict, Any, List
from src.tools.formatters import (
    format_number,
    format_percent,
    format_currency,
    format_change,
    get_metric_display_name
)

def get_trend(change: float) -> str:
    """判断趋势：up, down, flat"""
    if change is None:
        return "flat"
    if change > 0.05:
        return "up"
    if change < -0.05:
        return "down"
    return "flat"

async def reporter_agent(
    query_intent: Dict[str, Any],
    query_request: Dict[str, Any],
    query_result: Dict[str, Any],
    analysis_result: Dict[str, Any]
) -> Dict[str, Any]:
    """报告生成 Agent"""
    metrics = query_request.get("metrics", [])
    data = query_result.get("data", [])
    anomalies = analysis_result.get("anomalies", [])
    rankings = analysis_result.get("rankings", {})
    
    # 1. 计算总体指标（汇总）
    formatted_metrics = []
    for metric in metrics:
        total = sum(float(row.get(metric, 0)) for row in data) if data else 0
        
        # 根据指标类型选择格式化
        if metric in ["ctr", "cvr"]:
            value = format_percent.func(total / len(data) if data else 0)
        elif metric == "cost":
            value = format_currency.func(total)
        else:
            value = format_number.func(total)
        
        formatted_metrics.append({
            "name": get_metric_display_name.func(metric),
            "value": value,
            "change": None,
            "trend": "flat"
        })
    
    # 2. 生成亮点/告警
    highlights = []
    for anomaly in anomalies:
        emoji = "🟢" if anomaly.get("change_percent", 0) > 0 else "🔴"
        metric_name = get_metric_display_name.func(anomaly.get("metric", ""))
        change_str = format_change.func(anomaly.get("change_percent", 0)) if anomaly.get("change_percent") is not None else ""
        highlights.append({
            "type": "positive" if anomaly.get("change_percent", 0) > 0 else "negative",
            "text": f"{emoji} {anomaly.get('dimension_value', '')} {metric_name} 异常：{change_str}"
        })
    
    # 加入洞察
    for insight in analysis_result.get("insights", []):
        highlights.append({
            "type": "info",
            "text": f"ℹ️ {insight}"
        })
    
    # 加入建议
    for rec in analysis_result.get("recommendations", []):
        highlights.append({
            "type": "info",
            "text": f"💡 {rec}"
        })
    
    # 3. 准备表格数据
    if data:
        columns = list(data[0].keys())
        rows = [list(row.values()) for row in data]
    else:
        columns = []
        rows = []
    
    # 4. 推荐后续查询
    next_queries = []
    if rankings.get("top"):
        next_queries.append(f"查看 {rankings['top'][0]['name']} 的详细数据")
    if len(anomalies) > 0:
        next_queries.append("按创意维度下钻分析异常点")
    
    # 生成标题
    time_range = query_request.get("time_range", {})
    start = time_range.get("start_date", "")
    end = time_range.get("end_date", "")
    title = f"{start} ~ {end} 广告报表分析"
    
    return {
        "title": title,
        "time_range": {"start": start, "end": end},
        "metrics": formatted_metrics,
        "highlights": highlights,
        "data_table": {"columns": columns, "rows": rows},
        "next_queries": next_queries
    }
```

---

## Task 14：Graph 节点完善

**Files:**
- Modify: `backend/src/graph/nodes.py`
- Create: `backend/tests/test_full_graph_flow.py`

### 实现：
1. 完善 `analyst_node` - 调用 `analyst_agent`
2. 完善 `reporter_node` - 调用 `reporter_agent`
3. 编写完整流程测试

---

## Task 15：Mock 数据查询

**Files:**
- Modify: `backend/src/tools/custom_report_client.py`

在客户端中加入 Mock 模式，用于无需真实后端的测试：

```python
def get_mock_data(query_request: Dict[str, Any]) -> Dict[str, Any]:
    """生成 Mock 数据用于测试"""
    import random
    
    metrics = query_request.get("metrics", ["impressions", "clicks"])
    group_by = query_request.get("group_by", [])
    
    channels = ["渠道A", "渠道B", "渠道C", "渠道D", "渠道E"]
    data = []
    
    for i, channel in enumerate(channels):
        row = {"name": channel, "id": i + 1}
        if "impressions" in metrics:
            row["impressions"] = random.randint(10000, 100000)
        if "clicks" in metrics:
            row["clicks"] = random.randint(100, 5000)
        if "ctr" in metrics:
            row["ctr"] = random.uniform(0.01, 0.05)
        if "cost" in metrics:
            row["cost"] = random.randint(1000, 10000)
        # 加入环比变化
        row["wow_change"] = random.uniform(-0.5, 0.5)
        data.append(row)
    
    return {
        "success": True,
        "total_rows": len(data),
        "data": data,
        "execution_time_ms": 42
    }
```

修改 execute_query 方法，当 CustomReport 不可用时使用 Mock 数据。

---

## Task 16：前端结果展示组件

**Files:**
- Create: `frontend/src/components/MetricCard.tsx`
- Create: `frontend/src/components/HighlightList.tsx`
- Create: `frontend/src/components/DataTable.tsx`
- Modify: `frontend/src/components/ChatMessage.tsx`

### 实现：
1. **MetricCard** - 指标卡片，带趋势箭头
2. **HighlightList** - 亮点/告警列表
3. **DataTable** - 数据表格展示
4. 更新 ChatMessage 组件支持富文本渲染

---

## Task 17：端到端测试

**Files:**
- Create: `backend/tests/e2e/test_full_flow.py`

测试场景：
1. 基础查询："看上周的曝光点击"
2. 带维度查询："按渠道看 CTR"
3. 带过滤查询："看安卓端的花费"
4. 验证：NLU → Planner → Executor → Analyst → Reporter 完整流程

---

## Task 18：对比报告功能（补充）

**Files:**
- Modify: `backend/src/agents/reporter_agent.py`

### Step 1: 新增 format_comparison_report() 函数
```python
def format_comparison_report(
    query_intent: Dict[str, Any],
    query_requests: List[Dict[str, Any]],
    query_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """格式化对比查询报告"""
    # 双周期总指标对比
    # 变化率计算（+23.4% 格式）
    # 趋势判断（up/down/flat）
    # 维度项逐一对比表格
    # 对比专用 chart_config 生成
```

### Step 2: 新增 auto_select_chart_type_for_comparison() 函数
```python
def auto_select_chart_type_for_comparison(group_by: List[str]) -> str:
    """根据维度自动选择对比图表类型"""
    # 时间维度 → 折线图 (data_date, data_hour 等)
    # 分类维度 → 柱状图 (gender, audience 等)
```

---

## Task 19：UI 优化（补充）

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/ChatMessage.tsx`
- Modify: `frontend/src/components/DataTable.tsx`
- Modify: `frontend/src/components/ChartRenderer.tsx`

### Step 1: 页面宽度优化
```
App.tsx:
- 主容器宽度：max-w-4xl → max-w-7xl

ChatMessage.tsx:
- Assistant 消息：max-w-[80%] → max-w-full
- 用户消息：max-w-[80%] → max-w-[60%]
```

### Step 2: DataTable 分页增强
```typescript
const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

// 新增状态
const [pageSize, setPageSize] = useState(initialPageSize);
const [jumpValue, setJumpValue] = useState('');

// 新增函数
const changePageSize = (newSize: number) => {
  setPageSize(newSize);
  setCurrentPage(1);
};

const handleJump = () => {
  const page = parseInt(jumpValue, 10);
  if (!isNaN(page)) {
    goToPage(page);
  }
  setJumpValue('');
};

// 分页控制布局
flex-wrap 响应式布局
左侧：每页显示条数 + 页码信息
右侧：首页/上一页/页码/下一页/末页 + 跳转输入框
```

### Step 3: ChartRenderer 图表优化
```typescript
// 对比图表渲染
- 双折线图（时间趋势对比）
- 分组柱状图（分类维度对比）
- 双周期颜色区分（绿色/蓝色）

// 视觉优化
- 容器高度：h-[520px]
- ECharts 高度：420px
- Grid: { top: '10%', bottom: '15%' }
```

---

## Task 20：数据验证与错误处理（补充）

**Files:**
- Modify: `backend/src/agents/reporter_agent.py`
- Modify: `frontend/src/components/ChatMessage.tsx`

### 验证规则（强制要求）：
1. ✅ 查询成功但无数据时，必须返回友好的空数据提示（如"未查询到符合条件的数据"）
2. ✅ 查询失败时，必须返回具体的错误原因和解决建议
3. ✅ **禁止返回"查询完成"但没有任何数据内容**
4. ✅ Reporter Agent 必须对空数据场景做特殊处理，返回有意义的提示
5. ✅ 前端必须对 error 场景做友好展示，不展示原始错误堆栈

### Bug 修复：
```python
# 位置：backend/src/agents/reporter_agent.py:191
# 修复：TypeError: '>' not supported between instances of 'NoneType' and 'int'

# 修复前
change_percent = anomaly.get("change_percent", 0)

# 修复后
change_percent = anomaly.get("change_percent", 0) or 0
```
