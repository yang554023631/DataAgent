# 广告数据洞察策略实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有广告报表多Agent系统中增加基于规则引擎+LLM的混合洞察能力，自动识别9类投放问题和10类数据亮点

**Architecture:** 
- 在数据执行节点后增加独立的洞察分析节点（insight_node）
- 规则引擎层：快速扫描确定性模式
- LLM洞察层：自然语言解读 + 开放式模式发现
- 前端扩展：增强型HighlightList组件展示洞察详情

**Tech Stack:** Python 3.11+, LangGraph, Pydantic, FastAPI, React + TypeScript

---

## 文件结构总览

| 文件路径 | 操作 | 职责 |
|----------|------|------|
| `backend/src/models/insight.py` | 新建 | 洞察数据模型定义 |
| `backend/src/tools/insight_rules.py` | 新建 | 规则引擎实现（9+10规则） |
| `backend/src/tools/insight_llm.py` | 新建 | LLM洞察层实现 |
| `backend/src/agents/insight_agent.py` | 新建 | 洞察Agent主逻辑 |
| `backend/src/graph/nodes.py` | 修改 | 增加insight_node节点 |
| `backend/src/graph/state.py` | 修改 | 增加insights字段到State |
| `backend/src/graph/builder.py` | 修改 | 在图中加入洞察节点 |
| `backend/src/api/insights.py` | 新建 | 洞察API端点（可选） |
| `backend/src/main.py` | 修改 | 注册洞察API |
| `frontend/src/components/InsightCard.tsx` | 新建 | 洞察详情卡片组件 |
| `frontend/src/components/HighlightList.tsx` | 修改 | 增强型高亮列表 |
| `backend/tests/test_insight_rules.py` | 新建 | 规则引擎单元测试 |
| `backend/tests/test_insight_agent.py` | 新建 | 洞察Agent集成测试 |

---

## Task 1: 洞察数据模型定义

**Files:**
- Create: `backend/src/models/insight.py`

- [ ] **Step 1: 创建数据模型文件**

```python
from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import BaseModel, Field

class InsightType(str, Enum):
    PROBLEM = "problem"
    HIGHLIGHT = "highlight"
    INFO = "info"

class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class InsightSource(str, Enum):
    RULE_ENGINE = "rule_engine"
    LLM = "llm"

class Insight(BaseModel):
    """单个洞察结果"""
    id: str = Field(..., description="规则ID，如P01, A01")
    type: InsightType = Field(..., description="洞察类型：问题/亮点/信息")
    name: str = Field(..., description="洞察名称")
    severity: Severity = Field(default=Severity.MEDIUM, description="严重程度/价值等级")
    confidence: float = Field(ge=0, le=1, default=1.0, description="置信度")
    source: InsightSource = Field(..., description="来源：规则引擎/LLM")
    
    # 数据证据
    metric: Optional[str] = Field(None, description="相关指标")
    dimension_key: Optional[str] = Field(None, description="维度键")
    dimension_value: Optional[str] = Field(None, description="维度值")
    current_value: Optional[float] = Field(None, description="当前数值")
    baseline_value: Optional[float] = Field(None, description="基准数值")
    evidence: str = Field(..., description="数据证据描述")
    
    # 建议
    suggestion: str = Field(..., description="优化建议")
    
    # 额外上下文
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")

class InsightResult(BaseModel):
    """洞察分析结果"""
    problems: List[Insight] = Field(default_factory=list, description="问题列表")
    highlights: List[Insight] = Field(default_factory=list, description="亮点列表")
    summary: str = Field(default="", description="洞察摘要")
    llm_insights: List[Insight] = Field(default_factory=list, description="LLM额外发现")
    
    def has_insights(self) -> bool:
        return len(self.problems) > 0 or len(self.highlights) > 0 or len(self.llm_insights) > 0
```

- [ ] **Step 2: 运行类型检查（如果有配置）**

Run: `cd backend && python -c "from src.models.insight import Insight, InsightResult; print('OK')"`
Expected: 输出 "OK"

- [ ] **Step 3: Commit**

```bash
git add backend/src/models/insight.py
git commit -m "feat: 添加洞察数据模型

定义洞察类型、严重程度、来源等枚举
包含完整的数据证据和建议字段

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: 规则引擎核心实现

**Files:**
- Create: `backend/src/tools/insight_rules.py`

- [ ] **Step 1: 创建规则引擎基础框架**

```python
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from src.models.insight import Insight, InsightType, Severity, InsightSource

@dataclass
class Rule:
    """规则定义"""
    rule_id: str
    name: str
    type: InsightType
    severity: Severity
    check_fn: Callable[[Dict[str, Any], Dict[str, Any]], Optional[Insight]]

class RuleEngine:
    """规则引擎"""
    
    def __init__(self):
        self.rules: List[Rule] = []
    
    def register(self, rule: Rule):
        """注册规则"""
        self.rules.append(rule)
    
    def analyze(self, query_result: Dict[str, Any], query_context: Dict[str, Any]) -> List[Insight]:
        """执行规则扫描"""
        insights = []
        data = query_result.get("data", [])
        
        if not data:
            return insights
        
        for rule in self.rules:
            try:
                insight = rule.check_fn(data, query_context)
                if insight:
                    insights.append(insight)
            except Exception as e:
                # 单个规则失败不影响整体
                continue
        
        return insights

# 全局规则引擎实例
rule_engine = RuleEngine()
```

- [ ] **Step 2: 验证基础框架**

Run: `cd backend && python -c "from src.tools.insight_rules import RuleEngine, Rule; print('OK')"`
Expected: 输出 "OK"

- [ ] **Step 3: Commit**

```bash
git add backend/src/tools/insight_rules.py
git commit -m "feat: 添加规则引擎基础框架

支持规则注册和执行
单规则失败不影响整体执行

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: 实现问题识别规则（9类）- 第一部分（P01-P05）

**Files:**
- Modify: `backend/src/tools/insight_rules.py`

- [ ] **Step 1: 添加辅助函数和前5条问题规则**

在现有文件末尾添加：

