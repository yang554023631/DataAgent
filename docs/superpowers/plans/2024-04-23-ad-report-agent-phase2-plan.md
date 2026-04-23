# 广告报表多Agent系统 第二阶段实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** 实现 NLU Agent + HITL Node + Planner Agent，完成自然语言到查询请求的完整转换

**Architecture:** LangGraph 3节点串联 + Tool 函数 + FastAPI 接口

---

## Task 7: NLU Agent 实现

**Files:**
- Create: `backend/src/tools/time_parser.py`
- Create: `backend/src/tools/term_mapper.py`
- Create: `backend/src/tools/filter_parser.py`
- Create: `backend/src/agents/nlu_agent.py`
- Create: `backend/src/prompts/nlu_prompt.py`
- Modify: `backend/src/graph/nodes.py` - Update nlu_node
- Create: `backend/tests/test_time_parser.py`
- Create: `backend/tests/test_term_mapper.py`
- Create: `backend/tests/test_nlu_agent.py`

---

**Step 1: 创建时间解析 Tool**

```python
from datetime import datetime, timedelta, date
from pydantic import BaseModel
from langchain_core.tools import tool

class TimeRange(BaseModel):
    start_date: str
    end_date: str
    unit: str  # day, week, month

@tool
def parse_time_range(text: str) -> TimeRange:
    """
    解析自然语言时间范围
    
    支持:
    - 今天、昨天
    - 本周、上周、上上周
    - 本月、上个月
    - 近N天、近N周、近N月
    - 2024年4月、4月15日到4月21日
    - 上周、上周同期
    """
    today = date.today()
    
    # 今天
    if "今天" in text:
        return TimeRange(
            start_date=str(today),
            end_date=str(today),
            unit="day"
        )
    
    # 昨天
    if "昨天" in text:
        yesterday = today - timedelta(days=1)
        return TimeRange(
            start_date=str(yesterday),
            end_date=str(yesterday),
            unit="day"
        )
    
    # 上周（周一到周日）
    if "上周" in text:
        # 找到上周周一
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        last_sunday = last_monday + timedelta(days=6)
        return TimeRange(
            start_date=str(last_monday),
            end_date=str(last_sunday),
            unit="day"
        )
    
    # 近7天（默认）
    if "近7天" in text or "最近7天" in text or "过去一周" in text:
        start = today - timedelta(days=6)
        return TimeRange(
            start_date=str(start),
            end_date=str(today),
            unit="day"
        )
    
    # 默认：近7天
    start = today - timedelta(days=6)
    return TimeRange(
        start_date=str(start),
        end_date=str(today),
        unit="day"
    )
```

**Step 2: 创建术语映射 Tool**

```python
from typing import List, Dict
from langchain_core.tools import tool

METRIC_MAPPING = {
    "曝光": "impressions",
    "展示": "impressions",
    "展示量": "impressions",
    "点击": "clicks",
    "点击量": "clicks",
    "花费": "cost",
    "消耗": "cost",
    "点击率": "ctr",
    "CTR": "ctr",
    "转化率": "cvr",
    "CVR": "cvr",
    "投产比": "roi",
    "ROI": "roi",
}

DIMENSION_MAPPING = {
    "日期": "data_date",
    "渠道": "campaign_id",
    "广告组": "adgroup_id",
    "创意": "creative_id",
    "性别": "audience_gender",
    "年龄段": "audience_age",
    "年龄": "audience_age",
    "系统": "audience_os",
    "平台": "audience_os",
    "OS": "audience_os",
    "兴趣": "audience_interest",
}

FILTER_VALUE_MAPPING = {
    "安卓": {"field": "audience_os", "value": 2},
    "Android": {"field": "audience_os", "value": 2},
    "苹果": {"field": "audience_os", "value": 1},
    "iOS": {"field": "audience_os", "value": 1},
    "男性": {"field": "audience_gender", "value": 1},
    "女性": {"field": "audience_gender", "value": 2},
}

@tool
def map_metrics(text: str) -> List[str]:
    """将自然语言指标名称映射为标准指标名"""
    result = []
    for term, standard in METRIC_MAPPING.items():
        if term in text and standard not in result:
            result.append(standard)
    return result if result else ["impressions", "clicks"]

@tool
def map_dimensions(text: str) -> List[str]:
    """将自然语言维度名称映射为标准维度名"""
    result = []
    for term, standard in DIMENSION_MAPPING.items():
        if term in text and standard not in result:
            result.append(standard)
    return result
```

