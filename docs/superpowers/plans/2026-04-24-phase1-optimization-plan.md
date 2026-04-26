# 第一阶段优化：核心功能修复 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps using checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复5个核心功能问题：维度组合解析、时间对比查询、移除WOW_CHANGE字段、补充分月分周映射、对比图表可视化，保证系统基础体验。

**Architecture:** 
- 后端采用 TDD 方式，先写测试再实现
- 前端采用组件化方式，先改展示逻辑再加图表
- 每个任务独立提交，保证可回滚

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, React 18+, TypeScript, ECharts

**注意：** 实际代码位于 `.worktrees/ad-report-agent/` 目录下，文件名略有不同。

---

## 文件结构概览

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/tools/custom_report_client.py` | 修改 | 删除wow_change生成逻辑 |
| `backend/src/tools/term_mapper.py` | 修改 | 添加月份、周度映射 |
| `backend/src/agents/nlu_agent.py` | 修改 | 多维度识别 + 对比查询识别 |
| `backend/src/agents/planner_agent.py` | 修改 | 多维度校验 + 对比查询规划 |
| `backend/src/models/intent.py` | 修改 | 扩展对比查询字段 |
| `backend/src/graph/state.py` | 修改 | 扩展State支持多查询 |
| `backend/src/tools/executor.py` | 修改 | 支持并行执行多个查询 |
| `backend/src/agents/reporter_agent.py` | 修改 | 对比结果格式化 + 图表配置 |
| `frontend/src/components/ChartRenderer.tsx` | 修改 | 对比图表渲染 |
| `backend/tests/test_nlu_agent.py` | 已存在 | NLU测试 |
| `backend/tests/test_planner_agent.py` | 已存在 | Planner测试 |

---

## Task 1: 移除WOW_CHANGE字段（后端）

**Files:**
- Modify: `backend/src/tools/custom_report_client.py` (第258-260行)
- Test: `backend/tests/test_custom_report_client.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_custom_report_client.py` 中添加：
```python
def test_no_wow_change_in_result():
    """测试查询结果中不包含wow_change字段"""
    from src.tools.custom_report_client import parse_es_result
    
    # 模拟ES响应
    mock_response = {
        "aggregations": {
            "sum_impressions": {"value": {"value": 1000}}
        }
    }
    
    class MockQuery:
        metrics = ["impressions"]
    
    result = parse_es_result(mock_response, MockQuery(), group_by=[])
    
    assert len(result) > 0
    assert "wow_change" not in result[0], "wow_change 字段应该被移除"
```

- [ ] **Step 2: 运行测试验证失败**
```bash
cd backend
pytest tests/test_custom_report_client.py::test_no_wow_change_in_result -v
```
预期：测试失败

- [ ] **Step 3: 删除wow_change生成逻辑**

在 `custom_report_client.py` 中删除第258-260行：
```python
# 移除以下代码
# # 计算环比变化（模拟）
# if result and len(result) > 0:
#     for row in result:
#         row["wow_change"] = random.uniform(-0.3, 0.3)
```

同时移除不再使用的 `random` 导入。

- [ ] **Step 4: 运行测试验证通过**
```bash
cd backend
pytest tests/test_custom_report_client.py::test_no_wow_change_in_result -v
```
预期：测试通过

- [ ] **Step 5: Commit**
```bash
git add backend/src/tools/custom_report_client.py
git commit -m "fix: remove random wow_change field from ES result"
```

---

## Task 2: 补充分月、分周维度映射

**Files:**
- Modify: `backend/src/tools/term_mapper.py`
- Test: 手动测试

- [ ] **Step 1: 在 DIMENSION_MAPPING 中添加新映射**

```python
DIMENSION_MAPPING = {
    # ... 原有映射保持不变
    "日期": "data_date",
    "按天": "data_date",
    "每天": "data_date",
    "小时": "data_hour",
    "分时": "data_hour",
    "时段": "data_hour",
    # 新增
    "月份": "data_month",
    "按月": "data_month",
    "每月": "data_month",
    "周": "data_week",
    "按周": "data_week",
    "每周": "data_week",
    # ... 后续原有映射
}
```

- [ ] **Step 2: 验证映射生效**

```bash
cd backend
python -c "
from src.tools.term_mapper import map_dimensions
result = map_dimensions.invoke('按月统计')
print('按月:', result)
result = map_dimensions.invoke('按周展示')
print('按周:', result)
"
```
预期：`按月` 输出包含 `data_month`，`按周` 输出包含 `data_week`

- [ ] **Step 3: 运行现有测试确保不破坏原有功能**
```bash
cd backend
pytest tests/test_term_mapper.py -v
```
预期：所有测试通过

- [ ] **Step 4: Commit**
```bash
git add backend/src/tools/term_mapper.py
git commit -m "feat: add month and week dimension mapping"
```

---

## Task 3: NLU Agent - 多维度识别优化

**Files:**
- Modify: `backend/src/agents/nlu.py`
- Test: `backend/tests/agents/test_nlu.py`

- [ ] **Step 1: 写失败测试**

创建测试文件 `backend/tests/agents/test_nlu.py`：
```python
import pytest
from src.agents.nlu import parse_user_input, NLUActor

