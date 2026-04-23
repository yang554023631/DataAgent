# 广告报表多Agent系统 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零开始构建一个6节点的多Agent对话式广告数据分析系统，包含完整的前后端实现。

**Architecture:** FastAPI + LangGraph 后端，React + TypeScript 前端，调用现有CustomReport服务获取数据。采用6节点单体架构：意图理解 → 人机协调 → 查询规划 → 数据执行 → 数据分析 → 报告生成。

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, Pydantic 2, React 18, TypeScript, Vite, Tailwind CSS, ECharts, Docker Compose

---

## 第一阶段：项目初始化与基础架构

---

### Task 1: 后端项目脚手架搭建

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/main.py`
- Create: `backend/src/config/settings.py`
- Create: `backend/.env.example`
- Create: `Makefile`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[tool.poetry]
name = "ad-report-agent"
version = "0.1.0"
description = "Multi-Agent Ad Report Analysis System"
authors = ["Your Name"]
readme = "README.md"

[tool.poetry.dependencies]
python = ">=3.11,<3.13"
fastapi = "^0.109.0"
uvicorn = { extras = ["standard"], version = "^0.27.0" }
langgraph = "^0.1.0"
langchain = "^0.1.0"
langchain-anthropic = "^0.1.0"
anthropic = "^0.18.0"
openai = "^1.0.0"
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"
httpx = "^0.26.0"
python-dotenv = "^1.0.0"
numpy = "^1.26.0"
pandas = "^2.2.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.23.0"
ruff = "^0.2.0"
mypy = "^1.8.0"
pre-commit = "^3.6.0"

[build-system]
requires = ["poetry-core==1.7.0"]
build-backend = "poetry.core.masonry.api"
```

- [ ] **Step 2: 创建 config/settings.py**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    
    # LLM
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DEFAULT_MODEL: str = "claude-3-haiku-20240307"
    ANALYST_MODEL: str = "claude-3-sonnet-20240229"
    
    # Custom Report
    CUSTOM_REPORT_URL: str = "http://localhost:3000"
    CUSTOM_REPORT_TIMEOUT: int = 30
    
    # Limits
    MAX_CLARIFICATION_COUNT: int = 3
    MAX_DRILL_DOWN_LEVEL: int = 2

settings = Settings()
```

- [ ] **Step 3: 创建 .env.example**

```env
ANTHROPIC_API_KEY=your_api_key_here
OPENAI_API_KEY=your_api_key_here
CUSTOM_REPORT_URL=http://localhost:3000
```

- [ ] **Step 4: 创建 src/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config.settings import settings

app = FastAPI(title="Ad Report Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ad-report-agent"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
```

- [ ] **Step 5: 创建 Makefile**

```makefile
.PHONY: install install-dev run test lint format clean

install:
	poetry install

install-dev: install
	poetry run pre-commit install

run:
	cd backend && poetry run python src/main.py

test:
	cd backend && poetry run pytest tests/ -v

lint:
	cd backend && poetry run ruff check src/ tests/
	cd backend && poetry run mypy src/

format:
	cd backend && poetry run ruff format src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.pyc" -delete
```

- [ ] **Step 6: 测试项目能运行**

Run: `cd backend && poetry install && poetry run python src/main.py`
Expected: Server starts on port 8000, health check returns ok

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/src/main.py backend/src/config/settings.py backend/.env.example Makefile
git commit -m "feat: initialize backend project scaffold"
```

---

### Task 2: Pydantic 数据模型定义

**Files:**
- Create: `backend/src/models/__init__.py`
- Create: `backend/src/models/common.py`
- Create: `backend/src/models/intent.py`
- Create: `backend/src/models/query.py`
- Create: `backend/src/models/analysis.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: 创建 models/common.py**

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class Filter(BaseModel):
    field: str
    op: str = Field(default="=", description="比较操作符: =, !=, >, <, >=, <=")
    value: int | str | float

class TimeRange(BaseModel):
    start_date: date
    end_date: date
    unit: str = Field(default="day", description="聚合粒度: day, week, month")