**Step 3: 创建过滤条件解析 Tool**

```python
from typing import List, Dict, Any
from langchain_core.tools import tool

@tool
def parse_filters(text: str) -> List[Dict[str, Any]]:
    """
    解析自然语言中的过滤条件
    
    示例:
    "安卓端" → [{"field": "audience_os", "op": "=", "value": 2}]
    "非iOS" → [{"field": "audience_os", "op": "!=", "value": 1}]
    "男性" → [{"field": "audience_gender", "op": "=", "value": 1}]
    """
    filters = []
    
    for term, mapping in FILTER_VALUE_MAPPING.items():
        if term in text:
            filters.append({
                "field": mapping["field"],
                "op": "=",
                "value": mapping["value"]
            })
    
    return filters
```

**Step 4: 创建 NLU Prompt 模板**

```python
NLU_PROMPT = """
你是广告报表意图理解专家。

你的任务是分析用户的自然语言输入，转换成结构化的查询意图。

已知指标映射：
{metric_mapping}

已知维度映射：
{dimension_mapping}

上下文会话历史：
{conversation_history}

当前查询：
{user_input}

请输出 JSON 格式：
{{
    "time_range": {{
        "start_date": "YYYY-MM-DD",
        "end_date": "YYYY-MM-DD",
        "unit": "day"
    }},
    "metrics": ["指标1"],
    "group_by": ["维度1"],
    "filters": [],
    "is_incremental": false,
    "intent_type": "query",
    "ambiguity": {{
        "has_ambiguity": false,
        "type": null,
        "reason": null,
        "options": []
    }}
}}
"""
```

**Step 5: 创建 NLU Agent 实现**

```python
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.config.settings import settings
from src.tools.time_parser import parse_time_range
from src.tools.term_mapper import map_metrics, map_dimensions
from src.tools.filter_parser import parse_filters
from src.prompts.nlu_prompt import NLU_PROMPT

async def nlu_agent(user_input: str, conversation_history: list = None) -> Dict[str, Any]:
    """
    意图理解 Agent
    
    Args:
        user_input: 用户自然语言输入
        conversation_history: 会话历史
    
    Returns:
        QueryIntent 结构化数据
    """
    # Step 1: 先用工具解析可确定的部分
    time_range = parse_time_range.invoke(user_input)
    metrics = map_metrics.invoke(user_input)
    group_by = map_dimensions.invoke(user_input)
    filters = parse_filters.invoke(user_input)
    
    # Step 2: 用 LLM 做更复杂的理解
    llm = ChatOpenAI(
        model=settings.DEFAULT_MODEL,
        temperature=0,
        api_key=settings.OPENAI_API_KEY
    )
    
    prompt = ChatPromptTemplate.from_template(NLU_PROMPT)
    chain = prompt | llm | JsonOutputParser()
    
    result = await chain.ainvoke({
        "metric_mapping": str(METRIC_MAPPING),
        "dimension_mapping": str(DIMENSION_MAPPING),
        "conversation_history": str(conversation_history or []),
        "user_input": user_input
    })
    
    # Step 3: 合并工具结果和 LLM 结果
    result.setdefault("metrics", metrics)
    result.setdefault("group_by", group_by)
    result.setdefault("filters", filters)
    result.setdefault("time_range", time_range.model_dump())
    
    return result
```

**Step 6: 更新 graph/nodes.py 中的 nlu_node**

```python
from src.agents.nlu_agent import nlu_agent

async def nlu_node(state: dict) -> dict:
    """意图理解节点"""
    user_input = state.get("user_input", "")
    conversation_history = state.get("conversation_history", [])
    
    try:
        query_intent = await nlu_agent(user_input, conversation_history)
        
        return {
            "query_intent": query_intent,
            "ambiguity": query_intent.get("ambiguity"),
            "error": None
        }
    except Exception as e:
        return {
            "query_intent": None,
            "ambiguity": None,
            "error": {"type": "nlu_error", "message": str(e)}
        }
```

**Step 7: 写单元测试**

```python
import pytest
from src.tools.time_parser import parse_time_range

def test_parse_time_range_yesterday():
    result = parse_time_range.invoke("看昨天的数据")
    assert result.unit == "day"

def test_parse_time_range_last_week():
    result = parse_time_range.invoke("上周的数据")
    assert result.unit == "day"

def test_map_metrics_basic():
    from src.tools.term_mapper import map_metrics
    result = map_metrics.invoke("看曝光和点击率")
    assert "impressions" in result
    assert "ctr" in result
```