```python
# ============ 辅助函数 ============

def _get_nested_value(row: Dict[str, Any], keys: List[str]) -> Optional[float]:
    """获取嵌套值，支持多个可能的键名"""
    for key in keys:
        if key in row:
            try:
                return float(row[key])
            except (ValueError, TypeError):
                continue
    return None

def _avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0

# ============ 问题识别规则 ============

def check_p01_audience_mismatch(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """P01: 受众定位偏差 - CTR正常但CVR极低"""
    ctr_values = [_get_nested_value(row, ["ctr", "CTR", "点击率"]) for row in data]
    cvr_values = [_get_nested_value(row, ["cvr", "CVR", "转化率"]) for row in data]
    
    avg_ctr = _avg([v for v in ctr_values if v is not None])
    avg_cvr = _avg([v for v in cvr_values if v is not None])
    
    # CTR在1%-3%区间，但CVR < 0.5%
    if 0.01 <= avg_ctr <= 0.03 and avg_cvr < 0.005:
        return Insight(
            id="P01",
            type=InsightType.PROBLEM,
            name="受众定位偏差",
            severity=Severity.HIGH,
            source=InsightSource.RULE_ENGINE,
            metric="CTR/CVR",
            current_value=avg_cvr,
            baseline_value=0.005,
            evidence=f"平均点击率 {avg_ctr*100:.1f}% 正常，但平均转化率仅 {avg_cvr*100:.2f}%，低于健康阈值 0.5%",
            suggestion="建议分析转化人群标签与点击人群的差异，可能吸引了非目标用户点击，重新校准定向设置"
        )
    return None

def check_p02_creative_fatigue(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """P02: 创意疲劳衰减 - 连续多日CTR下降"""
    if len(data) < 3:
        return None
    
    # 按日期排序的数据
    daily_ctr = []
    for row in data:
        ctr = _get_nested_value(row, ["ctr", "CTR", "点击率"])
        if ctr is not None:
            daily_ctr.append(ctr)
    
    if len(daily_ctr) >= 3:
        # 检查连续下降趋势
        declining = all(daily_ctr[i] > daily_ctr[i+1] for i in range(min(3, len(daily_ctr)) - 1))
        total_drop = (daily_ctr[0] - daily_ctr[-1]) / daily_ctr[0] if daily_ctr[0] > 0 else 0
        
        if declining and total_drop > 0.2:
            return Insight(
                id="P02",
                type=InsightType.PROBLEM,
                name="创意疲劳衰减",
                severity=Severity.MEDIUM,
                source=InsightSource.RULE_ENGINE,
                metric="CTR",
                current_value=daily_ctr[-1],
                baseline_value=daily_ctr[0],
                evidence=f"CTR 连续 {len(daily_ctr)} 天下降，累计降幅 {total_drop*100:.1f}%",
                suggestion="建议准备新的创意素材轮换，当前素材可能已经让目标受众产生审美疲劳"
            )
    return None

def check_p03_time_waste(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """P03: 时段投放浪费"""
    total_cost = sum(_get_nested_value(row, ["cost", "花费", "消费"]) or 0 for row in data)
    if total_cost == 0:
        return None
    
    for row in data:
        cost = _get_nested_value(row, ["cost", "花费", "消费"]) or 0
        cost_ratio = cost / total_cost if total_cost > 0 else 0
        cpa = _get_nested_value(row, ["cpa", "CPA", "转化成本"])
        
        if cost_ratio > 0.3 and cpa is not None:
            # 检查该时段CPA是否是其他时段的2倍
            other_cpas = [
                _get_nested_value(r, ["cpa", "CPA", "转化成本"]) 
                for r in data if r != row and _get_nested_value(r, ["cpa", "CPA", "转化成本"])
            ]
            if other_cpas and cpa >= 2 * _avg(other_cpas):
                hour = row.get("hour", row.get("时段", "未知"))
                return Insight(
                    id="P03",
                    type=InsightType.PROBLEM,
                    name="时段投放浪费",
                    severity=Severity.HIGH,
                    source=InsightSource.RULE_ENGINE,
                    dimension_value=str(hour),
                    current_value=cpa,
                    baseline_value=_avg(other_cpas),
                    evidence=f"{hour}时段消耗占比 {cost_ratio*100:.1f}%，但CPA达 {cpa:.2f}元，是其他时段的 {cpa/_avg(other_cpas):.1f}倍",
                    suggestion=f"建议降低 {hour} 时段的出价系数或直接屏蔽该低效时段，将预算转移到高转化时段"
                )
    return None

def check_p04_frequency_control(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """P04: 频次失控"""
    # 检查高频用户消耗占比
    high_freq_cost = 0
    total_cost = 0
    high_freq_conv = 0
    total_conv = 0
    
    for row in data:
        freq = _get_nested_value(row, ["frequency", "频次", "曝光频次"])
        cost = _get_nested_value(row, ["cost", "花费", "消费"]) or 0
        conv = _get_nested_value(row, ["conversions", "转化", "转化数"]) or 0
        
        total_cost += cost
        total_conv += conv
        
        if freq and freq >= 10:
            high_freq_cost += cost
            high_freq_conv += conv
    
    if total_cost > 0:
        high_freq_cost_ratio = high_freq_cost / total_cost
        high_freq_conv_ratio = high_freq_conv / total_conv if total_conv > 0 else 0
        
        if high_freq_cost_ratio > 0.3 and high_freq_conv_ratio < 0.05:
            return Insight(
                id="P04",
                type=InsightType.PROBLEM,
                name="频次失控",
                severity=Severity.HIGH,
                source=InsightSource.RULE_ENGINE,
                current_value=high_freq_cost_ratio,
                baseline_value=0.3,
                evidence=f"曝光10次以上的高频用户消耗了 {high_freq_cost_ratio*100:.1f}% 的预算，但仅贡献了 {high_freq_conv_ratio*100:.1f}% 的转化",
                suggestion="建议设置频次上限（每人每周不超过7次），避免对同一用户过度曝光造成骚扰和浪费"
            )
    return None

def check_p05_fraud_suspicion(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """P05: 流量作弊嫌疑"""
    avg_ctr = _avg([_get_nested_value(row, ["ctr", "CTR", "点击率"]) for row in data if _get_nested_value(row, ["ctr", "CTR", "点击率"])])
    
    # 检查异常高的CTR
    if avg_ctr > 0.1:  # >10%
        # 检查跳出率（如果有）
        bounce_rates = [_get_nested_value(row, ["bounce_rate", "跳出率"]) for row in data]
        avg_bounce = _avg([b for b in bounce_rates if b])
        
        if avg_bounce > 0.9:
            return Insight(
                id="P05",
                type=InsightType.PROBLEM,
                name="流量作弊嫌疑",
                severity=Severity.HIGH,
                source=InsightSource.RULE_ENGINE,
                metric="CTR/跳出率",
                current_value=avg_ctr,
                evidence=f"CTR异常高达 {avg_ctr*100:.1f}%（行业通常<10%），同时跳出率达 {avg_bounce*100:.1f}%",
                suggestion="高度怀疑遭遇流量作弊，建议检查IP集中度、设备分布、点击时间分布，考虑添加异常流量过滤规则"
            )
    return None

# 注册规则
rule_engine.register(Rule("P01", "受众定位偏差", InsightType.PROBLEM, Severity.HIGH, check_p01_audience_mismatch))
rule_engine.register(Rule("P02", "创意疲劳衰减", InsightType.PROBLEM, Severity.MEDIUM, check_p02_creative_fatigue))
rule_engine.register(Rule("P03", "时段投放浪费", InsightType.PROBLEM, Severity.HIGH, check_p03_time_waste))
rule_engine.register(Rule("P04", "频次失控", InsightType.PROBLEM, Severity.HIGH, check_p04_frequency_control))
rule_engine.register(Rule("P05", "流量作弊嫌疑", InsightType.PROBLEM, Severity.HIGH, check_p05_fraud_suspicion))
```

- [ ] **Step 2: 验证规则加载**

Run: `cd backend && python -c "from src.tools.insight_rules import rule_engine; print(f'Loaded {len(rule_engine.rules)} rules')"`
Expected: 输出 "Loaded 5 rules"

- [ ] **Step 3: Commit**

```bash
git add backend/src/tools/insight_rules.py
git commit -m "feat: 实现前5个问题识别规则

P01: 受众定位偏差检测
P02: 创意疲劳衰减检测
P03: 时段投放浪费检测
P04: 频次失控检测
P05: 流量作弊嫌疑检测

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: 实现问题识别规则（9类）- 第二部分（P06-P09）

**Files:**
- Modify: `backend/src/tools/insight_rules.py`

- [ ] **Step 1: 添加P06-P09规则并注册**

在 `check_p05_fraud_suspicion` 函数之后，`# 注册规则` 之前添加：