class TestNLUMultiDimension:
    def test_parse_gender_and_month_dimension(self):
        """测试识别'性别+月份'多维度组合"""
        user_input = "看广告主 电商家居_40_new 最近5个月的转化数的性别按月细分分析"
        
        result = parse_user_input(user_input)
        
        assert "gender" in result.group_by or "sex" in result.group_by
        assert "month" in result.group_by
        assert len(result.group_by) >= 2
    
    def test_parse_date_and_audience_dimension(self):
        """测试识别'分天+分受众'多维度组合"""
        user_input = "分天+分受众的点击数对比"
        
        result = parse_user_input(user_input)
        
        assert "date" in result.group_by or "day" in result.group_by
        assert "audience" in result.group_by
    
    def test_parse_multi_region_device(self):
        """测试识别'按地区、设备'多维度"""
        user_input = "按地区和设备展示曝光数据"
        
        result = parse_user_input(user_input)
        
        assert "region" in result.group_by
        assert "device" in result.group_by
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend
pytest tests/agents/test_nlu.py -v
```

预期：测试失败（因为当前NLU还不支持多维度识别）

- [ ] **Step 3: 优化NLU prompt支持多维度**

修改 `backend/src/agents/nlu.py` 中的 prompt：
```python
# 在prompt中增加多维度识别规则
NLU_PROMPT = """
... 原有内容 ...

## 多维度组合识别（重要！）
用户可能请求多个维度组合，请将所有维度都解析到 group_by 数组中，不要遗漏！

示例：
- "按性别和月份" → group_by: ["gender", "month"]
- "分天+分受众" → group_by: ["date", "audience"]
- "按地区、设备、年龄段" → group_by: ["region", "device", "age_group"]
- "性别按月细分" → group_by: ["gender", "month"]

请仔细检查用户输入中的所有维度关键词，确保全部提取。
"""
```

- [ ] **Step 4: 确保group_by字段是数组类型**

检查 `backend/src/models/intent.py` 中 QueryIntent 的定义，确保：
```python
class QueryIntent(BaseModel):
    # ... 其他字段
    group_by: List[str] = []  # 确保是List[str]类型，不是Optional[str]
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd backend
pytest tests/agents/test_nlu.py::TestNLUMultiDimension -v
```

预期：所有测试通过

- [ ] **Step 6: Commit**

```bash
git add backend/src/agents/nlu.py backend/src/models/intent.py backend/tests/agents/test_nlu.py
git commit -m "feat: support multi-dimension parsing in NLU agent"
```

---

## Task 4: Planner Agent - 多维度校验逻辑

**Files:**
- Modify: `backend/src/agents/planner.py`
- Test: `backend/tests/agents/test_planner.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/agents/test_planner.py` 中添加：
```python
import pytest
from src.agents.planner import validate_multi_dimension, PlannerActor