**Step 8: 运行测试 & Commit**

---

## Task 8: HITL 节点实现

**Files:**
- Create: `backend/src/tools/clarification_generator.py`
- Create: `backend/src/agents/hitl_node.py`
- Modify: `backend/src/graph/nodes.py` - Update hitl_node
- Create: `backend/tests/test_hitl_node.py`

---

**Step 1: 创建澄清选项生成 Tool**

```python
from typing import List, Dict, Any
from pydantic import BaseModel
from langchain_core.tools import tool

class ClarificationQuestion(BaseModel):
    question: str
    options: List[Dict[str, str]]
    allow_custom_input: bool = False

@tool
def generate_clarification_options(
    ambiguity_type: str,
    context: Dict[str, Any]
) -> ClarificationQuestion:
    """
    根据歧义类型生成澄清问题和选项
    
    ambiguity_type: metric, dimension, time, advertiser, query_too_large, empty_data
    """
    
    if ambiguity_type == "metric":
        return ClarificationQuestion(
            question="您想查看哪些指标？",
            options=[
                {"value": "impressions,clicks", "label": "曝光和点击"},
                {"value": "ctr,cvr", "label": "CTR和CVR"},
                {"value": "cost,roi", "label": "花费和ROI"}
            ],
            allow_custom_input=True
        )
    
    if ambiguity_type == "time":
        return ClarificationQuestion(
            question="您想查询哪个时间范围的数据？",
            options=[
                {"value": "today", "label": "今天"},
                {"value": "yesterday", "label": "昨天"},
                {"value": "last_7_days", "label": "最近7天"},
                {"value": "last_week", "label": "上周"}
            ],
            allow_custom_input=True
        )
    
    if ambiguity_type == "query_too_large":
        estimated_rows = context.get("estimated_rows", 1000)
        return ClarificationQuestion(
            question=f"这个查询预计返回约 {estimated_rows} 条数据，可能耗时较长，是否继续？",
            options=[
                {"value": "confirm", "label": "确认查询"},
                {"value": "reduce_to_month", "label": "改成按月汇总"},
                {"value": "narrow_time", "label": "缩小时间范围"}
            ],
            allow_custom_input=False
        )
    
    # 默认
    return ClarificationQuestion(
        question="请选择以下选项：",
        options=context.get("options", []),
        allow_custom_input=True
    )
```

**Step 2: 更新 graph/builder.py 配置 interrupt**

```python
# 在 build_graph 函数中
graph.add_node("hitl", hitl_node)

# 关键：配置在 hitl 节点之前暂停
return graph.compile(interrupt_before=["hitl"])
```

**Step 3: HITL 节点实现**

```python
from src.tools.clarification_generator import generate_clarification_options

async def hitl_node(state: dict) -> dict:
    """
    人机协调节点
    
    注意：此节点执行前 Graph 已经 interrupt 等待用户输入，
    用户反馈已经通过 API 写入 user_feedback
    """
    user_feedback = state.get("user_feedback")
    clarification_count = state.get("clarification_count", 0) + 1
    
    return {
        "user_feedback": user_feedback,
        "clarification_count": clarification_count
    }
```

**Step 4: 写测试**

```python
import pytest
from src.tools.clarification_generator import generate_clarification_options

def test_generate_clarification_metric():
    result = generate_clarification_options.invoke(
        ambiguity_type="metric",
        context={}
    )
    assert "指标" in result.question
    assert len(result.options) == 3
```

---

## Task 9: Planner Agent 实现

**Files:**
- Create: `backend/src/tools/business_rules.py`
- Create: `backend/src/tools/chart_selector.py`
- Create: `backend/src/tools/query_validator.py`
- Create: `backend/src/agents/planner_agent.py`
- Create: `backend/src/prompts/planner_prompt.py`
- Modify: `backend/src/graph/nodes.py` - Update planner_node
- Create: `backend/tests/test_business_rules.py`
- Create: `backend/tests/test_planner_agent.py`

---

**Step 1: 业务规则 Tool**