```

- [ ] **Step 2: 创建 models/intent.py**

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from .common import TimeRange, Filter

class Ambiguity(BaseModel):
    has_ambiguity: bool = False
    type: Optional[str] = None
    reason: Optional[str] = None
    options: List[Dict] = Field(default_factory=list)

class QueryIntent(BaseModel):
    """结构化查询意图"""
    time_range: TimeRange
    metrics: List[str]
    group_by: List[str] = Field(default_factory=list)
    filters: List[Filter] = Field(default_factory=list)
    is_incremental: bool = False
    intent_type: str = Field(default="query", description="query / attribution / compare")
    ambiguity: Ambiguity = Field(default_factory=Ambiguity)
```

- [ ] **Step 3: 创建 models/query.py**

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from .common import Filter

class ChartConfig(BaseModel):
    type: str = Field(description="line, bar, pie, table")
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    limit: Optional[int] = None

class QueryRequest(BaseModel):
    """最终查询请求，传给CustomReport"""
    index_type: str = Field(default="general", description="general, audience")
    time_range: dict
    metrics: List[str]
    group_by: List[str] = Field(default_factory=list)
    filters: List[Filter] = Field(default_factory=list)
    chart_config: Optional[ChartConfig] = None

class QueryResult(BaseModel):
    """查询结果"""
    success: bool
    total_rows: int = 0
    data: List[dict] = Field(default_factory=list)
    execution_time_ms: Optional[int] = None
    error_type: Optional[str] = None
    message: Optional[str] = None
    suggestions: List[str] = Field(default_factory=list)
```

- [ ] **Step 4: 创建 models/analysis.py**

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class Anomaly(BaseModel):
    type: str = Field(description="sudden_change, outlier, trend")
    metric: str
    dimension_key: Optional[str] = None
    dimension_value: Optional[str] = None
    current_value: float
    change_percent: Optional[float] = None
    z_score: Optional[float] = None
    severity: str = Field(description="low, medium, high")

class AnalysisResult(BaseModel):
    """数据分析结果"""
    summary: str
    anomalies: List[Anomaly] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
```

- [ ] **Step 5: 创建 models/__init__.py**

```python
from .common import TimeRange, Filter
from .intent import QueryIntent, Ambiguity
from .query import QueryRequest, QueryResult, ChartConfig
from .analysis import AnalysisResult, Anomaly

__all__ = [
    "TimeRange",
    "Filter",
    "QueryIntent",
    "Ambiguity",
    "QueryRequest",
    "QueryResult",
    "ChartConfig",
    "AnalysisResult",
    "Anomaly",
]
```

- [ ] **Step 6: 写单元测试**

```python
from datetime import date
from src.models import QueryIntent, TimeRange, Filter

def test_query_intent_creation():
    intent = QueryIntent(
        time_range=TimeRange(
            start_date=date(2024, 4, 15),
            end_date=date(2024, 4, 21)
        ),
        metrics=["impressions", "clicks", "ctr"],
        group_by=["campaign_id"],
        filters=[Filter(field="audience_os", op="=", value=2)]
    )
    assert intent.metrics == ["impressions", "clicks", "ctr"]
    assert intent.filters[0].value == 2

def test_ambiguity_default():
    intent = QueryIntent(
        time_range=TimeRange(start_date=date(2024, 4, 15), end_date=date(2024, 4, 21)),
        metrics=["impressions"]
    )
    assert intent.ambiguity.has_ambiguity is False
```

- [ ] **Step 7: 运行测试验证**

Run: `cd backend && poetry run pytest tests/test_models.py -v`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add backend/src/models/ backend/tests/test_models.py
git commit -m "feat: add Pydantic data models"
```

---

### Task 3: LangGraph State 与 Graph 骨架

**Files:**
- Create: `backend/src/graph/state.py`
- Create: `backend/src/graph/builder.py`
- Create: `backend/src/graph/nodes.py`
- Create: `backend/tests/test_graph_state.py`

- [ ] **Step 1: 创建 graph/state.py**

```python
from typing import TypedDict, Optional, List, Dict, Annotated
from datetime import datetime
from langgraph.graph import add_messages

def append_history(left: List[Dict], right: List[Dict]) -> List[Dict]:
    """追加历史记录，最多保留20条"""
    result = left.copy()
    result.extend(right)
    if len(result) > 20:
        result = result[-20:]
    return result