class TestPlannerMultiDimension:
    def test_validate_under_limit(self):
        """测试维度数量在限制内"""
        group_by = ["gender", "month"]
        valid, warnings = validate_multi_dimension(group_by)
        
        assert valid is True
        assert len(warnings) == 0
    
    def test_validate_over_limit(self):
        """测试维度数量超过限制"""
        group_by = ["gender", "month", "region", "device", "age"]  # 5个维度
        valid, warnings = validate_multi_dimension(group_by)
        
        assert valid is False
        assert len(warnings) > 0
        assert "最多支持" in warnings[0]
    
    def test_validate_date_month_redundant(self):
        """测试date和month同时出现时去重"""
        group_by = ["date", "month"]
        valid, warnings = validate_multi_dimension(group_by)
        
        assert valid is True
        assert "month" not in group_by  # month应被移除
        assert "date" in group_by
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend
pytest tests/agents/test_planner.py::TestPlannerMultiDimension -v
```

预期：测试失败

- [ ] **Step 3: 实现多维度校验函数**

修改 `backend/src/agents/planner.py`：
```python
from typing import List, Tuple

def validate_multi_dimension(group_by: List[str]) -> Tuple[bool, List[str]]:
    """
    校验多维度组合的合法性
    返回: (是否合法, 警告列表)
    """
    warnings = []
    
    # 检查维度数量限制（最多支持3个维度）
    if len(group_by) > 3:
        warnings.append(f"最多支持3个维度组合，当前有{len(group_by)}个，请减少查询维度")
        return False, warnings
    
    # 检查维度之间的兼容性 - date和month不能同时出现（冗余）
    if "date" in group_by and "month" in group_by:
        group_by.remove("month")  # 保留更细粒度的date
        warnings.append("检测到同时选择按天和按月，已自动保留按天维度")
    
    # 检查其他不兼容的维度组合
    incompatible_pairs = [
        ("hour", "day"),
        ("week", "month"),
    ]
    
    for dim1, dim2 in incompatible_pairs:
        if dim1 in group_by and dim2 in group_by:
            group_by.remove(dim2)
            warnings.append(f"检测到同时选择{dim1}和{dim2}，已自动保留{dim1}维度")
    
    return True, warnings

# 在 PlannerActor 的 plan 方法中调用此校验函数
class PlannerActor:
    def plan(self, state: AdReportState) -> AdReportState:
        intent = state.query_intent
        
        # 多维度校验
        if intent.group_by:
            valid, warnings = validate_multi_dimension(intent.group_by)
            state.query_warnings.extend(warnings)
            if not valid:
                state.error = {"type": "validation_error", "message": warnings[0]}
                return state
        
        # ... 原有逻辑
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend
pytest tests/agents/test_planner.py::TestPlannerMultiDimension -v
```

预期：所有测试通过

- [ ] **Step 5: Commit**

```bash
git add backend/src/agents/planner.py backend/tests/agents/test_planner.py
git commit -m "feat: add multi-dimension validation in planner agent"
```

---

## Task 5: NLU Agent - 对比查询识别

**Files:**
- Modify: `backend/src/models/intent.py`
- Modify: `backend/src/agents/nlu.py`
- Test: `backend/tests/agents/test_nlu.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/agents/test_nlu.py` 中添加：
```python
class TestNLUComparisonQuery:
    def test_recognize_last_two_months_comparison(self):
        """测试识别'上个月和上上个月对比'"""
        user_input = "上个月和上上个月的点击数对比"
        
        result = parse_user_input(user_input)
        
        assert result.is_comparison is True
        assert result.compare_time_range is not None
        assert result.time_range is not None
    
    def test_recognize_today_yesterday_comparison(self):
        """测试识别'今天和昨天对比'"""
        user_input = "今天和昨天的曝光数据对比"
        
        result = parse_user_input(user_input)
        
        assert result.is_comparison is True
    
    def test_recognize_week_comparison(self):
        """测试识别'本周 vs 上周'"""
        user_input = "本周 vs 上周的转化数"
        
        result = parse_user_input(user_input)
        
        assert result.is_comparison is True
    
    def test_normal_query_not_comparison(self):
        """测试普通查询不被识别为对比查询"""
        user_input = "看昨天的点击数"
        
        result = parse_user_input(user_input)
        
        assert result.is_comparison is False
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend
pytest tests/agents/test_nlu.py::TestNLUComparisonQuery -v
```

预期：测试失败

- [ ] **Step 3: 扩展 QueryIntent 模型**

修改 `backend/src/models/intent.py`：
```python
from typing import Optional