```python
from langchain_core.tools import tool
from typing import Dict, Any, List

@tool
def apply_business_rules(intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    应用广告报表查询业务规则
    
    1. 如果分组维度包含 audience_* 字段，必须切换到 audience 索引
    2. 切换索引后必须添加对应的 audience_type 过滤
    """
    result = intent.copy()
    group_by = intent.get("group_by", [])
    filters = intent.get("filters", [])
    
    has_audience_dim = any(d.startswith("audience_") for d in group_by)
    
    if has_audience_dim:
        result["index_type"] = "audience"
        
        # 自动添加 audience_type 过滤
        if "audience_gender" in group_by:
            filters.append({"field": "audience_type", "op": "=", "value": 1})
        if "audience_age" in group_by:
            filters.append({"field": "audience_type", "op": "=", "value": 2})
        if "audience_os" in group_by:
            filters.append({"field": "audience_type", "op": "=", "value": 3})
        
        result["filters"] = filters
    else:
        result["index_type"] = "general"
    
    return result
```

**Step 2: 图表选择 Tool**

```python
from langchain_core.tools import tool
from typing import Dict, Any

@tool
def auto_select_chart_type(metrics: list, dimensions: list) -> Dict[str, Any]:
    """
    根据指标和维度自动选择合适的图表类型
    
    规则:
    - 有时间维度 → line 折线图
    - 分类维度 < 10 → bar 柱状图
    - 分类维度 < 5 + 看占比场景 → pie 饼图
    - 其他 → table 表格
    """
    has_time = "data_date" in dimensions or "data_week" in dimensions
    
    if has_time:
        return {
            "type": "line",
            "x_axis": "data_date",
            "y_axis": metrics
        }
    
    dim_count = len(dimensions)
    
    if dim_count == 0 or dim_count >= 10:
        return {"type": "table"}
    
    if dim_count < 5:
        return {
            "type": "bar",
            "x_axis": dimensions[0],
            "y_axis": metrics
        }
    
    return {"type": "table"}
```

**Step 3: 参数校验 Tool**

```python
from langchain_core.tools import tool
from typing import Dict, Any, List

@tool
def validate_and_warn(query_request: Dict[str, Any]) -> List[str]:
    """
    校验查询参数并返回警告列表
    
    检查项:
    - 维度数量限制（最多3个）
    - 时间范围大小限制（最多90天）
    - 预计数据量警告
    """
    warnings = []
    
    # 维度数量检查
    group_by = query_request.get("group_by", [])
    if len(group_by) > 3:
        warnings.append("分组维度超过3个，图表可能难以阅读")
    
    # 时间范围检查
    time_range = query_request.get("time_range", {})
    if "start_date" in time_range and "end_date" in time_range:
        from datetime import datetime
        start = datetime.fromisoformat(time_range["start_date"])
        end = datetime.fromisoformat(time_range["end_date"])
        days = (end - start).days
        
        if days > 90:
            warnings.append("时间范围超过90天，查询可能较慢 need_confirm")
    
    return warnings
```

**Step 4: Planner Prompt**

```python
PLANNER_PROMPT = """
你是广告报表查询规划专家。

请把查询意图转换成合法的 QueryRequest。

查询意图：
{query_intent}

用户澄清反馈：
{user_feedback}

请输出：
{{
    "query_request": {{
        "index_type": "general",
        "time_range": {},
        "metrics": [],
        "group_by": [],
        "filters": [],
        "chart_config": {}
    }},
    "query_warnings": []
}}
"""
```

**Step 5: Planner Agent 实现 + 更新节点 + 测试**

---

## Task 10: FastAPI 会话接口

**Files:**
- Create: `backend/src/api/sessions.py`
- Create: `backend/src/services/session_service.py`
- Create: `backend/tests/integration/test_api.py`

**核心接口：**
- `POST /api/sessions` - 创建会话
- `POST /api/sessions/{session_id}/messages` - 发送消息
- `POST /api/sessions/{session_id}/clarification` - 提交澄清

---

## Task 11: 前端对话界面

**Files:**
- Create: `frontend/src/components/ChatMessage.tsx`
- Create: `frontend/src/components/ClarificationModal.tsx`
- Create: `frontend/src/components/ChatInput.tsx`
- Create: `frontend/src/stores/chatStore.ts`
- Create: `frontend/src/services/api.ts`
- Modify: `frontend/src/App.tsx`

**功能：**
- 聊天消息展示（用户消息、系统消息）
- 澄清对话框（单选/多选选项）
- 输入框 + 发送按钮
- 加载状态展示