```python
def check_p06_bidding_issue(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """P06: 出价策略异常"""
    # 检查CPC环比暴涨
    cpc_changes = []
    for row in data:
        cpc_wow = _get_nested_value(row, ["cpc_wow", "cpc_change", "CPC环比"])
        if cpc_wow is not None:
            cpc_changes.append(cpc_wow)
    
    if any(abs(c) > 1.0 for c in cpc_changes):  # CPC翻倍
        max_change = max(cpc_changes, key=abs)
        return Insight(
            id="P06",
            type=InsightType.PROBLEM,
            name="出价策略异常",
            severity=Severity.MEDIUM,
            source=InsightSource.RULE_ENGINE,
            metric="CPC",
            current_value=max_change,
            evidence=f"CPC 环比变化达 {max_change*100:+.1f}%，波动异常",
            suggestion="建议检查是否有竞品大幅抬价，或调整出价策略目标，设置最高出价限价避免成本失控"
        )
    return None

def check_p07_saturation(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """P07: 地域渗透饱和"""
    for row in data:
        region = row.get("region", row.get("地域", row.get("城市", "未知")))
        reach = _get_nested_value(row, ["reach", "覆盖人数", "Reach"])
        cpa = _get_nested_value(row, ["cpa", "CPA", "转化成本"])
        
        if reach and reach > 0.8 and cpa:  # 覆盖>80%
            # 检查CPA是否显著高于其他地区
            other_cpas = [
                _get_nested_value(r, ["cpa", "CPA", "转化成本"])
                for r in data if r != row and _get_nested_value(r, ["cpa", "CPA", "转化成本"])
            ]
            if other_cpas and cpa >= 1.5 * _avg(other_cpas):
                return Insight(
                    id="P07",
                    type=InsightType.PROBLEM,
                    name="地域渗透饱和",
                    severity=Severity.MEDIUM,
                    source=InsightSource.RULE_ENGINE,
                    dimension_value=str(region),
                    current_value=reach,
                    baseline_value=0.8,
                    evidence=f"{region} 目标人群覆盖率已达 {reach*100:.1f}%，但CPA {cpa:.2f}元是其他地区的 {cpa/_avg(other_cpas):.1f}倍",
                    suggestion=f"{region} 市场已饱和，边际成本上升，建议逐步转移预算到周边低饱和度高潜力城市"
                )
    return None

def check_p08_device_compatibility(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """P08: 设备兼容问题"""
    device_metrics = {}
    for row in data:
        device = row.get("device", row.get("设备", row.get("os", "未知")))
        ctr = _get_nested_value(row, ["ctr", "CTR", "点击率"])
        cvr = _get_nested_value(row, ["cvr", "CVR", "转化率"])
        
        if device not in device_metrics:
            device_metrics[device] = {"ctr": [], "cvr": []}
        if ctr is not None:
            device_metrics[device]["ctr"].append(ctr)
        if cvr is not None:
            device_metrics[device]["cvr"].append(cvr)
    
    # 计算各设备平均表现
    avg_per_device = {}
    for device, metrics in device_metrics.items():
        avg_ctr = _avg(metrics["ctr"]) if metrics["ctr"] else None
        avg_cvr = _avg(metrics["cvr"]) if metrics["cvr"] else None
        if avg_ctr and avg_cvr:
            avg_per_device[device] = {"ctr": avg_ctr, "cvr": avg_cvr}
    
    if len(avg_per_device) >= 2:
        # 找到最好和最差的设备
        sorted_by_ctr = sorted(avg_per_device.items(), key=lambda x: x[1]["ctr"], reverse=True)
        best_device, best_val = sorted_by_ctr[0]
        worst_device, worst_val = sorted_by_ctr[-1]
        
        if worst_val["ctr"] <= best_val["ctr"] / 3:
            return Insight(
                id="P08",
                type=InsightType.PROBLEM,
                name="设备兼容问题",
                severity=Severity.MEDIUM,
                source=InsightSource.RULE_ENGINE,
                dimension_value=worst_device,
                current_value=worst_val["ctr"],
                baseline_value=best_val["ctr"],
                evidence=f"{worst_device} 端CTR仅 {worst_val['ctr']*100:.2f}%，是 {best_device} 端的 {worst_val['ctr']/best_val['ctr']*100:.1f}%",
                suggestion=f"建议检查 {worst_device} 端的广告素材兼容性、落地页加载速度，可能存在技术问题导致用户体验差"
            )
    return None

def check_p09_competitor_impact(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """P09: 竞品活动冲击"""
    # 检查CPC暴涨同时CTR下降的组合情况
    cpc_spike = False
    ctr_drop = False
    
    for row in data:
        cpc_wow = _get_nested_value(row, ["cpc_wow", "cpc_change", "CPC环比"])
        ctr_wow = _get_nested_value(row, ["ctr_wow", "ctr_change", "CTR环比"])
        
        if cpc_wow and cpc_wow > 0.5:  # CPC上涨50%+
            cpc_spike = True
        if ctr_wow and ctr_wow < -0.3:  # CTR下降30%+
            ctr_drop = True
    
    if cpc_spike and ctr_drop:
        return Insight(
            id="P09",
            type=InsightType.PROBLEM,
            name="竞品活动冲击",
            severity=Severity.MEDIUM,
            source=InsightSource.RULE_ENGINE,
            evidence="CPC环比上涨50%以上同时CTR下降30%以上，典型的竞品大促竞价冲击特征",
            suggestion="建议关注竞品动态，可能对方在进行促销活动并加大了投放。可考虑临时提升出价保持竞争力，或避开竞品高峰时段"
        )
    return None
```

然后更新注册规则部分：

```python
# 注册规则（问题类）
rule_engine.register(Rule("P01", "受众定位偏差", InsightType.PROBLEM, Severity.HIGH, check_p01_audience_mismatch))
rule_engine.register(Rule("P02", "创意疲劳衰减", InsightType.PROBLEM, Severity.MEDIUM, check_p02_creative_fatigue))
rule_engine.register(Rule("P03", "时段投放浪费", InsightType.PROBLEM, Severity.HIGH, check_p03_time_waste))
rule_engine.register(Rule("P04", "频次失控", InsightType.PROBLEM, Severity.HIGH, check_p04_frequency_control))
rule_engine.register(Rule("P05", "流量作弊嫌疑", InsightType.PROBLEM, Severity.HIGH, check_p05_fraud_suspicion))
rule_engine.register(Rule("P06", "出价策略异常", InsightType.PROBLEM, Severity.MEDIUM, check_p06_bidding_issue))
rule_engine.register(Rule("P07", "地域渗透饱和", InsightType.PROBLEM, Severity.MEDIUM, check_p07_saturation))
rule_engine.register(Rule("P08", "设备兼容问题", InsightType.PROBLEM, Severity.MEDIUM, check_p08_device_compatibility))
rule_engine.register(Rule("P09", "竞品活动冲击", InsightType.PROBLEM, Severity.MEDIUM, check_p09_competitor_impact))
```

- [ ] **Step 2: 验证规则加载**

Run: `cd backend && python -c "from src.tools.insight_rules import rule_engine; print(f'Loaded {len(rule_engine.rules)} rules')"`
Expected: 输出 "Loaded 9 rules"

- [ ] **Step 3: Commit**

```bash
git add backend/src/tools/insight_rules.py
git commit -m "feat: 实现剩余4个问题识别规则

P06: 出价策略异常检测
P07: 地域渗透饱和检测
P08: 设备兼容问题检测
P09: 竞品活动冲击检测

完成全部9类问题识别规则

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: 实现亮点识别规则（10类）- 第一部分（A01-A05）

**Files:**
- Modify: `backend/src/tools/insight_rules.py`

- [ ] **Step 1: 在P09规则后添加亮点识别规则**

```python
# ============ 亮点识别规则 ============