class AdReportState(TypedDict):
    """LangGraph 全局状态"""
    # 会话基本信息
    session_id: str
    user_id: Optional[str]
    
    # 用户输入
    user_input: str
    conversation_history: Annotated[List[Dict], append_history]
    
    # 意图理解输出
    query_intent: Optional[Dict]
    ambiguity: Optional[Dict]
    
    # 人机澄清输出
    user_feedback: Optional[Dict]
    clarification_count: int
    
    # 查询规划输出
    query_request: Optional[Dict]
    query_warnings: List[str]
    
    # 数据执行输出
    query_result: Optional[Dict]
    execution_time_ms: Optional[int]
    
    # 数据分析输出
    analysis_result: Optional[Dict]
    drill_down_level: int
    needs_drill_down: bool
    
    # 报告生成输出
    final_report: Optional[Dict]
    
    # 执行控制
    error: Optional[Dict]
```

- [ ] **Step 2: 创建 graph/nodes.py 占位**

```python
"""
各节点实现占位符
"""

async def nlu_node(state: dict) -> dict:
    """意图理解节点"""
    # TODO: 实现
    return {"query_intent": None, "ambiguity": None}

async def hitl_node(state: dict) -> dict:
    """人机协调节点"""
    # TODO: 实现
    return {"user_feedback": None}

async def planner_node(state: dict) -> dict:
    """查询规划节点"""
    # TODO: 实现
    return {"query_request": None, "query_warnings": []}

async def executor_node(state: dict) -> dict:
    """数据执行节点"""
    # TODO: 实现
    return {"query_result": None, "execution_time_ms": 0}

async def analyst_node(state: dict) -> dict:
    """数据分析节点"""
    # TODO: 实现
    return {
        "analysis_result": None,
        "drill_down_level": state.get("drill_down_level", 0),
        "needs_drill_down": False
    }

async def reporter_node(state: dict) -> dict:
    """报告生成节点"""
    # TODO: 实现
    return {"final_report": None}
```

- [ ] **Step 3: 创建 graph/builder.py**

```python
from langgraph.graph import StateGraph, END
from .state import AdReportState
from .nodes import nlu_node, hitl_node, planner_node, executor_node, analyst_node, reporter_node