class TimeRange(BaseModel):
    start_date: str
    end_date: str
    unit: str = "day"
    label: Optional[str] = None  # 用于显示的标签，如"上个月"、"3月"

class QueryIntent(BaseModel):
    # ... 原有字段
    time_range: TimeRange
    
    # 新增对比查询支持
    is_comparison: bool = False
    compare_time_range: Optional[TimeRange] = None
    compare_type: Optional[str] = None  # "period_over_period" | "dimension_compare"
```

- [ ] **Step 4: 优化NLU prompt支持对比查询识别**

修改 `backend/src/agents/nlu.py` 中的 prompt：
```python
NLU_PROMPT = """
... 原有内容 ...

## 对比查询识别（非常重要！）
当用户输入包含"对比"、"比较"、"vs"、"和"、"与"等词汇，且涉及两个时间范围时，识别为对比查询。

对比查询识别规则：
- "A和B对比" / "A与B比较" / "对比A和B" / "A vs B" → is_comparison: true
- "上个月和上上个月" → time_range: {上个月}, compare_time_range: {上上个月}
- "今天和昨天" → time_range: {今天}, compare_time_range: {昨天}
- "本周 vs 上周" → time_range: {本周}, compare_time_range: {上周}
- "3月和4月的趋势" → time_range: {3月}, compare_time_range: {4月}

每个时间范围都要设置 label 字段，用于图表显示，例如：label: "3月"

如果用户只提到一个时间范围，不要识别为对比查询。
"""
```

- [ ] **Step 5: 在NLU解析逻辑中处理对比查询**

修改 `backend/src/agents/nlu.py` 的解析函数：
```python
def parse_user_input(user_input: str) -> QueryIntent:
    # 调用LLM解析...
    
    # 额外规则：如果解析结果包含两个时间范围，自动设置is_comparison
    if hasattr(result, 'compare_time_range') and result.compare_time_range:
        result.is_comparison = True
    
    return result
```

- [ ] **Step 6: 运行测试验证通过**

```bash
cd backend
pytest tests/agents/test_nlu.py::TestNLUComparisonQuery -v
```

预期：所有测试通过

- [ ] **Step 7: Commit**

```bash
git add backend/src/models/intent.py backend/src/agents/nlu.py backend/tests/agents/test_nlu.py
git commit -m "feat: support comparison query recognition in NLU agent"
```

---

## Task 6: State 扩展支持多查询

**Files:**
- Modify: `backend/src/graph/state.py`

- [ ] **Step 1: 扩展 AdReportState**

修改 `backend/src/graph/state.py`：
```python
from typing import List, Optional, Dict

class AdReportState(BaseModel):
    # ... 原有字段
    
    # 对比查询支持
    is_comparison: bool = False
    query_requests: List[Dict] = []  # 支持多个查询请求
    query_results: List[Dict] = []   # 支持多个查询结果
    
    # 向后兼容：保留单个query_request和query_result
    @property
    def query_request(self):
        return self.query_requests[0] if self.query_requests else None
    
    @query_request.setter
    def query_request(self, value):
        if not self.query_requests:
            self.query_requests = [value]
        else:
            self.query_requests[0] = value
    
    @property
    def query_result(self):
        return self.query_results[0] if self.query_results else None
    
    @query_result.setter
    def query_result(self, value):
        if not self.query_results:
            self.query_results = [value]
        else:
            self.query_results[0] = value