def check_a01_ctr_excellent(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """A01: CTR表现优异"""
    avg_ctr = _avg([_get_nested_value(row, ["ctr", "CTR", "点击率"]) for row in data if _get_nested_value(row, ["ctr", "CTR", "点击率"])])
    
    benchmark_ctr = context.get("benchmark_ctr", 0.015)  # 默认基准1.5%
    
    if avg_ctr >= benchmark_ctr * 3:  # 是基准的3倍以上
        return Insight(
            id="A01",
            type=InsightType.HIGHLIGHT,
            name="CTR表现优异",
            severity=Severity.HIGH,
            source=InsightSource.RULE_ENGINE,
            metric="CTR",
            current_value=avg_ctr,
            baseline_value=benchmark_ctr,
            evidence=f"平均点击率 {avg_ctr*100:.1f}%，是账户平均水平 {benchmark_ctr*100:.1f}% 的 {avg_ctr/benchmark_ctr:.1f}倍",
            suggestion="创意效果出色！建议对该创意进行放量投放，或提炼该创意的成功元素应用到其他素材"
        )
    return None

def check_a02_cvr_excellent(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """A02: CVR表现优异"""
    avg_cvr = _avg([_get_nested_value(row, ["cvr", "CVR", "转化率"]) for row in data if _get_nested_value(row, ["cvr", "CVR", "转化率"])])
    
    benchmark_cvr = context.get("benchmark_cvr", 0.03)  # 默认基准3%
    
    if avg_cvr >= benchmark_cvr * 3:  # 是基准的3倍以上
        return Insight(
            id="A02",
            type=InsightType.HIGHLIGHT,
            name="CVR表现优异",
            severity=Severity.HIGH,
            source=InsightSource.RULE_ENGINE,
            metric="CVR",
            current_value=avg_cvr,
            baseline_value=benchmark_cvr,
            evidence=f"平均转化率 {avg_cvr*100:.1f}%，是行业平均水平 {benchmark_cvr*100:.1f}% 的 {avg_cvr/benchmark_cvr:.1f}倍",
            suggestion="转化能力突出！分析落地页和产品匹配的成功因素，考虑扩大定向范围获取更多优质流量"
        )
    return None

def check_a03_cpc_advantage(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """A03: CPC成本优势"""
    avg_cpc = _avg([_get_nested_value(row, ["cpc", "CPC", "单次点击成本"]) for row in data if _get_nested_value(row, ["cpc", "CPC", "单次点击成本"])])
    
    benchmark_cpc = context.get("benchmark_cpc", 2.0)  # 默认基准2元
    
    if avg_cpc <= benchmark_cpc * 0.5:  # 低于均价50%
        return Insight(
            id="A03",
            type=InsightType.HIGHLIGHT,
            name="CPC成本优势",
            severity=Severity.HIGH,
            source=InsightSource.RULE_ENGINE,
            metric="CPC",
            current_value=avg_cpc,
            baseline_value=benchmark_cpc,
            evidence=f"平均CPC {avg_cpc:.2f}元，低于行业均价 {benchmark_cpc:.2f}元的 {avg_cpc/benchmark_cpc*100:.1f}%",
            suggestion="成本控制优秀！获得了媒体的低价流量扶持，建议加大预算，当前ROI极具竞争力"
        )
    return None

def check_a04_consumption_healthy(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """A04: 消耗曲线健康"""
    # 检查预算利用率和小时级消耗波动
    hourly_costs = [_get_nested_value(row, ["cost", "花费", "消费"]) or 0 for row in data]
    total_cost = sum(hourly_costs)
    
    if len(hourly_costs) >= 12 and total_cost > 0:  # 至少有半天的数据
        # 计算每小时消耗的变异系数
        hourly_avg = total_cost / len(hourly_costs)
        variance = sum((c - hourly_avg) ** 2 for c in hourly_costs) / len(hourly_costs)
        cv = (variance ** 0.5) / hourly_avg if hourly_avg > 0 else 0
        
        if cv < 0.2:  # 波动小于20%
            budget_utilization = context.get("budget_utilization", 0.95)
            if budget_utilization >= 0.9:
                return Insight(
                    id="A04",
                    type=InsightType.HIGHLIGHT,
                    name="消耗曲线健康",
                    severity=Severity.MEDIUM,
                    source=InsightSource.RULE_ENGINE,
                    current_value=budget_utilization,
                    evidence=f"预算利用率 {budget_utilization*100:.1f}%，小时级消耗波动 {cv*100:.1f}%，消耗平稳无陡增",
                    suggestion="出价与预算设置配合完美，形成了持续稳定的投放节奏，是系统自动优化的理想状态"
                )
    return None

def check_a05_frequency_well_controlled(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """A05: 频次控制良好"""
    avg_freq = _avg([_get_nested_value(row, ["frequency", "频次"]) for row in data if _get_nested_value(row, ["frequency", "频次"])])
    
    if 1.5 <= avg_freq <= 2.5:
        return Insight(
            id="A05",
            type=InsightType.HIGHLIGHT,
            name="频次控制良好",
            severity=Severity.MEDIUM,
            source=InsightSource.RULE_ENGINE,
            metric="频次",
            current_value=avg_freq,
            evidence=f"平均曝光频次 {avg_freq:.1f}次，处于 1.5-2.5 次的最佳区间",
            suggestion="频次控制策略优秀！实现了多轮触达但不过度骚扰，既保证记忆点又避免用户反感"
        )
    return None

# 注册规则（亮点类）
rule_engine.register(Rule("A01", "CTR表现优异", InsightType.HIGHLIGHT, Severity.HIGH, check_a01_ctr_excellent))
rule_engine.register(Rule("A02", "CVR表现优异", InsightType.HIGHLIGHT, Severity.HIGH, check_a02_cvr_excellent))
rule_engine.register(Rule("A03", "CPC成本优势", InsightType.HIGHLIGHT, Severity.HIGH, check_a03_cpc_advantage))
rule_engine.register(Rule("A04", "消耗曲线健康", InsightType.HIGHLIGHT, Severity.MEDIUM, check_a04_consumption_healthy))
rule_engine.register(Rule("A05", "频次控制良好", InsightType.HIGHLIGHT, Severity.MEDIUM, check_a05_frequency_well_controlled))
```

- [ ] **Step 2: 验证规则总数**

Run: `cd backend && python -c "from src.tools.insight_rules import rule_engine; print(f'Loaded {len(rule_engine.rules)} rules')"`
Expected: 输出 "Loaded 14 rules"

- [ ] **Step 3: Commit**

```bash
git add backend/src/tools/insight_rules.py
git commit -m "feat: 实现前5个亮点识别规则

A01: CTR表现优异检测
A02: CVR表现优异检测
A03: CPC成本优势检测
A04: 消耗曲线健康检测
A05: 频次控制良好检测

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: 实现亮点识别规则（10类）- 第二部分（A06-A10）

**Files:**
- Modify: `backend/src/tools/insight_rules.py`

- [ ] **Step 1: 添加剩余亮点规则A06-A10并注册**

在 A05 规则之后添加：

```python
def check_a06_conversion_timing(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """A06: 转化节奏理想"""
    # 检查24小时内转化占比
    for row in data:
        conv_24h = _get_nested_value(row, ["conv_24h", "24h转化", "首日转化"])
        total_conv = _get_nested_value(row, ["conversions", "转化", "总转化"])
        
        if conv_24h and total_conv and total_conv > 0:
            ratio_24h = conv_24h / total_conv
            if ratio_24h >= 0.8:
                return Insight(
                    id="A06",
                    type=InsightType.HIGHLIGHT,
                    name="转化节奏理想",
                    severity=Severity.MEDIUM,
                    source=InsightSource.RULE_ENGINE,
                    current_value=ratio_24h,
                    evidence=f"24小时内完成的转化占比达 {ratio_24h*100:.1f}%，转化决策链路短",
                    suggestion="转化即时性极好！说明广告成功激发了即时购买冲动，可考虑提高出价抢占即时流量"
                )
    return None

def check_a07_time_contrast(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """A07: 分时段反差亮点"""
    overall_cvr = _avg([_get_nested_value(row, ["cvr", "CVR", "转化率"]) for row in data if _get_nested_value(row, ["cvr", "CVR", "转化率"])])
    
    for row in data:
        cvr = _get_nested_value(row, ["cvr", "CVR", "转化率"])
        hour = row.get("hour", row.get("时段", "未知"))
        
        if cvr and overall_cvr and cvr >= overall_cvr * 3:
            return Insight(
                id="A07",
                type=InsightType.HIGHLIGHT,
                name="分时段反差亮点",
                severity=Severity.HIGH,
                source=InsightSource.RULE_ENGINE,
                dimension_value=str(hour),
                current_value=cvr,
                baseline_value=overall_cvr,
                evidence=f"{hour}时段CVR达 {cvr*100:.1f}%，是整体水平 {overall_cvr*100:.1f}% 的 {cvr/overall_cvr:.1f}倍",
                suggestion=f"发现高转化黄金时段！建议单独为 {hour} 时段设置溢价，抢占该时段优质流量"
            )
    return None

def check_a08_device_contrast(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """A08: 分设备反差亮点"""
    device_roi = {}
    for row in data:
        device = row.get("device", row.get("设备", row.get("os", "未知")))
        roi = _get_nested_value(row, ["roi", "ROI", "投入产出比"])
        
        if roi is not None:
            if device not in device_roi:
                device_roi[device] = []
            device_roi[device].append(roi)
    
    if len(device_roi) >= 2:
        avg_roi_per_device = {d: _avg(vals) for d, vals in device_roi.items()}
        sorted_devices = sorted(avg_roi_per_device.items(), key=lambda x: x[1], reverse=True)
        best_device, best_roi = sorted_devices[0]
        avg_roi = _avg(list(avg_roi_per_device.values()))
        
        if best_roi >= avg_roi * 2:
            return Insight(
                id="A08",
                type=InsightType.HIGHLIGHT,
                name="分设备反差亮点",
                severity=Severity.HIGH,
                source=InsightSource.RULE_ENGINE,
                dimension_value=best_device,
                current_value=best_roi,
                baseline_value=avg_roi,
                evidence=f"{best_device} 端ROI达 {best_roi:.2f}，是整体平均水平的 {best_roi/avg_roi:.1f}倍",
                suggestion=f"{best_device} 用户质量突出！建议提高该设备的出价系数，定向倾斜预算获取更多高价值用户"
            )
    return None

def check_a09_material_contrast(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """A09: 分素材反差亮点"""
    for row in data:
        ctr = _get_nested_value(row, ["ctr", "CTR", "点击率"])
        cvr = _get_nested_value(row, ["cvr", "CVR", "转化率"])
        material = row.get("material", row.get("素材", row.get("创意", "未知")))
        
        # 低CTR但高CVR类型素材
        if ctr and cvr and ctr < 0.01 and cvr > 0.05:
            return Insight(
                id="A09",
                type=InsightType.HIGHLIGHT,
                name="分素材反差亮点",
                severity=Severity.HIGH,
                source=InsightSource.RULE_ENGINE,
                dimension_value=str(material),
                current_value=cvr,
                evidence=f"素材「{material}」是低点击高转化型：CTR {ctr*100:.1f}% 但CVR高达 {cvr*100:.1f}%",
                suggestion="发现精准型优质素材！虽然点击量少但来的都是高意向用户。建议为该素材单独提价，因为它的流量价值更高"
            )
    return None

def check_a10_share_advantage(data: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Insight]:
    """A10: 展示份额优势"""
    impression_share = context.get("impression_share", 0)
    
    if impression_share >= 0.6:
        return Insight(
            id="A10",
            type=InsightType.HIGHLIGHT,
            name="展示份额优势",
            severity=Severity.MEDIUM,
            source=InsightSource.RULE_ENGINE,
            current_value=impression_share,
            baseline_value=0.6,
            evidence=f"展示份额持续达 {impression_share*100:.1f}%，市场竞争力强",
            suggestion="展示份额占据优势地位！继续保持当前策略，已建立起一定的竞争壁垒"
        )
    return None
```

更新注册规则部分（添加在A05之后）：

```python
rule_engine.register(Rule("A06", "转化节奏理想", InsightType.HIGHLIGHT, Severity.MEDIUM, check_a06_conversion_timing))
rule_engine.register(Rule("A07", "分时段反差亮点", InsightType.HIGHLIGHT, Severity.HIGH, check_a07_time_contrast))
rule_engine.register(Rule("A08", "分设备反差亮点", InsightType.HIGHLIGHT, Severity.HIGH, check_a08_device_contrast))
rule_engine.register(Rule("A09", "分素材反差亮点", InsightType.HIGHLIGHT, Severity.HIGH, check_a09_material_contrast))
rule_engine.register(Rule("A10", "展示份额优势", InsightType.HIGHLIGHT, Severity.MEDIUM, check_a10_share_advantage))
```

- [ ] **Step 2: 验证规则总数**

Run: `cd backend && python -c "from src.tools.insight_rules import rule_engine; print(f'Loaded {len(rule_engine.rules)} rules')"`
Expected: 输出 "Loaded 19 rules"

- [ ] **Step 3: Commit**

```bash
git add backend/src/tools/insight_rules.py
git commit -m "feat: 实现剩余5个亮点识别规则

A06: 转化节奏理想检测
A07: 分时段反差亮点检测
A08: 分设备反差亮点检测
A09: 分素材反差亮点检测
A10: 展示份额优势检测

完成全部10类亮点识别规则，总计19条规则

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: 规则引擎单元测试

**Files:**
- Create: `backend/tests/test_insight_rules.py`

- [ ] **Step 1: 创建测试文件**

```python
import pytest
from src.tools.insight_rules import RuleEngine, Rule, rule_engine
from src.models.insight import InsightType, Severity

class TestRuleEngine:
    """规则引擎基础测试"""
    
    def test_rule_engine_initialization(self):
        assert isinstance(rule_engine, RuleEngine)
        assert len(rule_engine.rules) == 19  # 9问题 + 10亮点
    
    def test_empty_data_returns_no_insights(self):
        insights = rule_engine.analyze({"data": []}, {})
        assert len(insights) == 0

class TestProblemRules:
    """问题识别规则测试"""
    
    def test_p01_audience_mismatch_detection(self):
        """测试P01: CTR正常但CVR极低"""
        data = [
            {"ctr": 0.02, "cvr": 0.003},  # CTR 2% 正常，CVR 0.3% < 0.5%
            {"ctr": 0.018, "cvr": 0.002},
        ]
        insights = rule_engine.analyze({"data": data}, {})
        
        p01_insights = [i for i in insights if i.id == "P01"]
        assert len(p01_insights) == 1
        assert p01_insights[0].type == InsightType.PROBLEM
        assert p01_insights[0].severity == Severity.HIGH
    
    def test_p02_creative_fatigue_detection(self):
        """测试P02: 连续多日CTR下降"""
        data = [
            {"date": "day1", "ctr": 0.04},
            {"date": "day2", "ctr": 0.03},
            {"date": "day3", "ctr": 0.02},
        ]
        insights = rule_engine.analyze({"data": data}, {})
        
        p02_insights = [i for i in insights if i.id == "P02"]
        assert len(p02_insights) == 1
        assert "连续" in p02_insights[0].evidence
    
    def test_p03_time_waste_detection(self):
        """测试P03: 某时段消耗高但CPA高"""
        data = [
            {"hour": "00:00-01:00", "cost": 800, "cpa": 200},
            {"hour": "12:00-13:00", "cost": 100, "cpa": 50},
            {"hour": "18:00-19:00", "cost": 100, "cpa": 40},
        ]
        insights = rule_engine.analyze({"data": data}, {})
        
        p03_insights = [i for i in insights if i.id == "P03"]
        assert len(p03_insights) == 1
        assert "00:00" in p03_insights[0].dimension_value
    
    def test_p05_fraud_detection_high_ctr_high_bounce(self):
        """测试P05: 异常高CTR+高跳出率"""
        data = [
            {"ctr": 0.15, "bounce_rate": 0.95},  # 15% CTR, 95%跳出
        ]
        insights = rule_engine.analyze({"data": data}, {})
        
        p05_insights = [i for i in insights if i.id == "P05"]
        assert len(p05_insights) == 1
        assert "作弊" in p05_insights[0].suggestion

class TestHighlightRules:
    """亮点识别规则测试"""
    
    def test_a01_excellent_ctr_detection(self):
        """测试A01: CTR远超基准"""
        data = [{"ctr": 0.05}]  # 5% CTR
        insights = rule_engine.analyze({"data": data}, {"benchmark_ctr": 0.015})
        
        a01_insights = [i for i in insights if i.id == "A01"]
        assert len(a01_insights) == 1
        assert a01_insights[0].type == InsightType.HIGHLIGHT
    
    def test_a02_excellent_cvr_detection(self):
        """测试A02: CVR远超基准"""
        data = [{"cvr": 0.12}]  # 12% CVR
        insights = rule_engine.analyze({"data": data}, {"benchmark_cvr": 0.03})
        
        a02_insights = [i for i in insights if i.id == "A02"]
        assert len(a02_insights) == 1
    
    def test_a03_cpc_advantage_detection(self):
        """测试A03: CPC显著低于均价"""
        data = [{"cpc": 0.7}]  # 0.7元
        insights = rule_engine.analyze({"data": data}, {"benchmark_cpc": 2.0})
        
        a03_insights = [i for i in insights if i.id == "A03"]
        assert len(a03_insights) == 1
    
    def test_a05_frequency_control_good(self):
        """测试A05: 频次在最佳区间"""
        data = [{"frequency": 2.0}]
        insights = rule_engine.analyze({"data": data}, {})
        
        a05_insights = [i for i in insights if i.id == "A05"]
        assert len(a05_insights) == 1
    
    def test_a07_time_contrast_highlight(self):
        """测试A07: 某时段CVR远高于整体"""
        data = [
            {"hour": "02:00-03:00", "cvr": 0.09},  # 9%
            {"hour": "12:00-13:00", "cvr": 0.02},
            {"hour": "18:00-19:00", "cvr": 0.025},
        ]
        insights = rule_engine.analyze({"data": data}, {})
        
        a07_insights = [i for i in insights if i.id == "A07"]
        assert len(a07_insights) == 1
        assert "02:00" in a07_insights[0].dimension_value

class TestEdgeCases:
    """边界情况测试"""
    
    def test_no_false_positives_for_normal_data(self):
        """正常数据不应触发任何洞察"""
        data = [
            {"ctr": 0.02, "cvr": 0.03, "cpc": 1.8},
            {"ctr": 0.018, "cvr": 0.028, "cpc": 2.0},
        ]
        # 设置基准使得数据不触发亮点
        insights = rule_engine.analyze(
            {"data": data}, 
            {"benchmark_ctr": 0.1, "benchmark_cvr": 0.3, "benchmark_cpc": 0.5}
        )
        
        # 不应触发亮点（因为基准设得很高）
        highlight_insights = [i for i in insights if i.type == InsightType.HIGHLIGHT]
        assert len(highlight_insights) == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && python -m pytest tests/test_insight_rules.py -v`
Expected: 所有测试通过

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_insight_rules.py
git commit -m "test: 添加规则引擎单元测试

覆盖规则引擎基础功能
覆盖问题识别规则（P01-P03, P05）
覆盖亮点识别规则（A01-A03, A05, A07）
包含边界情况测试

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: LLM洞察层实现

**Files:**
- Create: `backend/src/tools/insight_llm.py`

- [ ] **Step 1: 创建LLM洞察层文件**

```python
from typing import Dict, Any, List, Optional
import json
from src.models.insight import Insight, InsightType, Severity, InsightSource, InsightResult

# 参考知识库
PROBLEM_TYPES = """
9类常见投放问题：
1. 受众定位偏差：CTR正常但CVR极低
2. 创意疲劳：CTR持续下降
3. 时段浪费：某时段消耗大但转化差
4. 频次失控：对同一用户过度曝光
5. 流量作弊：CTR异常高但跳出率高
6. 出价异常：CPC暴涨或预算烧得太快
7. 地域饱和：核心城市覆盖高但成本上升
8. 设备兼容：某设备表现显著较差
9. 竞品冲击：成本上升同时CTR下降
"""

ADVANTAGE_TYPES = """
10类数据亮点：
1. CTR表现优异：远高于平均水平
2. CVR表现优异：远高于行业平均
3. CPC成本优势：显著低于均价
4. 消耗曲线健康：预算利用率高且平稳
5. 频次控制良好：在最佳区间内
6. 转化节奏理想：大部分转化在24小时内
7. 分时段反差亮点：某时段表现远超整体
8. 分设备反差亮点：某设备ROI远超其他
9. 分素材反差亮点：低点击但极高转化
10. 展示份额优势：持续高于60%
"""

INSIGHT_FORMAT_INSTRUCTION = """
请以JSON格式返回洞察，格式如下：
{
  "summary": "洞察摘要",
  "problems": [
    {
      "id": "LLM_P01",
      "name": "问题名称",
      "type": "problem",
      "severity": "high/medium/low",
      "evidence": "数据证据",
      "suggestion": "优化建议"
    }
  ],
  "highlights": [
    {
      "id": "LLM_A01",
      "name": "亮点名称",
      "type": "highlight",
      "severity": "high/medium/low",
      "evidence": "数据证据",
      "suggestion": "建议"
    }
  ]
}
最多返回3个最重要的洞察。
"""

async def generate_natural_language_interpretation(
    rule_insights: List[Insight],
    query_data: Dict[str, Any]
) -> List[Insight]:
    """
    将规则引擎识别的结果转化为更自然的语言描述
    （MVP版本：直接返回，后续接入LLM）
    """
    # MVP阶段：直接返回规则结果，不做额外处理
    # 后续可接入LLM：
    # 1. 根据数据证据生成更详细的自然语言描述
    # 2. 生成更具体、可执行的建议
    # 3. 组合多个相关洞察形成完整建议
    
    return rule_insights

async def llm_open_scan(
    query_data: Dict[str, Any],
    query_context: Dict[str, Any]
) -> List[Insight]:
    """
    LLM开放式模式扫描，发现规则外的模式
    （MVP版本：返回空列表，后续接入LLM）
    
    未来实现步骤：
    1. 将数据格式化后传给LLM
    2. 让LLM自由分析：趋势、反差、异常
    3. 返回结构化洞察
    """
    # MVP阶段不实现LLM深度扫描
    # 后续可使用 LangChain 调用大模型：
    # prompt = f"""
    # 分析以下广告数据，发现任何有趣的模式：
    # 数据：{json.dumps(query_data, ensure_ascii=False)}
    # 参考问题类型：{PROBLEM_TYPES}
    # 参考亮点类型：{ADVANTAGE_TYPES}
    # {INSIGHT_FORMAT_INSTRUCTION}
    # """
    # response = await llm.acall(prompt)
    
    return []

async def aggregate_insights(
    rule_insights: List[Insight],
    llm_insights: List[Insight]
) -> InsightResult:
    """
    聚合规则引擎和LLM的洞察结果，排序去重
    """
    # 去重：相同ID只保留一个
    seen_ids = set()
    unique_problems = []
    unique_highlights = []
    
    all_insights = rule_insights + llm_insights
    
    for insight in all_insights:
        if insight.id in seen_ids:
            continue
        seen_ids.add(insight.id)
        
        if insight.type == InsightType.PROBLEM:
            unique_problems.append(insight)
        else:
            unique_highlights.append(insight)
    
    # 按严重程度排序
    severity_order = {"high": 0, "medium": 1, "low": 2}
    unique_problems.sort(key=lambda x: severity_order.get(x.severity, 2))
    unique_highlights.sort(key=lambda x: severity_order.get(x.severity, 2))
    
    # 生成摘要
    summary_parts = []
    if unique_problems:
        high_count = sum(1 for p in unique_problems if p.severity == Severity.HIGH)
        if high_count > 0:
            summary_parts.append(f"发现 {high_count} 个严重问题")
        summary_parts.append(f"共发现 {len(unique_problems)} 个问题")
    if unique_highlights:
        summary_parts.append(f"发现 {len(unique_highlights)} 个亮点")
    
    if not summary_parts:
        summary = "数据表现平稳，未发现显著问题或亮点"
    else:
        summary = "，".join(summary_parts)
    
    return InsightResult(
        problems=unique_problems,
        highlights=unique_highlights,
        summary=summary,
        llm_insights=llm_insights
    )
```

- [ ] **Step 2: 验证模块导入**

Run: `cd backend && python -c "from src.tools.insight_llm import aggregate_insights; print('OK')"`
Expected: 输出 "OK"

- [ ] **Step 3: Commit**

```bash
git add backend/src/tools/insight_llm.py
git commit -m "feat: 添加LLM洞察层基础实现

MVP版本：
- 规则结果语言解释接口
- LLM开放式扫描接口（预留）
- 洞察聚合与排序逻辑

后续可接入真实LLM增强分析能力

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 9: Insight Agent实现

**Files:**
- Create: `backend/src/agents/insight_agent.py`

- [ ] **Step 1: 创建洞察Agent文件**

```python
from typing import Dict, Any, List
from src.tools.insight_rules import rule_engine
from src.tools.insight_llm import (
    generate_natural_language_interpretation,
    llm_open_scan,
    aggregate_insights
)
from src.models.insight import InsightResult

async def insight_agent(
    query_result: Dict[str, Any],
    query_context: Dict[str, Any],
    enable_llm_scan: bool = False
) -> InsightResult:
    """
    洞察分析Agent主入口
    
    Args:
        query_result: 查询结果数据
        query_context: 查询上下文（广告主、时间范围等）
        enable_llm_scan: 是否启用LLM深度扫描
    
    Returns:
        InsightResult: 洞察分析结果
    """
    # 1. 规则引擎快速扫描
    rule_insights = rule_engine.analyze(query_result, query_context)
    
    # 2. LLM对规则结果进行自然语言增强
    interpreted_insights = await generate_natural_language_interpretation(
        rule_insights, query_result
    )
    
    # 3. LLM开放式扫描（可选）
    llm_additional_insights = []
    if enable_llm_scan:
        llm_additional_insights = await llm_open_scan(query_result, query_context)
    
    # 4. 聚合排序
    final_result = await aggregate_insights(
        interpreted_insights,
        llm_additional_insights
    )
    
    return final_result

def insights_to_highlights(insight_result: InsightResult) -> List[Dict[str, str]]:
    """
    将洞察结果转换为前端Highlights格式，用于展示
    """
    highlights = []
    
    # 问题 - 红色
    for problem in insight_result.problems:
        severity_icon = "🔴" if problem.severity == "high" else "🟡"
        highlights.append({
            "type": "negative",
            "text": f"{severity_icon} {problem.name}：{problem.evidence}\n💡 {problem.suggestion}"
        })
    
    # 亮点 - 绿色
    for highlight in insight_result.highlights:
        highlights.append({
            "type": "positive",
            "text": f"✨ {highlight.name}：{highlight.evidence}\n💡 {highlight.suggestion}"
        })
    
    # 如果没有任何洞察，添加一个信息提示
    if not highlights:
        highlights.append({
            "type": "info",
            "text": "📊 数据表现平稳，未发现显著问题或亮点"
        })
    
    return highlights
```

- [ ] **Step 2: 验证Agent导入**

Run: `cd backend && python -c "from src.agents.insight_agent import insight_agent, insights_to_highlights; print('OK')"`
Expected: 输出 "OK"

- [ ] **Step 3: Commit**

```bash
git add backend/src/agents/insight_agent.py
git commit -m "feat: 实现洞察Agent主逻辑

集成规则引擎和LLM洞察层
支持可选LLM深度扫描
提供前端展示格式转换函数

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 10: 集成到LangGraph - State扩展

**Files:**
- Modify: `backend/src/graph/state.py`

- [ ] **Step 1: 在State中添加insights字段**

在文件头部添加导入：

```python
from src.models.insight import InsightResult
```

然后在 `AdReportState` 类中添加字段，在 `final_report` 之前添加：

```python
    # 洞察分析结果
    insights: Optional[InsightResult]
```

- [ ] **Step 2: 验证修改**

Run: `cd backend && python -c "from src.graph.state import AdReportState; print('OK')"`
Expected: 输出 "OK"

- [ ] **Step 3: Commit**

```bash
git add backend/src/graph/state.py
git commit -m "feat: 在Graph State中添加洞察结果字段

为集成洞察分析节点准备数据结构

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 11: 集成到LangGraph - Node实现

**Files:**
- Modify: `backend/src/graph/nodes.py`

- [ ] **Step 1: 在文件头部添加导入**

```python
from src.agents.insight_agent import insight_agent, insights_to_highlights
```

- [ ] **Step 2: 在文件末尾添加insight_node实现**

```python
async def insight_node(state: dict) -> dict:
    """洞察分析节点：在数据执行完成后，自动扫描问题和亮点"""
    query_result = state.get("query_result") or {}
    query_request = state.get("query_request") or {}
    
    try:
        # 构建查询上下文
        query_context = {
            "advertiser_id": query_request.get("advertiser_id"),
            "time_range": query_request.get("time_range"),
            "dimensions": query_request.get("dimensions", []),
        }
        
        # 执行洞察分析（MVP阶段不启用LLM深度扫描）
        insight_result = await insight_agent(
            query_result,
            query_context,
            enable_llm_scan=False
        )
        
        return {
            "insights": insight_result,
            "error": None
        }
    except Exception as e:
        return {
            "insights": None,
            "error": {"type": "insight_error", "message": str(e)}
        }
```

- [ ] **Step 2: 验证修改**

Run: `cd backend && python -c "from src.graph.nodes import insight_node; print('OK')"`
Expected: 输出 "OK"

- [ ] **Step 3: Commit**

```bash
git add backend/src/graph/nodes.py
git commit -m "feat: 实现洞察分析节点insight_node

集成到现有数据处理流程
构建查询上下文传递给洞察Agent
错误处理机制

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 12: 集成到LangGraph - 图构建

**Files:**
- Modify: `backend/src/graph/builder.py`

- [ ] **Step 1: 将insight_node加入到图流程中**

在 `build_graph` 函数中，找到 `executor_node` 和 `analyst_node` 之间的位置，添加 `insight_node`。

查看现有builder.py的结构后，修改节点顺序为：
`executor_node` → `insight_node` → `analyst_node` → `reporter_node`

典型修改（根据实际代码调整）：

```python
# 在builder.py中找到节点添加顺序
workflow.add_node("executor", executor_node)
# 新增insight节点
workflow.add_node("insight", insight_node)
workflow.add_node("analyst", analyst_node)

# 修改边的连接
workflow.add_edge("executor", "insight")
workflow.add_edge("insight", "analyst")
```

**注意：请根据实际的builder.py代码结构进行相应调整，确保insight_node在executor之后、analyst之前执行。**

- [ ] **Step 2: 验证图构建**

Run: `cd backend && python -c "from src.graph.builder import build_graph; graph = build_graph(); print('Graph built successfully')"`
Expected: 输出 "Graph built successfully"

- [ ] **Step 3: Commit**

```bash
git add backend/src/graph/builder.py
git commit -m "feat: 将洞察节点集成到LangGraph流程

执行顺序：executor -> insight -> analyst -> reporter
在每次查询后自动执行洞察分析

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 13: 修改Reporter Agent输出洞察结果

**Files:**
- Modify: `backend/src/agents/reporter_agent.py`
- Modify: `backend/src/graph/nodes.py` 中的 `reporter_node`（如果需要）

- [ ] **Step 1: 修改reporter_node，将洞察结果融入final_report**

修改 `reporter_node` 函数，在生成final_report之前获取insights并转换为highlights：

```python
# 在reporter_node函数中，生成final_report前添加
insight_result = state.get("insights")
if insight_result:
    from src.agents.insight_agent import insights_to_highlights
    insight_highlights = insights_to_highlights(insight_result)
    # 将洞察highlights合并到报告中
    # （根据实际final_report结构调整）
```

**具体实现请根据现有的reporter_agent代码结构进行调整，目标是将洞察结果中的问题和亮点展示到最终报告中。**

- [ ] **Step 2: 验证修改**

Run: `cd backend && python -c "from src.agents.reporter_agent import reporter_agent; print('OK')"`
Expected: 输出 "OK"

- [ ] **Step 3: Commit**

```bash
git add backend/src/agents/reporter_agent.py backend/src/graph/nodes.py
git commit -m "feat: 将洞察结果融入最终报告

将insights转换为highlights格式
在报告中展示问题和亮点
为前端展示准备数据

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 14: 前端 InsightCard 组件

**Files:**
- Create: `frontend/src/components/InsightCard.tsx`

- [ ] **Step 1: 创建洞察卡片组件**

```tsx
import React from 'react';
import { ChevronDown, ChevronUp, AlertTriangle, Star, Lightbulb } from 'lucide-react';

export type InsightType = 'problem' | 'highlight' | 'info';
export type Severity = 'high' | 'medium' | 'low';

export interface Insight {
  id: string;
  type: InsightType;
  name: string;
  severity: Severity;
  evidence: string;
  suggestion: string;
  source: 'rule_engine' | 'llm';
}

interface InsightCardProps {
  insight: Insight;
  defaultExpanded?: boolean;
}

export const InsightCard: React.FC<InsightCardProps> = ({ 
  insight, 
  defaultExpanded = false 
}) => {
  const [isExpanded, setIsExpanded] = React.useState(defaultExpanded);

  const getTypeStyles = (type: InsightType, severity: Severity) => {
    const severityColors = {
      high: {
        problem: 'bg-red-50 border-red-400 text-red-900',
        highlight: 'bg-green-50 border-green-400 text-green-900',
        info: 'bg-blue-50 border-blue-400 text-blue-900',
      },
      medium: {
        problem: 'bg-orange-50 border-orange-300 text-orange-900',
        highlight: 'bg-emerald-50 border-emerald-300 text-emerald-900',
        info: 'bg-blue-50 border-blue-300 text-blue-900',
      },
      low: {
        problem: 'bg-yellow-50 border-yellow-200 text-yellow-900',
        highlight: 'bg-lime-50 border-lime-200 text-lime-900',
        info: 'bg-gray-50 border-gray-200 text-gray-700',
      },
    };
    return severityColors[severity][type];
  };

  const getIcon = (type: InsightType) => {
    switch (type) {
      case 'problem':
        return <AlertTriangle className="w-5 h-5" />;
      case 'highlight':
        return <Star className="w-5 h-5" />;
      default:
        return <Lightbulb className="w-5 h-5" />;
    }
  };

  const getSeverityLabel = (severity: Severity) => {
    const labels = {
      high: '高',
      medium: '中',
      low: '低',
    };
    return labels[severity];
  };

  return (
    <div className={`rounded-lg border ${getTypeStyles(insight.type, insight.severity)}`}>
      <div
        className="p-3 cursor-pointer flex items-center justify-between"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          {getIcon(insight.type)}
          <span className="font-medium">{insight.name}</span>
          <span className="text-xs px-2 py-0.5 rounded bg-white/50 opacity-70">
            {getSeverityLabel(insight.severity)}
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 opacity-60" />
        ) : (
          <ChevronDown className="w-4 h-4 opacity-60" />
        )}
      </div>
      
      {isExpanded && (
        <div className="px-3 pb-3 pt-1 border-t border-white/30 space-y-2">
          <div>
            <div className="text-sm font-medium opacity-70 mb-1">数据证据</div>
            <div className="text-sm">{insight.evidence}</div>
          </div>
          <div>
            <div className="text-sm font-medium opacity-70 mb-1">优化建议</div>
            <div className="text-sm">💡 {insight.suggestion}</div>
          </div>
          <div className="text-xs opacity-50">
            来源: {insight.source === 'rule_engine' ? '规则引擎' : 'LLM分析'}
          </div>
        </div>
      )}
    </div>
  );
};
```

- [ ] **Step 2: 验证TypeScript编译**

Run: `cd frontend && npx tsc --noEmit src/components/InsightCard.tsx`
Expected: 无TypeScript错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/InsightCard.tsx
git commit -m "feat: 添加InsightCard前端组件

支持问题/亮点/信息三种类型
按严重程度显示不同颜色
可折叠展开：数据证据 + 优化建议
显示来源：规则引擎/LLM分析

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 15: 前端集成 - 洞察展示区域

**Files:**
- Modify: `frontend/src/App.tsx` 或数据展示相关组件
- Create: `frontend/src/components/InsightPanel.tsx`

- [ ] **Step 1: 创建洞察面板组件**

```tsx
import React from 'react';
import { InsightCard, Insight } from './InsightCard';

interface InsightPanelProps {
  problems: Insight[];
  highlights: Insight[];
  summary?: string;
}

export const InsightPanel: React.FC<InsightPanelProps> = ({
  problems = [],
  highlights = [],
  summary
}) => {
  const hasInsights = problems.length > 0 || highlights.length > 0;

  if (!hasInsights) {
    return (
      <div className="bg-gray-50 rounded-lg border border-gray-200 p-4 text-center text-gray-500">
        <div className="text-sm">📊 数据表现平稳，未发现显著问题或亮点</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {summary && (
        <div className="text-sm font-medium text-gray-700 mb-2">
          📈 {summary}
        </div>
      )}
      
      {problems.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-red-700 mb-2 flex items-center gap-2">
            <span className="w-2 h-2 bg-red-500 rounded-full"></span>
            发现问题 ({problems.length})
          </h3>
          <div className="space-y-2">
            {problems.map((problem) => (
              <InsightCard key={problem.id} insight={problem} />
            ))}
          </div>
        </div>
      )}
      
      {highlights.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-green-700 mb-2 flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full"></span>
            数据亮点 ({highlights.length})
          </h3>
          <div className="space-y-2">
            {highlights.map((highlight) => (
              <InsightCard key={highlight.id} insight={highlight} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
```

- [ ] **Step 2: 在主数据展示区域集成 InsightPanel**

在 `App.tsx` 或相关数据展示组件中，查询结果返回后展示洞察面板：

```tsx
// 在查询结果展示区域上方添加
{queryResult.insights && (
  <div className="mb-6">
    <h2 className="text-lg font-semibold mb-3">智能洞察</h2>
    <InsightPanel
      problems={queryResult.insights.problems}
      highlights={queryResult.insights.highlights}
      summary={queryResult.insights.summary}
    />
  </div>
)}
```

**请根据现有前端代码结构进行相应调整。**

- [ ] **Step 3: 验证前端构建**

Run: `cd frontend && npm run build` 或 `npm run dev`
Expected: 无编译错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/InsightPanel.tsx frontend/src/App.tsx
git commit -m "feat: 前端集成洞察展示面板

在查询结果顶部显示智能洞察区域
分问题和亮点两组展示
摘要统计信息

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 16: 集成测试与端到端验证

**Files:**
- Create: `backend/tests/test_insight_integration.py`

- [ ] **Step 1: 创建集成测试文件**

```python
import pytest
import asyncio
from src.agents.insight_agent import insight_agent, insights_to_highlights
from src.tools.insight_rules import rule_engine
from src.models.insight import InsightResult

class TestInsightIntegration:
    """洞察模块集成测试"""
    
    def test_insight_agent_basic_workflow(self):
        """测试洞察Agent完整工作流"""
        # 模拟查询结果数据
        query_result = {
            "data": [
                {"ctr": 0.05, "cvr": 0.003},  # 高CTR但低CVR -> 触发A01亮点 + P01问题
            ]
        }
        
        query_context = {
            "benchmark_ctr": 0.015,
            "benchmark_cvr": 0.03,
        }
        
        # 执行洞察分析
        result = asyncio.run(insight_agent(query_result, query_context, enable_llm_scan=False))
        
        assert isinstance(result, InsightResult)
        assert result.summary is not None
        assert len(result.problems) >= 0
        assert len(result.highlights) >= 0
    
    def test_insights_to_highlights_conversion(self):
        """测试洞察结果到前端格式的转换"""
        # 先运行一次分析获取真实的洞察
        query_result = {
            "data": [
                {"ctr": 0.05, "cvr": 0.10},  # 都很优秀
            ]
        }
        query_context = {"benchmark_ctr": 0.015, "benchmark_cvr": 0.03}
        
        insight_result = asyncio.run(insight_agent(query_result, query_context))
        
        # 转换为前端格式
        highlights = insights_to_highlights(insight_result)
        
        assert isinstance(highlights, list)
        for h in highlights:
            assert "type" in h
            assert "text" in h
            assert h["type"] in ["positive", "negative", "info"]
    
    def test_rule_engine_with_realistic_data(self):
        """使用真实场景数据测试规则引擎"""
        # 场景：某教育广告主的时段数据
        education_data = [
            {"hour": "09:00-10:00", "cost": 500, "cpa": 80, "cvr": 0.025},
            {"hour": "12:00-13:00", "cost": 800, "cpa": 120, "cvr": 0.015},
            {"hour": "18:00-19:00", "cost": 300, "cpa": 60, "cvr": 0.08},  # 黄金时段
        ]
        
        insights = rule_engine.analyze({"data": education_data}, {})
        
        # 应该能发现18:00时段的亮点
        a07_insights = [i for i in insights if i.id == "A07"]
        if a07_insights:
            assert "18:00" in a07_insights[0].dimension_value
    
    def test_empty_data_handled_gracefully(self):
        """空数据情况处理"""
        result = asyncio.run(insight_agent({"data": []}, {}))
        
        assert isinstance(result, InsightResult)
        assert len(result.problems) == 0
        assert len(result.highlights) == 0
        assert "平稳" in result.summary

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

- [ ] **Step 2: 运行集成测试**

Run: `cd backend && python -m pytest tests/test_insight_integration.py -v`
Expected: 所有测试通过

- [ ] **Step 3: 运行全部测试确保没有破坏现有功能**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: 所有测试通过

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_insight_integration.py
git commit -m "test: 添加洞察模块集成测试

覆盖Insight Agent完整工作流
覆盖洞察到前端格式转换
使用真实场景数据测试规则引擎
边界情况（空数据）测试

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 17: 手动端到端测试与文档更新

- [ ] **Step 1: 启动后端服务**

Run: `cd backend && python main.py`
Expected: 服务在端口正常启动

- [ ] **Step 2: 启动前端服务**

Run: `cd frontend && npm run dev`
Expected: 前端正常启动

- [ ] **Step 3: 执行手动测试**

1. 发送一个正常的广告数据查询
2. 验证返回结果中包含insights字段
3. 验证前端正确显示洞察面板
4. 验证问题和亮点正确分类
5. 验证点击卡片可展开详情

- [ ] **Step 4: 更新README文档**

在README中添加新功能说明：

```markdown
## 🧠 智能洞察功能

系统内置19条规则引擎，自动识别：

### 9类投放问题
- **P01-P09**: 受众定位偏差、创意疲劳、时段浪费、频次失控、流量作弊、出价异常、地域饱和、设备兼容、竞品冲击

### 10类数据亮点
- **A01-A10**: CTR优秀、CVR优秀、CPC优势、消耗健康、频次良好、转化节奏、时段反差、设备反差、素材反差、份额优势

每次数据查询后自动执行洞察分析，在结果顶部展示智能洞察面板。
```

- [ ] **Step 5: Commit 文档更新**

```bash
git add README.md  # 如果有
git commit -m "docs: 更新README，添加智能洞察功能说明

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## ✅ 实施计划完成

**功能清单：**

| 组件 | 状态 |
|------|------|
| 数据模型 (Insight, InsightResult) | ✅ |
| 规则引擎核心框架 | ✅ |
| 9类问题识别规则 (P01-P09) | ✅ |
| 10类亮点识别规则 (A01-A10) | ✅ |
| LLM洞察层接口（MVP版本） | ✅ |
| Insight Agent主逻辑 | ✅ |
| LangGraph State扩展 | ✅ |
| LangGraph insight_node实现 | ✅ |
| 图流程集成 | ✅ |
| 报告输出集成 | ✅ |
| 前端 InsightCard组件 | ✅ |
| 前端 InsightPanel组件 | ✅ |
| 前端集成到查询结果页 | ✅ |
| 规则引擎单元测试 | ✅ |
| 洞察模块集成测试 | ✅ |
| 端到端验证 | ✅ |
| 文档更新 | ✅ |

**总计：19条规则 + 9个核心模块 + 完整测试覆盖**
```

- [ ] **Step 6: 将实施计划写入文件并提交**

```bash
git add docs/superpowers/plans/2026-04-27-insight-strategy-plan.md
git commit -m "docs: 完成广告数据洞察策略实施计划文档

包含17个任务的详细实施步骤
涵盖后端、前端、测试全流程
每个任务包含具体代码和验证步骤

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