def build_graph():
    """构建完整的 LangGraph 流程图"""
    graph = StateGraph(AdReportState)
    
    # 添加节点
    graph.add_node("nlu", nlu_node)
    graph.add_node("hitl", hitl_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("reporter", reporter_node)
    
    # 设置入口
    graph.set_entry_point("nlu")
    
    # NLU -> 条件判断
    def need_clarification_after_nlu(state: dict) -> str:
        ambiguity = state.get("ambiguity", {})
        if ambiguity and ambiguity.get("has_ambiguity", False):
            return "hitl"
        return "planner"
    
    graph.add_conditional_edges(
        "nlu",
        need_clarification_after_nlu,
        {"hitl": "hitl", "planner": "planner"}
    )
    
    # HITL -> 回到 NLU 重新理解
    graph.add_edge("hitl", "nlu")
    
    # Planner -> 条件判断（可能也需要确认）
    def need_confirm_after_planner(state: dict) -> str:
        warnings = state.get("query_warnings", [])
        # 如果有需要用户确认的警告，去HITL
        for warning in warnings:
            if "need_confirm" in warning:
                return "hitl"
        return "executor"
    
    graph.add_conditional_edges(
        "planner",
        need_confirm_after_planner,
        {"hitl": "hitl", "executor": "executor"}
    )
    
    # Executor -> Analyst
    graph.add_edge("executor", "analyst")
    
    # Analyst -> 条件判断（是否需要下钻）
    def need_drill_down(state: dict) -> str:
        if state.get("needs_drill_down", False):
            return "planner"
        return "reporter"
    
    graph.add_conditional_edges(
        "analyst",
        need_drill_down,
        {"planner": "planner", "reporter": "reporter"}
    )
    
    # Reporter -> 结束
    graph.add_edge("reporter", END)
    
    return graph.compile()

# 导出编译好的Graph
app = build_graph()
```

- [ ] **Step 4: 写Graph状态测试**

```python
from src.graph.state import AdReportState

def test_state_initialization():
    state: AdReportState = {
        "session_id": "test-123",
        "user_id": "user-456",
        "user_input": "看上周的曝光",
        "conversation_history": [],
        "query_intent": None,
        "ambiguity": None,
        "user_feedback": None,
        "clarification_count": 0,
        "query_request": None,
        "query_warnings": [],
        "query_result": None,
        "execution_time_ms": None,
        "analysis_result": None,
        "drill_down_level": 0,
        "needs_drill_down": False,
        "final_report": None,
        "error": None
    }
    assert state["session_id"] == "test-123"
    assert state["user_input"] == "看上周的曝光"

def test_append_history_reducer():
    from src.graph.state import append_history
    
    left = [{"role": "user", "content": "hello"}]
    right = [{"role": "assistant", "content": "hi"}]
    result = append_history(left, right)
    
    assert len(result) == 2
    assert result[0]["content"] == "hello"
    assert result[1]["content"] == "hi"
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && poetry run pytest tests/test_graph_state.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/src/graph/ backend/tests/test_graph_state.py
git commit -m "feat: add LangGraph state and graph skeleton"
```

---

### Task 4: CustomReport 客户端实现

**Files:**
- Create: `backend/src/tools/custom_report_client.py`
- Create: `backend/src/tools/executor.py`
- Create: `backend/tests/test_custom_report_client.py`

- [ ] **Step 1: 创建 CustomReport 客户端**

```python
import httpx
import time
from typing import Optional
from src.config.settings import settings
from src.models import QueryRequest, QueryResult

class CustomReportClient:
    """CustomReport 服务 HTTP 客户端"""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.CUSTOM_REPORT_URL
        self.timeout = settings.CUSTOM_REPORT_TIMEOUT
    
    async def execute_query(self, query_request: QueryRequest) -> QueryResult:
        """执行报表查询"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/report/query",
                    json=query_request.model_dump()
                )
                response.raise_for_status()
                data = response.json()
                
                execution_time = int((time.time() - start_time) * 1000)
                
                return QueryResult(
                    success=True,
                    total_rows=len(data.get("data", [])),
                    data=data.get("data", []),
                    execution_time_ms=execution_time
                )
                
        except httpx.TimeoutException:
            return QueryResult(
                success=False,
                error_type="timeout",
                message="查询超时，请缩小时间范围或减少维度",
                suggestions=["改成按月汇总", "减少分组维度", "缩小时间范围到最近7天"]
            )
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return QueryResult(
                    success=False,
                    error_type="empty",
                    message="该条件下没有数据",
                    suggestions=["扩大时间范围", "调整过滤条件"]
                )
            return QueryResult(
                success=False,
                error_type="http_error",
                message=f"查询失败: {str(e)}"
            )
            
        except Exception as e:
            return QueryResult(
                success=False,
                error_type="unknown",
                message=f"未知错误: {str(e)}"
            )

# 单例
custom_report_client = CustomReportClient()
```

- [ ] **Step 2: 创建 Executor Tool**

```python
from langchain_core.tools import tool
from src.models import QueryRequest
from .custom_report_client import custom_report_client

@tool
async def execute_ad_report_query(query_request: dict) -> dict:
    """
    调用 CustomReport 服务执行广告报表查询
    
    Args:
        query_request: 查询请求Dict，符合QueryRequest模型结构
    
    Returns:
        查询结果Dict
    """
    req = QueryRequest(**query_request)
    result = await custom_report_client.execute_query(req)
    return result.model_dump()
```

- [ ] **Step 3: 写客户端测试**

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.tools.custom_report_client import CustomReportClient
from src.models import QueryRequest, TimeRange

@pytest.mark.asyncio
async def test_execute_query_timeout():
    client = CustomReportClient(base_url="http://test")
    
    with patch.object(client, '_post', new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = TimeoutError()
        
        result = await client.execute_query(
            QueryRequest(
                time_range={"start_date": "2024-04-01", "end_date": "2024-04-07"},
                metrics=["impressions"]
            )
        )
        
        assert result.success is False
        assert result.error_type == "timeout"
        assert len(result.suggestions) > 0
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && poetry run pytest tests/test_custom_report_client.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/src/tools/custom_report_client.py backend/src/tools/executor.py backend/tests/test_custom_report_client.py
git commit -m "feat: add CustomReport client and executor tool"
```

---

### Task 5: 数据执行节点完整实现

**Files:**
- Modify: `backend/src/graph/nodes.py`
- Create: `backend/tests/test_executor_node.py`

- [ ] **Step 1: 完善 executor_node 实现**

在 `backend/src/graph/nodes.py` 中更新 executor_node：

```python
import time
from src.tools.executor import execute_ad_report_query

async def executor_node(state: dict) -> dict:
    """数据执行节点：调用 CustomReport 接口"""
    query_request = state.get("query_request")
    
    if not query_request:
        return {
            "query_result": None,
            "execution_time_ms": 0,
            "error": {"type": "no_query", "message": "没有查询请求"}
        }
    
    start_time = time.time()
    
    try:
        result = await execute_ad_report_query.ainvoke(query_request)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return {
            "query_result": result,
            "execution_time_ms": execution_time,
            "error": None if result["success"] else {
                "type": result.get("error_type"),
                "message": result.get("message"),
                "suggestions": result.get("suggestions", [])
            }
        }
    except Exception as e:
        return {
            "query_result": None,
            "execution_time_ms": 0,
            "error": {"type": "exception", "message": str(e)}
        }
```

- [ ] **Step 2: 写节点测试**

```python
import pytest
from unittest.mock import patch
from src.graph.nodes import executor_node

@pytest.mark.asyncio
async def test_executor_node_with_valid_query():
    with patch("src.graph.nodes.execute_ad_report_query") as mock_tool:
        mock_tool.ainvoke.return_value = {
            "success": True,
            "total_rows": 10,
            "data": [{"date": "2024-04-01", "impressions": 1000}],
            "execution_time_ms": 150
        }
        
        state = {
            "query_request": {
                "time_range": {"start": "2024-04-01", "end": "2024-04-07"},
                "metrics": ["impressions"]
            }
        }
        
        result = await executor_node(state)
        assert result["query_result"]["success"] is True
        assert result["query_result"]["total_rows"] == 10
        assert result["error"] is None

@pytest.mark.asyncio
async def test_executor_node_no_query():
    state = {"query_request": None}
    result = await executor_node(state)
    assert result["query_result"] is None
    assert result["error"] is not None
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && poetry run pytest tests/test_executor_node.py -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/src/graph/nodes.py backend/tests/test_executor_node.py
git commit -m "feat: complete executor node implementation"
```

---

### Task 6: 前端项目脚手架

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/index.css`

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "ad-report-agent-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "@tanstack/react-query": "^5.18.0",
    "zustand": "^4.5.0",
    "echarts": "^5.4.3",
    "echarts-for-react": "^3.0.2",
    "lucide-react": "^0.323.0",
    "axios": "^1.6.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@typescript-eslint/eslint-plugin": "^6.14.0",
    "@typescript-eslint/parser": "^6.14.0",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.16",
    "eslint": "^8.55.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.5",
    "postcss": "^8.4.32",
    "tailwindcss": "^3.3.6",
    "typescript": "^5.2.2",
    "vite": "^5.0.8"
  }
}
```

- [ ] **Step 2: 创建 vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 3: 创建 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 4: 创建 Tailwind 配置**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 5: 创建 index.html**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>广告报表智能助手</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: 创建 src/index.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #a1a1a1;
}
```

- [ ] **Step 7: 创建 src/main.tsx 和 src/App.tsx**

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
)
```

```typescript
function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-gray-900">广告报表智能助手</h1>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="text-center py-20">
          <h2 className="text-xl text-gray-600">正在构建中...</h2>
        </div>
      </main>
    </div>
  )
}

export default App
```

- [ ] **Step 8: 测试前端能运行**

Run: `cd frontend && npm install && npm run dev`
Expected: Vite dev server starts on port 3001, page loads correctly

- [ ] **Step 9: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/tailwind.config.js frontend/postcss.config.js frontend/index.html frontend/src/main.tsx frontend/src/App.tsx frontend/src/index.css
git commit -m "feat: initialize frontend project scaffold"
```

---

## 📋 第一阶段完成检查

- [x] 后端项目脚手架
- [x] Pydantic 数据模型定义
- [x] LangGraph State 与 Graph 骨架
- [x] CustomReport 客户端
- [x] 数据执行节点
- [x] 前端项目脚手架

---

Plan complete and saved to `docs/superpowers/plans/2024-04-24-ad-report-agent-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach would you prefer?