```

- [ ] **Step 2: 验证类型检查**

```bash
cd backend
python -c "from src.graph.state import AdReportState; s = AdReportState(); print('State OK')"
```

预期：输出 "State OK"

- [ ] **Step 3: Commit**

```bash
git add backend/src/graph/state.py
git commit -m "feat: extend state to support multiple queries for comparison"
```

---

## Task 7: Planner Agent - 对比查询规划

**Files:**
- Modify: `backend/src/agents/planner.py`
- Test: `backend/tests/agents/test_planner.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/agents/test_planner.py` 中添加：
```python
class TestPlannerComparisonQuery:
    def test_plan_comparison_query(self):
        """测试对比查询生成多个查询请求"""
        from src.models.intent import QueryIntent, TimeRange
        
        intent = QueryIntent(
            is_comparison=True,
            time_range=TimeRange(start_date="2024-03-01", end_date="2024-03-31", label="3月"),
            compare_time_range=TimeRange(start_date="2024-04-01", end_date="2024-04-30", label="4月"),
            metrics=["clicks"],
            group_by=["date"]
        )
        
        queries = plan_comparison_query(intent)
        
        assert len(queries) == 2
        assert queries[0].time_range == intent.time_range
        assert queries[1].time_range == intent.compare_time_range
    
    def test_plan_normal_query(self):
        """测试普通查询只生成一个查询请求"""
        from src.models.intent import QueryIntent, TimeRange
        
        intent = QueryIntent(
            is_comparison=False,
            time_range=TimeRange(start_date="2024-04-01", end_date="2024-04-30"),
            metrics=["clicks"]
        )
        
        queries = plan_comparison_query(intent)
        
        assert len(queries) == 1
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend
pytest tests/agents/test_planner.py::TestPlannerComparisonQuery -v
```

预期：测试失败

- [ ] **Step 3: 实现对比查询规划函数**

修改 `backend/src/agents/planner.py`：
```python
from typing import List
from src.models.intent import QueryIntent, QueryRequest

def build_single_query(time_range, intent: QueryIntent) -> QueryRequest:
    """构建单个查询请求"""
    return QueryRequest(
        time_range=time_range,
        metrics=intent.metrics,
        group_by=intent.group_by,
        filters=intent.filters,
        advertiser_id=intent.advertiser_id,
        period_label=time_range.label if hasattr(time_range, 'label') else None
    )

def plan_comparison_query(intent: QueryIntent) -> List[QueryRequest]:
    """
    生成对比查询的多个请求
    返回一个或多个QueryRequest
    """
    queries = []
    
    # 第一个查询：主时间范围
    queries.append(build_single_query(intent.time_range, intent))
    
    # 第二个查询：对比时间范围（如果是对比查询）
    if intent.is_comparison and intent.compare_time_range:
        queries.append(build_single_query(intent.compare_time_range, intent))
    
    return queries

# 在PlannerActor中使用
class PlannerActor:
    def plan(self, state: AdReportState) -> AdReportState:
        intent = state.query_intent
        
        # ... 多维度校验
        
        # 生成查询计划
        if intent.is_comparison:
            state.query_requests = [q.dict() for q in plan_comparison_query(intent)]
        else:
            queries = plan_comparison_query(intent)
            state.query_requests = [q.dict() for q in queries]
            # 向后兼容
            state.query_request = queries[0].dict()
        
        return state
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend
pytest tests/agents/test_planner.py::TestPlannerComparisonQuery -v
```

预期：所有测试通过

- [ ] **Step 5: Commit**

```bash
git add backend/src/agents/planner.py backend/tests/agents/test_planner.py
git commit -m "feat: add comparison query planning in planner agent"
```

---

## Task 8: Executor Node - 多查询并行执行

**Files:**
- Modify: `backend/src/agents/executor.py`
- Test: `backend/tests/agents/test_executor.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/agents/test_executor.py`：
```python
import pytest
import asyncio
from src.agents.executor import execute_multiple_queries, ExecutorActor

class TestExecutorMultipleQueries:
    def test_execute_multiple_queries(self):
        """测试并行执行多个查询"""
        from src.models.intent import QueryRequest, TimeRange
        
        queries = [
            QueryRequest(time_range=TimeRange(start_date="2024-03-01", end_date="2024-03-31"), metrics=["clicks"]),
            QueryRequest(time_range=TimeRange(start_date="2024-04-01", end_date="2024-04-30"), metrics=["clicks"]),
        ]
        
        results = asyncio.run(execute_multiple_queries(queries))
        
        assert len(results) == 2
        assert all(r is not None for r in results)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend
pytest tests/agents/test_executor.py::TestExecutorMultipleQueries -v
```

预期：测试失败

- [ ] **Step 3: 实现多查询并行执行**

修改 `backend/src/agents/executor.py`：
```python
import asyncio
from typing import List
from src.models.intent import QueryRequest, QueryResult

async def execute_single_query(query: QueryRequest) -> QueryResult:
    """执行单个查询"""
    # 原有执行逻辑...
    return QueryResult(...)

async def execute_multiple_queries(queries: List[QueryRequest]) -> List[QueryResult]:
    """并行执行多个查询"""
    tasks = [execute_single_query(q) for q in queries]
    results = await asyncio.gather(*tasks)
    return results

# 在ExecutorActor中使用
class ExecutorActor:
    async def execute(self, state: AdReportState) -> AdReportState:
        if state.is_comparison and len(state.query_requests) > 1:
            # 对比查询：并行执行多个
            query_objects = [QueryRequest(**q) for q in state.query_requests]
            results = await execute_multiple_queries(query_objects)
            state.query_results = [r.dict() for r in results]
        else:
            # 普通查询：执行单个
            query = QueryRequest(**state.query_requests[0])
            result = await execute_single_query(query)
            state.query_results = [result.dict()]
            state.query_result = result.dict()
        
        return state
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend
pytest tests/agents/test_executor.py::TestExecutorMultipleQueries -v
```

预期：所有测试通过

- [ ] **Step 5: Commit**

```bash
git add backend/src/agents/executor.py backend/tests/agents/test_executor.py
git commit -m "feat: support parallel execution of multiple queries"
```

---

## Task 9: Reporter Agent - 对比结果格式化与图表配置

**Files:**
- Modify: `backend/src/agents/reporter.py`
- Test: `backend/tests/agents/test_reporter.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/agents/test_reporter.py`：
```python
import pytest
from src.agents.reporter import format_comparison_report, ReporterActor

class TestReporterComparisonReport:
    def test_format_comparison_report(self):
        """测试格式化对比报告"""
        from src.models.intent import QueryResult
        
        results = [
            QueryResult(
                period="3月",
                total=1000,
                data=[{"date": "2024-03-01", "clicks": 100}, {"date": "2024-03-02", "clicks": 150}]
            ),
            QueryResult(
                period="4月",
                total=1200,
                data=[{"date": "2024-04-01", "clicks": 120}, {"date": "2024-04-02", "clicks": 180}]
            ),
        ]
        
        report = format_comparison_report(results)
        
        assert report.is_comparison is True
        assert len(report.key_metrics) >= 3  # 至少有3个：3月、4月、变化
        assert report.chart_config is not None
        assert report.chart_config["type"] == "line"
        assert len(report.chart_config["series"]) == 2
    
    def test_chart_config_has_colors(self):
        """测试图表配置包含颜色"""
        from src.models.intent import QueryResult
        
        results = [
            QueryResult(period="3月", total=1000, data=[]),
            QueryResult(period="4月", total=1200, data=[]),
        ]
        
        report = format_comparison_report(results)
        
        series = report.chart_config["series"]
        assert all("color" in s for s in series)
        assert all("name" in s for s in series)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend
pytest tests/agents/test_reporter.py::TestReporterComparisonReport -v
```

预期：测试失败

- [ ] **Step 3: 扩展FinalReport模型支持图表配置**

先在 `backend/src/models/intent.py` 中添加：
```python
class ChartSeriesConfig(BaseModel):
    name: str
    dataKey: str
    color: str

class ChartConfig(BaseModel):
    type: str  # "line" | "bar" | "pie"
    x_axis: str
    y_axis: str
    series: List[ChartSeriesConfig]

class FinalReport(BaseModel):
    # ... 原有字段
    is_comparison: bool = False
    comparison_data: Optional[Dict] = None
    chart_config: Optional[ChartConfig] = None
```

- [ ] **Step 4: 实现对比报告格式化函数**

修改 `backend/src/agents/reporter.py`：
```python
from typing import List
from src.models.intent import QueryResult, FinalReport, ChartConfig, ChartSeriesConfig

def auto_select_chart_type(group_by: List[str]) -> str:
    """根据维度自动选择图表类型"""
    time_dimensions = {"date", "day", "hour", "week", "month"}
    if any(dim in group_by for dim in time_dimensions):
        return "line"  # 时间维度对比用折线图
    return "bar"  # 分类维度对比用柱状图

def format_comparison_report(results: List[QueryResult]) -> FinalReport:
    """将多个查询结果格式化为对比报告"""
    result1, result2 = results
    
    # 计算变化率
    change_rate = (result2.total - result1.total) / result1.total * 100 if result1.total != 0 else 0
    
    # 自动选择图表类型
    chart_type = auto_select_chart_type(result1.group_by or [])
    
    # 构建图表配置
    colors = ["#10b981", "#3b82f6"]  # 绿色、蓝色
    period_names = [
        getattr(result1, 'period_label', result1.period) or "周期1",
        getattr(result2, 'period_label', result2.period) or "周期2"
    ]
    
    chart_config = ChartConfig(
        type=chart_type,
        x_axis="date" if chart_type == "line" else "category",
        y_axis=result1.metrics[0] if result1.metrics else "value",
        series=[
            ChartSeriesConfig(name=period_names[0], dataKey="period1", color=colors[0]),
            ChartSeriesConfig(name=period_names[1], dataKey="period2", color=colors[1]),
        ]
    )
    
    return FinalReport(
        title=f"{period_names[0]} vs {period_names[1]} 对比",
        is_comparison=True,
        key_metrics=[
            {"name": f"{period_names[0]}", "value": f"{result1.total:,}"},
            {"name": f"{period_names[1]}", "value": f"{result2.total:,}"},
            {"name": "变化", "value": f"{change_rate:+.1f}%"},
        ],
        comparison_data={
            "period1": {"name": period_names[0], "color": colors[0], "data": result1.data},
            "period2": {"name": period_names[1], "color": colors[1], "data": result2.data},
        },
        chart_config=chart_config,
    )

# 在ReporterActor中使用
class ReporterActor:
    def report(self, state: AdReportState) -> AdReportState:
        if state.is_comparison and len(state.query_results) > 1:
            # 对比查询
            results = [QueryResult(**r) for r in state.query_results]
            report = format_comparison_report(results)
        else:
            # 普通查询（原有逻辑）
            ...
        
        state.final_report = report.dict()
        return state
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd backend
pytest tests/agents/test_reporter.py::TestReporterComparisonReport -v
```

预期：所有测试通过

- [ ] **Step 6: Commit**

```bash
git add backend/src/models/intent.py backend/src/agents/reporter.py backend/tests/agents/test_reporter.py
git commit -m "feat: add comparison report formatting with chart config"
```

---

## Task 10: 前端 ChartRenderer - 对比图表渲染

**Files:**
- Modify: `frontend/src/components/ChartRenderer.tsx`

- [ ] **Step 1: 扩展图表类型定义**

在 `ChartRenderer.tsx` 顶部添加类型定义：
```typescript
interface ChartSeriesConfig {
  name: string;
  dataKey: string;
  color: string;
}

interface ChartConfig {
  type: 'line' | 'bar' | 'pie';
  x_axis: string;
  y_axis: string;
  series: ChartSeriesConfig[];
}

interface ComparisonData {
  period1: { name: string; color: string; data: any[] };
  period2: { name: string; color: string; data: any[] };
}
```

- [ ] **Step 2: 实现对比折线图渲染**

添加双折线图组件：
```typescript
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const renderComparisonLineChart = (config: ChartConfig, comparisonData: ComparisonData) => {
  // 合并两个周期的数据用于双折线展示
  const { period1, period2 } = comparisonData;
  
  // 按日期合并数据
  const mergedData = period1.data.map((item1, index) => ({
    ...item1,
    period1: item1[config.y_axis] || item1.value,
    period2: period2.data[index]?.[config.y_axis] || period2.data[index]?.value || 0,
    date: item1.date || item1[config.x_axis],
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={mergedData}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
        <XAxis dataKey={config.x_axis} />
        <YAxis />
        <Tooltip />
        <Legend />
        {config.series.map((s, i) => (
          <Line
            key={i}
            type="monotone"
            dataKey={s.dataKey}
            name={s.name}
            stroke={s.color}
            strokeWidth={2}
            dot={{ r: 4 }}
            activeDot={{ r: 6 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
};
```

- [ ] **Step 3: 实现对比柱状图渲染**

```typescript
const renderComparisonBarChart = (config: ChartConfig, comparisonData: ComparisonData) => {
  const { period1, period2 } = comparisonData;
  
  // 合并数据用于分组柱状图
  const mergedData = period1.data.map((item1, index) => ({
    name: item1[config.x_axis] || item1.category || `Item ${index}`,
    period1: item1[config.y_axis] || item1.value,
    period2: period2.data[index]?.[config.y_axis] || period2.data[index]?.value || 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={mergedData}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
        <XAxis dataKey="name" />
        <YAxis />
        <Tooltip />
        <Legend />
        {config.series.map((s, i) => (
          <Bar
            key={i}
            dataKey={s.dataKey}
            name={s.name}
            fill={s.color}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
};
```

- [ ] **Step 4: 主渲染函数中添加对比图表分支**

修改主渲染逻辑：
```typescript
const ChartRenderer = ({ report }: { report: any }) => {
  // 对比查询渲染
  if (report.is_comparison && report.comparison_data && report.chart_config) {
    if (report.chart_config.type === 'line') {
      return renderComparisonLineChart(report.chart_config, report.comparison_data);
    }
    if (report.chart_config.type === 'bar') {
      return renderComparisonBarChart(report.chart_config, report.comparison_data);
    }
  }
  
  // 原有普通图表渲染逻辑...
};
```

- [ ] **Step 5: 验证前端编译通过**

```bash
cd frontend
npm run build
```

预期：编译成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ChartRenderer.tsx
git commit -m "feat: add comparison chart rendering (dual line & grouped bar)"
```

---

## Task 11: 集成测试与端到端验证

**Files:**
- 创建测试用例文档

- [ ] **Step 1: 运行所有单元测试**

```bash
cd backend
pytest tests/agents/ -v
```

预期：所有测试通过

- [ ] **Step 2: 手动测试多维度查询**

测试用例：
```
"看广告主 电商家居_40_new 最近5个月的转化数的性别按月细分分析"
```

预期：group_by 包含 ["gender", "month"]

- [ ] **Step 3: 手动测试对比查询**

测试用例：
```
"上个月和上上个月的点击数对比"
```

预期：
- is_comparison = true
- 有两个query_results
- 前端显示双折线对比图

- [ ] **Step 4: 手动测试WOW_CHANGE已移除**

查看任意数据详情页，确认不显示 WOW_CHANGE 字段。

- [ ] **Step 5: 提交最终测试验证**

```bash
git add docs/superpowers/tests/
git commit -m "test: add integration test cases for phase 1 optimization"
```

---

## 完成清单

- [ ] Task 1: 移除WOW_CHANGE字段（后端）
- [ ] Task 2: 补充分月、分周维度映射
- [ ] Task 3: NLU Agent - 多维度识别优化
- [ ] Task 4: Planner Agent - 多维度校验逻辑
- [ ] Task 5: NLU Agent - 对比查询识别
- [ ] Task 6: State 扩展支持多查询
- [ ] Task 7: Planner Agent - 对比查询规划
- [ ] Task 8: Executor Node - 多查询并行执行
- [ ] Task 9: Reporter Agent - 对比结果格式化与图表配置
- [ ] Task 10: 前端 ChartRenderer - 对比图表渲染
- [ ] Task 11: 集成测试与端到端验证

---

## 风险提示

1. **State扩展兼容性** - Task 5中添加了property setter来保证向后兼容，但如果有地方直接访问 `state.query_request` 的字典操作，可能需要调整
2. **异步执行** - Executor改为async后，需要确保LangGraph的node调用支持async
3. **前端数据格式** - 确保后端输出的 comparison_data 格式与前端期望一致
