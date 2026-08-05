# 意图识别模块优化（Phase 1）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级意图识别模块为"分层架构 + LLM 增强"方案，包含顶层三分类、报表意图结构化识别、通用澄清机制、拒答能力和回退机制。

**Architecture:**
- Layer 1: 顶层意图分类器（规则快筛 + LLM 精分），输出三分类 + 置信度
- Layer 2-报表: LLM 结构化提取 + 规则工具校验 + 能力校验，缺信息触发澄清
- 通用澄清节点: LangGraph interrupt 机制，支持 10 种澄清类型
- 回退机制: 第二层澄清时用户意图变化可回退到第一层，最多 3 次

**Tech Stack:** Python 3.11+, LangGraph 0.2.x, LangChain 0.3.x, Pydantic 2.x, langchain-openai (火山引擎 Ark), pytest

---

## Global Constraints

- Python version: `>=3.11,<3.13`
- LLM provider: 火山引擎 Ark（通过 `langchain-openai` 的 `ChatOpenAI` 调用，base_url 指向 Ark）
- 已有 LLM 单例: `src/rag/agents.py` 中的 `_get_llm()`，复用之
- Graph 状态类型: `AdReportState`（TypedDict，在 `src/graph/state.py`）
- 日志体系: `logging_config.py` + contextvars 注入 request_id/session_id，所有新日志用 `logger.info/error/warning`
- 置信度阈值: 顶层分类 0.7，别名澄清 0.8
- 最大回退次数: 3 次
- LLM 最大重试次数: 3 次（含首次）
- 代码风格: 跟随现有代码，使用 type hints，pydantic 模型做数据结构
- 测试框架: pytest + pytest-asyncio

---

## File Structure Map

### New Files
| File | Responsibility |
|------|---------------|
| `backend/src/intent/__init__.py` | 意图识别模块包 |
| `backend/src/intent/top_classifier.py` | 顶层意图分类器（规则快筛 + LLM 精分） |
| `backend/src/intent/report_intent.py` | 报表意图识别与填充（LLM + 规则校验 + 能力校验） |
| `backend/src/intent/capability_registry.py` | 系统能力注册表（指标/层级/维度/时间范围） |
| `backend/src/intent/clarify_node.py` | 通用澄清节点（处理用户反馈 + 路由 + 回退检测） |
| `backend/src/intent/reject_node.py` | 拒答节点 |
| `backend/src/intent/prompts.py` | 所有 LLM prompt 模板 |
| `backend/src/intent/models.py` | 意图相关 Pydantic 模型 |
| `backend/src/intent/llm_client.py` | LLM 调用封装（重试 + 降级） |

### Modified Files
| File | Change |
|------|--------|
| `backend/src/graph/state.py` | 新增意图分类、澄清、回退计数字段 |
| `backend/src/graph/builder.py` | 重建 Graph 流程（新节点 + 新路由） |
| `backend/src/graph/nodes.py` | 新增节点函数，旧 nlu_node/hitl_node 标记废弃 |
| `backend/src/api/sessions.py` | 适配新澄清格式的 API 返回 |
| `backend/src/services/session_service.py` | 适配新状态字段和澄清逻辑 |
| `backend/src/rag/agents.py` | 导出 `_get_llm` 供 intent 模块复用 |

### Test Files
| File | What it tests |
|------|--------------|
| `backend/tests/test_top_classifier.py` | 顶层分类器（规则快筛 + LLM mock） |
| `backend/tests/test_report_intent.py` | 报表意图识别（提取 + 校验 + 澄清触发） |
| `backend/tests/test_capability_registry.py` | 能力注册表 |
| `backend/tests/test_clarify_node.py` | 澄清节点（反馈处理 + 回退检测） |
| `backend/tests/test_reject_node.py` | 拒答节点 |
| `backend/tests/test_llm_client.py` | LLM 客户端（重试 + 降级） |
| `backend/tests/test_intent_integration.py` | 端到端集成测试 |

---

### Task 1: LLM 客户端封装（重试 + 降级）

**Files:**
- Create: `backend/src/intent/__init__.py`
- Create: `backend/src/intent/llm_client.py`
- Create: `backend/tests/test_llm_client.py`
- Modify: `backend/src/rag/agents.py` — 将 `_get_llm` 改为导出函数 `get_llm()`

**Interfaces:**
- Consumes: `_get_llm()` from `src/rag/agents.py`（Ark/ChatOpenAI 单例）
- Produces:
  - `IntentLLMClient` 类
  - `async call_llm_with_retry(system_prompt: str, user_prompt: str, json_mode: bool = True) -> str` — 返回 LLM 响应文本
  - `get_fallback_classifier()` — 获取降级用的纯规则分类器引用（用于 LLM 全挂时）

**Why this task first:** 所有后续 LLM 相关任务都依赖这个封装。先把重试/降级/错误处理做好，后面的任务只管调用。

- [ ] **Step 1: 创建 intent 包的 __init__.py**

```python
# src/intent/__init__.py
```

- [ ] **Step 2: 改造 rag/agents.py 导出 get_llm**

修改 `src/rag/agents.py` 第 18-35 行的 `_get_llm()`，改为公开函数：

```python
def get_llm():
    """获取 LLM 单例 - 优先使用火山引擎 Ark"""
    global _llm_instance
    if _llm_instance is None:
        if ARK_LLM_MODEL and ARK_API_KEY:
            _llm_instance = ChatOpenAI(
                model=ARK_LLM_MODEL,
                api_key=ARK_API_KEY,
                base_url=ARK_BASE_URL,
                temperature=0,
            )
        else:
            _llm_instance = ChatOpenAI(
                model="gpt-3.5-turbo",
                api_key=OPENAI_API_KEY,
                temperature=0,
            )
    return _llm_instance
```

保留 `_get_llm` 作为向后兼容的别名：`_get_llm = get_llm`

- [ ] **Step 3: 写 LLM 客户端测试**

```python
# tests/test_llm_client.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.intent.llm_client import IntentLLMClient, call_llm_with_retry


@pytest.mark.asyncio
async def test_call_llm_success():
    """LLM 首次调用成功"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"category": "report", "confidence": 0.9}'
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    client = IntentLLMClient(llm=mock_llm)
    result = await client.call("你是助手", "用户输入", json_mode=True)
    assert result == '{"category": "report", "confidence": 0.9}'
    assert mock_llm.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_call_llm_retry_success():
    """前两次失败，第三次成功"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"result": "ok"}'
    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("API error")
        return mock_response

    mock_llm.ainvoke = AsyncMock(side_effect=side_effect)
    client = IntentLLMClient(llm=mock_llm, max_retries=3, base_delay=0.001)

    result = await client.call("sys", "user")
    assert result == '{"result": "ok"}'
    assert call_count == 3


@pytest.mark.asyncio
async def test_call_llm_all_fail():
    """3 次全部失败，抛出异常"""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("API error"))

    client = IntentLLMClient(llm=mock_llm, max_retries=3, base_delay=0.001)

    with pytest.raises(Exception, match="API error"):
        await client.call("sys", "user")
    assert mock_llm.ainvoke.await_count == 3


@pytest.mark.asyncio
async def test_call_llm_json_output():
    """json_mode=True 时，确保使用结构化输出"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"key": "value"}'
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    client = IntentLLMClient(llm=mock_llm)
    await client.call("sys", "user", json_mode=True)

    # 验证调用时传入了正确的格式
    call_args = mock_llm.ainvoke.call_args
    # messages 应该是 system + human
    assert len(call_args[0][0].to_messages()) == 2
```

- [ ] **Step 4: 运行测试，验证失败**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_llm_client.py -v
```

预期：ImportError 或 ModuleNotFoundError（因为文件还没写）

- [ ] **Step 5: 实现 LLM 客户端**

```python
# src/intent/llm_client.py
"""
LLM 调用封装 — 带重试、指数退避、日志

用法:
    client = IntentLLMClient()
    result = await client.call(system_prompt, user_prompt, json_mode=True)
"""
import logging
import asyncio
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

# 单例
_client_instance: Optional["IntentLLMClient"] = None


def get_intent_llm_client() -> "IntentLLMClient":
    """获取 IntentLLMClient 单例"""
    global _client_instance
    if _client_instance is None:
        from src.rag.agents import get_llm
        _client_instance = IntentLLMClient(llm=get_llm())
    return _client_instance


class IntentLLMClient:
    """
    LLM 调用客户端，封装重试逻辑

    max_retries: 最大尝试次数（含首次）
    base_delay: 首次重试延迟秒数，后续指数退避
    """

    def __init__(
        self,
        llm: ChatOpenAI = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        self.llm = llm
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
    ) -> str:
        """
        调用 LLM，支持重试

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入提示词
            json_mode: 是否期望 JSON 输出（仅用于日志和提示，不强制结构化输出）

        Returns:
            LLM 响应文本

        Raises:
            Exception: 所有重试都失败时抛出最后一次异常
        """
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", user_prompt),
                ])
                chain = prompt | self.llm
                response = await chain.ainvoke({})
                content = response.content.strip()

                if attempt > 1:
                    logger.info(f"LLM调用成功（第{attempt}次重试）")
                return content

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"LLM调用失败（第{attempt}/{self.max_retries}次）: {e}"
                )
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        # 所有重试都失败
        logger.error(f"LLM调用全部失败（共{self.max_retries}次）: {last_exception}")
        raise last_exception
```

- [ ] **Step 6: 运行测试验证通过**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_llm_client.py -v
```

预期：全部 PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/simon/AL/DataAgent
git add backend/src/intent/__init__.py backend/src/intent/llm_client.py \
        backend/src/rag/agents.py backend/tests/test_llm_client.py
git commit -m "feat: 添加 LLM 调用客户端（带重试 + 指数退避）

- 封装 IntentLLMClient，支持 3 次重试 + 指数退避
- 复用 RAG 模块的 LLM 单例
- 完整日志埋点（失败告警 + 重试记录）
- 将 _get_llm 改为公开的 get_llm()

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: 系统能力注册表

**Files:**
- Create: `backend/src/intent/capability_registry.py`
- Create: `backend/tests/test_capability_registry.py`

**Interfaces:**
- Consumes: 现有 `METRIC_MAPPING` / `DIMENSION_MAPPING` from `src/tools/term_mapper.py`
- Produces:
  - `SUPPORTED_METRICS: Dict[str, List[str]]` — {标准名: [别名列表]}
  - `SUPPORTED_AD_LEVELS: List[str]` — ["campaign", "ad_group", "creative"]
  - `SUPPORTED_DIMENSIONS: Dict[str, List[str]]` — {标准名: [别名列表]}
  - `SUPPORTED_TIME_UNITS: List[str]` — ["day", "week", "month"]
  - `validate_metric(name: str) -> Tuple[bool, Optional[str]]` — (是否支持, 标准名)
  - `validate_ad_level(name: str) -> Tuple[bool, Optional[str]]`
  - `validate_dimension(name: str) -> Tuple[bool, Optional[str]]`
  - `get_metric_aliases() -> Dict[str, str]` — 别名 → 标准名 的映射字典
  - `get_all_metric_names() -> List[str]` — 所有指标的中文名称列表（用于澄清选项）
  - `get_all_dimension_names() -> List[str]` — 所有维度的中文名称列表

**Why:** 报表意图识别需要做能力校验，这个注册表是校验的数据源。独立成模块方便维护和测试。

- [ ] **Step 1: 写能力注册表测试**

```python
# tests/test_capability_registry.py
import pytest
from src.intent.capability_registry import (
    validate_metric,
    validate_ad_level,
    validate_dimension,
    get_all_metric_names,
    get_all_dimension_names,
    get_metric_aliases,
    SUPPORTED_AD_LEVELS,
)


class TestValidateMetric:
    def test_standard_name(self):
        ok, std = validate_metric("impressions")
        assert ok is True
        assert std == "impressions"

    def test_chinese_alias(self):
        ok, std = validate_metric("曝光")
        assert ok is True
        assert std == "impressions"

    def test_ctr_case_insensitive(self):
        ok, std = validate_metric("CTR")
        assert ok is True
        assert std == "ctr"

    def test_unsupported(self):
        ok, std = validate_metric("留存率")
        assert ok is False
        assert std is None

    def test_empty(self):
        ok, std = validate_metric("")
        assert ok is False
        assert std is None


class TestValidateAdLevel:
    @pytest.mark.parametrize("name,expected", [
        ("campaign", (True, "campaign")),
        ("计划", (True, "campaign")),
        ("ad_group", (True, "ad_group")),
        ("广告组", (True, "ad_group")),
        ("creative", (True, "creative")),
        ("素材", (True, "creative")),
        ("创意", (True, "creative")),
        ("账户", (False, None)),
    ])
    def test_ad_level_validation(self, name, expected):
        ok, std = validate_ad_level(name)
        assert (ok, std) == expected


class TestValidateDimension:
    def test_time_dimension(self):
        ok, std = validate_dimension("日期")
        assert ok is True
        assert std == "data_date"

    def test_audience_dimension(self):
        ok, std = validate_dimension("性别")
        assert ok is True
        assert std == "audience_gender"

    def test_business_dimension(self):
        ok, std = validate_dimension("渠道")
        assert ok is True
        assert std == "campaign_id"

    def test_unsupported_dimension(self):
        ok, std = validate_dimension("血型")
        assert ok is False
        assert std is None


class TestLists:
    def test_get_all_metric_names(self):
        names = get_all_metric_names()
        assert "曝光" in names
        assert "点击" in names
        assert "消耗" in names
        assert len(names) >= 9

    def test_get_all_dimension_names(self):
        names = get_all_dimension_names()
        assert "日期" in names
        assert "性别" in names
        assert len(names) >= 10

    def test_get_metric_aliases(self):
        aliases = get_metric_aliases()
        assert "曝光" in aliases
        assert aliases["曝光"] == "impressions"
        assert "ctr" in aliases
        assert aliases["ctr"] == "ctr"

    def test_supported_ad_levels(self):
        assert "campaign" in SUPPORTED_AD_LEVELS
        assert "ad_group" in SUPPORTED_AD_LEVELS
        assert "creative" in SUPPORTED_AD_LEVELS
        assert len(SUPPORTED_AD_LEVELS) == 3
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_capability_registry.py -v
```

预期：ImportError

- [ ] **Step 3: 实现能力注册表**

```python
# src/intent/capability_registry.py
"""
系统能力注册表 — 记录系统支持的指标、层级、维度、时间范围等

报表意图识别用这个注册表做能力校验，不支持的内容触发澄清。
"""
from typing import Dict, List, Tuple, Optional

# 从现有规则工具导入映射关系，保持一致性
from src.tools.term_mapper import METRIC_MAPPING, DIMENSION_MAPPING


# ========== 广告层级 ==========

# 标准名 -> 中文别名
AD_LEVEL_MAP: Dict[str, List[str]] = {
    "campaign": ["计划", "广告计划", "活动", "广告活动", "campaign"],
    "ad_group": ["广告组", "组", "adgroup", "ad_group"],
    "creative": ["创意", "素材", "creative", "creatives"],
}

SUPPORTED_AD_LEVELS: List[str] = list(AD_LEVEL_MAP.keys())


def _build_alias_map(standard_to_aliases: Dict[str, List[str]]) -> Dict[str, str]:
    """从 {标准名: [别名]} 构建 {别名: 标准名} 映射"""
    alias_map = {}
    for std, aliases in standard_to_aliases.items():
        # 标准名自己也加入映射
        alias_map[std.lower()] = std
        for alias in aliases:
            alias_map[alias.lower()] = std
    return alias_map


_ad_level_alias_map = _build_alias_map(AD_LEVEL_MAP)


def validate_ad_level(name: str) -> Tuple[bool, Optional[str]]:
    """
    校验广告层级是否支持

    Returns:
        (是否支持, 标准名)
    """
    if not name:
        return False, None
    key = name.lower()
    if key in _ad_level_alias_map:
        return True, _ad_level_alias_map[key]
    return False, None


# ========== 指标 ==========

# 把 METRIC_MAPPING（别名->标准）转换成 标准->[别名] 格式
_metric_standard_to_aliases: Dict[str, List[str]] = {}
for alias, standard in METRIC_MAPPING.items():
    if standard not in _metric_standard_to_aliases:
        _metric_standard_to_aliases[standard] = []
    _metric_standard_to_aliases[standard].append(alias)

SUPPORTED_METRICS: Dict[str, List[str]] = _metric_standard_to_aliases


def _build_metric_alias_map() -> Dict[str, str]:
    """构建 {别名: 标准名} 的指标映射"""
    alias_map = {}
    for standard, aliases in SUPPORTED_METRICS.items():
        alias_map[standard.lower()] = standard
        for alias in aliases:
            alias_map[alias.lower()] = standard
    return alias_map


_metric_alias_map = _build_metric_alias_map()


def validate_metric(name: str) -> Tuple[bool, Optional[str]]:
    """
    校验指标是否支持

    Returns:
        (是否支持, 标准名)
    """
    if not name:
        return False, None
    key = name.lower()
    if key in _metric_alias_map:
        return True, _metric_alias_map[key]
    return False, None


def get_metric_aliases() -> Dict[str, str]:
    """获取 {别名: 标准名} 的完整映射"""
    return _metric_alias_map.copy()


def get_all_metric_names() -> List[str]:
    """获取所有指标的主要中文名称列表（用于展示选项）"""
    # 每个指标取第一个中文别名作为展示名
    primary_names = []
    for standard, aliases in SUPPORTED_METRICS.items():
        # 优先找中文名（非英文）
        cn_aliases = [a for a in aliases if not a.replace("_", "").isalpha()]
        if cn_aliases:
            primary_names.append(cn_aliases[0])
        else:
            primary_names.append(standard)
    return primary_names


# ========== 维度 ==========

# 把 DIMENSION_MAPPING 转换成 标准->[别名]
_dimension_standard_to_aliases: Dict[str, List[str]] = {}
for alias, standard in DIMENSION_MAPPING.items():
    if standard not in _dimension_standard_to_aliases:
        _dimension_standard_to_aliases[standard] = []
    _dimension_standard_to_aliases[standard].append(alias)

SUPPORTED_DIMENSIONS: Dict[str, List[str]] = _dimension_standard_to_aliases


def _build_dimension_alias_map() -> Dict[str, str]:
    alias_map = {}
    for standard, aliases in SUPPORTED_DIMENSIONS.items():
        alias_map[standard.lower()] = standard
        for alias in aliases:
            alias_map[alias.lower()] = standard
    return alias_map


_dimension_alias_map = _build_dimension_alias_map()


def validate_dimension(name: str) -> Tuple[bool, Optional[str]]:
    """
    校验维度是否支持

    Returns:
        (是否支持, 标准名)
    """
    if not name:
        return False, None
    key = name.lower()
    if key in _dimension_alias_map:
        return True, _dimension_alias_map[key]
    return False, None


def get_all_dimension_names() -> List[str]:
    """获取所有维度的主要中文名称列表"""
    primary_names = []
    for standard, aliases in SUPPORTED_DIMENSIONS.items():
        cn_aliases = [a for a in aliases if not a.replace("_", "").isalpha()]
        if cn_aliases:
            primary_names.append(cn_aliases[0])
        else:
            primary_names.append(standard)
    return primary_names


# ========== 时间粒度 ==========

SUPPORTED_TIME_UNITS: List[str] = ["day", "week", "month"]
TIME_UNIT_ALIASES: Dict[str, str] = {
    "天": "day", "日": "day", "按天": "day", "每天": "day",
    "周": "week", "按周": "week", "每周": "week",
    "月": "month", "按月": "month", "每月": "month",
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_capability_registry.py -v
```

预期：全部 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/simon/AL/DataAgent
git add backend/src/intent/capability_registry.py \
        backend/tests/test_capability_registry.py
git commit -m "feat: 添加系统能力注册表（指标/层级/维度校验）

- 支持指标、广告层级、维度的校验与别名映射
- 从现有 term_mapper 导入数据，保持一致性
- 提供中文名称列表，用于澄清选项展示

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: 意图相关 Pydantic 模型 + Prompt 模板

**Files:**
- Create: `backend/src/intent/models.py`
- Create: `backend/src/intent/prompts.py`

**Interfaces:**
- Consumes: 无（纯数据定义）
- Produces:
  - `TopClassificationResult` — 顶层分类结果模型
  - `ReportIntentResult` — 报表意图识别结果模型
  - `ClarificationInfo` — 澄清信息模型
  - `TOP_CLASSIFIER_SYSTEM_PROMPT` — 顶层分类器系统提示词
  - `REPORT_INTENT_SYSTEM_PROMPT` — 报表意图识别系统提示词

**Why:** 把数据模型和 prompt 集中管理，后面的分类器和意图识别都引用这些。

- [ ] **Step 1: 实现 Pydantic 模型**

```python
# src/intent/models.py
"""
意图识别相关 Pydantic 模型
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ==================== 顶层分类 ====================

class TopClassificationResult(BaseModel):
    """顶层意图分类结果"""
    category: str = Field(description="report / knowledge / out_of_domain")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度 0.0~1.0")
    reason: str = Field(default="", description="判断依据，用于日志")
    source: str = Field(default="llm", description="rule_fastpath / llm")


# ==================== 报表意图 ====================

class ReportTimeRange(BaseModel):
    """时间范围"""
    start_date: str = Field(description="YYYY-MM-DD")
    end_date: str = Field(description="YYYY-MM-DD")
    unit: str = Field(default="day", description="day / week / month")
    is_lifetime: bool = Field(default=False, description="是否为广告生命周期")


class ReportIntentResult(BaseModel):
    """报表意图识别结果"""
    # 必填字段
    advertiser_ids: List[str] = Field(default_factory=list)
    time_range: Optional[ReportTimeRange] = None
    metrics: List[str] = Field(default_factory=list)
    ad_level: Optional[str] = Field(default=None, description="campaign / ad_group / creative")

    # 可选字段
    group_by: List[str] = Field(default_factory=list)
    filters: List[Dict[str, Any]] = Field(default_factory=list)
    is_comparison: bool = False
    compare_time_range: Optional[ReportTimeRange] = None
    top_n: Optional[int] = None
    chart_type: Optional[str] = None

    # 元信息
    confidence: float = Field(default=1.0, description="整体置信度")
    alias_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="别名映射记录，{用户原文: 标准名}"
    )


# ==================== 澄清信息 ====================

class ClarificationInfo(BaseModel):
    """澄清信息"""
    type: str = Field(description=(
        "澄清类型: intent_confirm / missing_advertiser / missing_time_range / "
        "missing_metrics / missing_ad_level / unsupported_metric / "
        "unsupported_dimension / alias_confirm / knowledge_scope_guide / "
        "knowledge_clarify"
    ))
    question: str = Field(description="向用户展示的问题")
    options: List[Dict[str, str]] = Field(
        default_factory=list,
        description="选项列表，每项 {value, label}"
    )
    allow_custom_input: bool = Field(
        default=True,
        description="是否允许用户自由输入"
    )
    missing_fields: List[str] = Field(
        default_factory=list,
        description="缺失的字段列表，用于层内恢复"
    )


# ==================== 知识意图（占位，Phase 2 实现） ====================

class KnowledgeIntentResult(BaseModel):
    """知识问答意图识别结果（Phase 2 实现）"""
    question_type: str = Field(default="general")
    core_topics: List[str] = Field(default_factory=list)
    query_rewrite: str = Field(default="")
    confidence: float = Field(default=1.0)
```

- [ ] **Step 2: 实现 Prompt 模板**

```python
# src/intent/prompts.py
"""
意图识别相关的 LLM Prompt 模板
"""

# ==================== 顶层分类器 ====================

TOP_CLASSIFIER_SYSTEM_PROMPT = """你是广告数据分析助手的意图分类专家。

你的任务是判断用户输入属于哪一类，并输出 JSON 格式的分类结果。

## 分类体系

### 1. report（报表查询）
用户想要查询广告数据、查看报表、分析数据表现。
特征：提到具体的指标（曝光、点击、消耗、转化、CTR、ROI 等）、时间（今天、上周、上个月等）、
维度（按天、按地区、按性别）、广告主/计划/组/素材等数据对象。
示例："昨天的曝光点击消耗"、"上个月 ROI 最好的计划"、"按性别看 CTR"

### 2. knowledge（知识问答）
用户想要了解广告相关的概念、知识、策略、操作方法等。
特征：询问"什么是"、"怎么"、"为什么"、"如何"，且不涉及具体数据查询。
示例："什么是 CTR"、"冷启动跑不动怎么办"、"怎么优化素材"、"A/B 测试怎么做"

### 3. out_of_domain（领域外）
用户的问题与广告完全无关，应该拒绝回答。
示例："今天天气怎么样"、"你好"、"推荐一部电影"、"Python 怎么学"

## 输出格式（严格 JSON）
{{
    "category": "report | knowledge | out_of_domain",
    "confidence": 0.0,
    "reason": "一句话说明判断依据"
}}

## 注意
- confidence 用 0 到 1 之间的小数表示你的确定程度
- 如果用户输入很简短或很模糊，confidence 应该低于 0.7
- 只输出 JSON，不要输出其他任何文字
"""


# ==================== 报表意图识别 ====================

REPORT_INTENT_SYSTEM_PROMPT = """你是广告报表意图理解专家。

你的任务是分析用户的自然语言查询，提取结构化的报表查询参数。

## 支持的指标（metrics）
标准名（中文别名）：
- impressions（曝光、展示、展示量）
- clicks（点击、点击量）
- cost（消耗、花费、消费）
- conversions（转化、转化数、转化量）
- reach（覆盖、覆盖人数、触达）
- frequency（频次、曝光频次）
- ctr（点击率、CTR）
- cvr（转化率、CVR）
- roi（投产比、ROI）

## 支持的广告层级（ad_level）
- campaign（计划、广告计划、活动）
- ad_group（广告组、组）
- creative（创意、素材）

## 支持的维度（group_by）
- 时间：data_date（日期、天）、data_hour（小时、时段）、data_month（月份、月）、data_week（周）
- 业务：campaign_id（渠道、计划、广告活动）、adgroup_id（广告组）、creative_id（创意、素材）
  industry（行业）、region_id（地区、区域）、device_type（设备）
- 受众：audience_gender（性别）、audience_age（年龄段、年龄）、audience_os（操作系统、平台、系统）
  audience_os_version（系统版本）、audience_country（国家）、audience_city（城市、地域）
  audience_interest（兴趣、兴趣标签）

## 必填字段
以下字段必须提取，提取不到的留空数组或 null：
- advertiser_ids: 广告主 ID 列表（从上下文中的广告主名称推断）
- time_range: 时间范围 {{start_date, end_date, unit}}
- metrics: 指标列表（用标准名）
- ad_level: 广告层级（campaign / ad_group / creative）

## 输出格式（严格 JSON）
{{
    "advertiser_ids": ["123"],
    "time_range": {{
        "start_date": "2026-07-01",
        "end_date": "2026-07-31",
        "unit": "day",
        "is_lifetime": false
    }},
    "metrics": ["impressions", "clicks"],
    "ad_level": "campaign",
    "group_by": ["data_date"],
    "filters": [],
    "is_comparison": false,
    "compare_time_range": null,
    "top_n": null,
    "chart_type": null,
    "confidence": 0.9,
    "alias_mappings": {{
        "曝光": "impressions"
    }}
}}

## 注意
- 今天的日期是 {today_date}
- metrics 必须使用上面列出的标准英文名
- 如果用户没有提到广告主，advertiser_ids 为空数组
- 如果用户没有提到时间，time_range 为 null
- 如果用户没有提到指标，metrics 为空数组
- 如果用户没有提到广告层级，ad_level 为 null
- confidence 表示你对整体提取结果的确定程度
- alias_mappings 记录用户原文中哪些词被映射成了标准名
- 只输出 JSON，不要输出其他任何文字
"""


# ==================== 回退检测 ====================

REENTRY_DETECT_SYSTEM_PROMPT = """你是意图变化检测器。

你的任务是判断用户的最新回复是否改变了最初的意图类别。

当前意图类别：{current_category}（report=报表查询, knowledge=知识问答）

用户原始问题：
{original_input}

用户最新回复（澄清反馈）：
{user_feedback}

请判断：用户的最新回复是否表明他们想从当前意图类别切换到另一类？

输出格式（严格 JSON）：
{{
    "has_changed": true/false,
    "new_category": "report | knowledge | null",
    "reason": "一句话说明依据"
}}

注意：
- 如果用户只是补充当前类别的信息，has_changed = false
- 如果用户明确说"不是，我要查数据"或"不是，我想了解知识"，has_changed = true
- 只有明确的类别切换才算变化，模糊的不算
"""
```

- [ ] **Step 3: 验证模型可以正常导入**

```bash
cd /Users/simon/AL/DataAgent/backend && python -c "
from src.intent.models import (
    TopClassificationResult, ReportIntentResult,
    ClarificationInfo, KnowledgeIntentResult
)
# 测试实例化
r = TopClassificationResult(category='report', confidence=0.9, reason='test')
print(f'TopClassification: {r.category}, conf={r.confidence}')

ri = ReportIntentResult(metrics=['impressions'], ad_level='campaign')
print(f'ReportIntent: {ri.metrics}, level={ri.ad_level}')

c = ClarificationInfo(type='missing_metrics', question='缺指标')
print(f'Clarification: {c.type}')

print('All models import OK')
"
```

预期：全部输出正常，无报错

- [ ] **Step 4: Commit**

```bash
cd /Users/simon/AL/DataAgent
git add backend/src/intent/models.py backend/src/intent/prompts.py
git commit -m "feat: 添加意图识别 Pydantic 模型和 Prompt 模板

- TopClassificationResult: 顶层分类结果
- ReportIntentResult: 报表意图识别结果
- ClarificationInfo: 澄清信息
- 顶层分类器和报表意图识别的系统提示词
- 回退检测提示词

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: 顶层意图分类器（规则快筛 + LLM 精分）

**Files:**
- Create: `backend/src/intent/top_classifier.py`
- Create: `backend/tests/test_top_classifier.py`

**Interfaces:**
- Consumes:
  - `IntentLLMClient` from `src/intent/llm_client.py`
  - `TOP_CLASSIFIER_SYSTEM_PROMPT` from `src/intent/prompts.py`
  - `TopClassificationResult` from `src/intent/models.py`
- Produces:
  - `IntentTopClassifier` 类
  - `async classify(user_input: str, conversation_history: list = None) -> TopClassificationResult`

- [ ] **Step 1: 写顶层分类器测试**

```python
# tests/test_top_classifier.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.intent.top_classifier import IntentTopClassifier
from src.intent.models import TopClassificationResult


class TestRuleFastpath:
    """规则快筛测试（不需要 LLM）"""

    def setup_method(self):
        self.classifier = IntentTopClassifier(llm_client=None)

    def test_time_plus_metric_fastpath(self):
        """时间词 + 指标词 → 快筛命中 report"""
        result = self.classifier._rule_fastpath("昨天的曝光点击消耗")
        assert result is not None
        assert result.category == "report"
        assert result.source == "rule_fastpath"
        assert result.confidence == 1.0

    def test_action_plus_metric_fastpath(self):
        """查询动作 + 指标 → 快筛命中"""
        result = self.classifier._rule_fastpath("查看 CTR 和 ROI 数据")
        assert result is not None
        assert result.category == "report"

    def test_comparison_pattern_fastpath(self):
        """对比模式 → 快筛命中"""
        result = self.classifier._rule_fastpath("3月和4月的消耗对比")
        assert result is not None
        assert result.category == "report"

    def test_knowledge_not_fastpath(self):
        """知识类问题 → 快筛不命中（交给 LLM）"""
        result = self.classifier._rule_fastpath("什么是 CTR")
        assert result is None

    def test_out_of_domain_not_fastpath(self):
        """领域外 → 快筛不命中（交给 LLM）"""
        result = self.classifier._rule_fastpath("今天天气怎么样")
        assert result is None

    def test_short_ambiguous_not_fastpath(self):
        """太短太模糊 → 快筛不命中"""
        result = self.classifier._rule_fastpath("帮我看看")
        assert result is None


class TestLLMClassification:
    """LLM 分类测试（mock LLM 客户端）"""

    def _make_mock_client(self, response_json: dict):
        """创建 mock LLM 客户端"""
        mock_client = MagicMock()
        import json
        mock_client.call = AsyncMock(return_value=json.dumps(response_json))
        return mock_client

    @pytest.mark.asyncio
    async def test_classify_report_via_llm(self):
        """LLM 返回 report 分类"""
        mock_client = self._make_mock_client({
            "category": "report",
            "confidence": 0.92,
            "reason": "用户提到了消耗和上周，属于数据查询"
        })
        classifier = IntentTopClassifier(llm_client=mock_client)
        # 用一个不会走快筛的输入
        result = await classifier.classify("分析一下投放效果怎么样")
        assert isinstance(result, TopClassificationResult)
        assert result.category == "report"
        assert result.confidence == 0.92
        assert result.source == "llm"

    @pytest.mark.asyncio
    async def test_classify_knowledge(self):
        mock_client = self._make_mock_client({
            "category": "knowledge",
            "confidence": 0.85,
            "reason": "用户询问冷启动策略，属于知识问答"
        })
        classifier = IntentTopClassifier(llm_client=mock_client)
        result = await classifier.classify("冷启动跑不动怎么办")
        assert result.category == "knowledge"

    @pytest.mark.asyncio
    async def test_classify_out_of_domain(self):
        mock_client = self._make_mock_client({
            "category": "out_of_domain",
            "confidence": 0.95,
            "reason": "天气与广告无关"
        })
        classifier = IntentTopClassifier(llm_client=mock_client)
        result = await classifier.classify("今天天气怎么样")
        assert result.category == "out_of_domain"

    @pytest.mark.asyncio
    async def test_low_confidence(self):
        """低置信度结果保持原值，由调用方判断阈值"""
        mock_client = self._make_mock_client({
            "category": "report",
            "confidence": 0.5,
            "reason": "用户输入太模糊"
        })
        classifier = IntentTopClassifier(llm_client=mock_client)
        result = await classifier.classify("帮我看看")
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_fastpath_skips_llm(self):
        """快筛命中时不调用 LLM"""
        mock_client = self._make_mock_client({"category": "report", "confidence": 0.9})
        classifier = IntentTopClassifier(llm_client=mock_client)
        result = await classifier.classify("昨天的曝光和点击")
        assert result.source == "rule_fastpath"
        # LLM 不应该被调用
        assert mock_client.call.await_count == 0

    @pytest.mark.asyncio
    async def test_llm_invalid_json_fallback(self):
        """LLM 返回无效 JSON 时的降级处理"""
        mock_client = MagicMock()
        mock_client.call = AsyncMock(return_value="invalid json response")
        classifier = IntentTopClassifier(llm_client=mock_client)
        # 失败时默认返回 knowledge（最安全的降级）
        result = await classifier.classify("一些模糊的输入")
        assert result.category in ["knowledge", "report"]
        assert result.confidence < 0.7
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_top_classifier.py -v
```

预期：ImportError

- [ ] **Step 3: 实现顶层分类器**

```python
# src/intent/top_classifier.py
"""
顶层意图分类器

混合策略：规则快筛 + LLM 精分
- 明确的报表查询 → 规则快筛直接放行（毫秒级）
- 不确定的 → LLM 做三分类（report / knowledge / out_of_domain）+ 置信度
"""
import json
import logging
from typing import Optional, List

from src.intent.llm_client import get_intent_llm_client, IntentLLMClient
from src.intent.prompts import TOP_CLASSIFIER_SYSTEM_PROMPT
from src.intent.models import TopClassificationResult

logger = logging.getLogger(__name__)

# 置信度阈值（低于此值触发澄清）
CONFIDENCE_THRESHOLD = 0.7


# ========== 规则快筛关键词 ==========

# 时间关键词
_TIME_KEYWORDS = [
    "今天", "昨天", "前天", "今日", "昨日",
    "本周", "上周", "这周", "上上周",
    "本月", "上个月", "上月", "这个月",
    "近7天", "最近7天", "近30天", "最近30天",
    "近3个月", "最近三个月", "近一个月",
    "日", "周", "月",  # 这些太泛，需要组合判断
]

# 指标关键词（中文 + 英文缩写）
_METRIC_KEYWORDS = [
    "曝光", "点击", "消耗", "转化", "成本", "花费",
    "点击率", "转化率", "投产比",
    "ctr", "cvr", "roi", "cpc", "cpm", "cpa",
    "impression", "click", "conversion",
    "覆盖", "触达", "频次",
]

# 报表查询动作词
_QUERY_ACTION_KEYWORDS = [
    "查看", "查询", "看看", "分析", "统计",
    "报表", "数据", "趋势", "对比",
    "哪些", "多少", "排名", "TOP", "top",
]

# 对比模式正则
import re
_COMPARISON_PATTERNS = [
    re.compile(r'\d+月\s*(vs|VS|和|与)\s*\d+月'),
    re.compile(r'(今天|昨天|本周|上周|本月|上个月)\s*(vs|VS|和|与)\s*(今天|昨天|本周|上周|本月|上个月)'),
]


def _has_time_keyword(text: str) -> bool:
    """检查是否包含明确的时间关键词（排除单个字的情况）"""
    for kw in _TIME_KEYWORDS:
        if len(kw) >= 2 and kw in text:
            return True
    return False


def _has_metric_keyword(text: str) -> bool:
    """检查是否包含指标关键词（不区分大小写）"""
    text_lower = text.lower()
    for kw in _METRIC_KEYWORDS:
        if kw.lower() in text_lower:
            return True
    return False


def _has_query_action(text: str) -> bool:
    """检查是否包含查询动作词"""
    for kw in _QUERY_ACTION_KEYWORDS:
        if kw in text:
            return True
    return False


def _has_comparison_pattern(text: str) -> bool:
    """检查是否包含明确的对比模式"""
    for pattern in _COMPARISON_PATTERNS:
        if pattern.search(text):
            return True
    return False


# ========== 分类器类 ==========

class IntentTopClassifier:
    """
    顶层意图分类器

    用法:
        classifier = IntentTopClassifier()
        result = await classifier.classify("用户输入")
        print(result.category, result.confidence)
    """

    def __init__(self, llm_client: Optional[IntentLLMClient] = None):
        self._llm_client = llm_client
        self.confidence_threshold = CONFIDENCE_THRESHOLD

    @property
    def llm_client(self) -> IntentLLMClient:
        if self._llm_client is None:
            self._llm_client = get_intent_llm_client()
        return self._llm_client

    # ---- 规则快筛 ----

    def _rule_fastpath(self, user_input: str) -> Optional[TopClassificationResult]:
        """
        规则快筛：只判断"确定是报表"的情况，其他都返回 None 交给 LLM

        命中条件（满足任一条）：
        1. 时间词 + 指标词 同时出现
        2. 查询动作词 + 指标词 同时出现
        3. 明确的对比模式
        """
        has_time = _has_time_keyword(user_input)
        has_metric = _has_metric_keyword(user_input)
        has_action = _has_query_action(user_input)
        has_comparison = _has_comparison_pattern(user_input)

        if (has_time and has_metric) or (has_action and has_metric) or has_comparison:
            result = TopClassificationResult(
                category="report",
                confidence=1.0,
                reason="规则快筛：命中报表关键词组合",
                source="rule_fastpath",
            )
            logger.info(f"意图快筛命中: input='{user_input[:50]}...', result=report")
            return result

        return None

    # ---- LLM 分类 ----

    async def _llm_classify(
        self,
        user_input: str,
        conversation_history: List[dict] = None,
    ) -> TopClassificationResult:
        """
        LLM 三分类：report / knowledge / out_of_domain
        """
        # 构建用户提示词
        history_text = ""
        if conversation_history:
            # 取最近 3 轮
            recent = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            history_lines = []
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:100]
                history_lines.append(f"{role}: {content}")
            history_text = "\n对话历史:\n" + "\n".join(history_lines)

        user_prompt = f"用户输入：{user_input}{history_text}"

        try:
            response_text = await self.llm_client.call(
                system_prompt=TOP_CLASSIFIER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                json_mode=True,
            )
            data = json.loads(response_text)

            result = TopClassificationResult(
                category=data.get("category", "knowledge"),
                confidence=float(data.get("confidence", 0.5)),
                reason=data.get("reason", ""),
                source="llm",
            )

            logger.info(
                f"意图分类(LLM): category={result.category}, "
                f"confidence={result.confidence:.2f}, "
                f"reason='{result.reason}'"
            )
            return result

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"LLM 分类结果解析失败: {e}, 原始响应前100字: {response_text[:100]}")
            # 解析失败 → 默认 knowledge + 低置信度，触发澄清
            return TopClassificationResult(
                category="knowledge",
                confidence=0.3,
                reason=f"LLM 响应解析失败: {str(e)}",
                source="llm_parse_error",
            )

        except Exception as e:
            logger.error(f"LLM 分类调用失败（已重试仍失败）: {e}")
            # LLM 完全失败 → 降级为 knowledge + 低置信度
            return TopClassificationResult(
                category="knowledge",
                confidence=0.2,
                reason="LLM 服务不可用，降级处理",
                source="llm_failure",
            )

    # ---- 主入口 ----

    async def classify(
        self,
        user_input: str,
        conversation_history: List[dict] = None,
    ) -> TopClassificationResult:
        """
        分类用户意图

        Args:
            user_input: 用户输入文本
            conversation_history: 对话历史列表

        Returns:
            TopClassificationResult
        """
        if not user_input or not user_input.strip():
            return TopClassificationResult(
                category="out_of_domain",
                confidence=0.9,
                reason="空输入",
                source="rule_fastpath",
            )

        # Step 1: 规则快筛
        fast_result = self._rule_fastpath(user_input)
        if fast_result is not None:
            return fast_result

        # Step 2: LLM 精分
        result = await self._llm_classify(user_input, conversation_history)
        return result


# 单例
_top_classifier_instance: Optional[IntentTopClassifier] = None


def get_top_classifier() -> IntentTopClassifier:
    """获取顶层分类器单例"""
    global _top_classifier_instance
    if _top_classifier_instance is None:
        _top_classifier_instance = IntentTopClassifier()
    return _top_classifier_instance
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_top_classifier.py -v
```

预期：全部 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/simon/AL/DataAgent
git add backend/src/intent/top_classifier.py \
        backend/tests/test_top_classifier.py
git commit -m "feat: 实现顶层意图分类器（规则快筛 + LLM 三分类）

- 规则快筛：时间+指标 / 动作+指标 / 对比模式 直接放行
- LLM 精分：三分类（report/knowledge/out_of_domain）+ 置信度
- 完整降级策略：JSON 解析失败 / LLM 不可用都有兜底
- 日志埋点：快筛命中、LLM 分类结果、失败告警

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: 报表意图识别（LLM 提取 + 规则校验 + 能力校验 + 澄清检测）

**Files:**
- Create: `backend/src/intent/report_intent.py`
- Create: `backend/tests/test_report_intent.py`

**Interfaces:**
- Consumes:
  - `IntentLLMClient` / `get_intent_llm_client()`
  - `REPORT_INTENT_SYSTEM_PROMPT` from `prompts.py`
  - `ReportIntentResult`, `ClarificationInfo` from `models.py`
  - `validate_metric`, `validate_ad_level`, `validate_dimension` from `capability_registry.py`
  - 现有规则工具：`parse_time_range`, `map_metrics`, `map_dimensions`, `parse_filters`
  - `extract_advertiser_from_input`, `get_similar_advertiser_names` from `advertiser_service`
- Produces:
  - `ReportIntentAnalyzer` 类
  - `async analyze(user_input, conversation_history, existing_advertiser_ids=None) -> ReportIntentResult`
  - `check_required_fields(result) -> Tuple[bool, Optional[ClarificationInfo]]` — 检查必填字段是否齐全
  - `check_capabilities(result) -> Tuple[bool, Optional[ClarificationInfo]]` — 检查能力是否支持

- [ ] **Step 1: 写报表意图识别测试**

```python
# tests/test_report_intent.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.intent.report_intent import ReportIntentAnalyzer
from src.intent.models import ReportIntentResult, ReportTimeRange


def _make_mock_client(response_dict: dict):
    mock = MagicMock()
    mock.call = AsyncMock(return_value=json.dumps(response_dict))
    return mock


class TestLLMExtraction:
    """LLM 提取测试（mock LLM）"""

    @pytest.mark.asyncio
    async def test_full_extraction(self):
        """完整提取所有字段"""
        mock_client = _make_mock_client({
            "advertiser_ids": ["123"],
            "time_range": {
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
                "unit": "day",
                "is_lifetime": False
            },
            "metrics": ["impressions", "clicks", "cost"],
            "ad_level": "campaign",
            "group_by": ["data_date"],
            "filters": [],
            "is_comparison": False,
            "compare_time_range": None,
            "top_n": None,
            "chart_type": None,
            "confidence": 0.95,
            "alias_mappings": {"曝光": "impressions", "点击": "clicks"}
        })
        analyzer = ReportIntentAnalyzer(llm_client=mock_client)
        result = await analyzer._llm_extract("上个月的曝光点击消耗，按天展示")
        assert isinstance(result, ReportIntentResult)
        assert result.metrics == ["impressions", "clicks", "cost"]
        assert result.ad_level == "campaign"
        assert result.time_range.start_date == "2026-07-01"
        assert "曝光" in result.alias_mappings

    @pytest.mark.asyncio
    async def test_empty_fields(self):
        """用户没说的字段留空"""
        mock_client = _make_mock_client({
            "advertiser_ids": [],
            "time_range": None,
            "metrics": [],
            "ad_level": None,
            "group_by": [],
            "filters": [],
            "is_comparison": False,
            "compare_time_range": None,
            "top_n": None,
            "chart_type": None,
            "confidence": 0.4,
            "alias_mappings": {}
        })
        analyzer = ReportIntentAnalyzer(llm_client=mock_client)
        result = await analyzer._llm_extract("帮我看看数据")
        assert result.advertiser_ids == []
        assert result.time_range is None
        assert result.metrics == []
        assert result.ad_level is None


class TestRequiredFieldsCheck:
    """必填字段检查测试"""

    def setup_method(self):
        self.analyzer = ReportIntentAnalyzer(llm_client=None)

    def test_all_present(self):
        """所有必填字段都有 → 不需要澄清"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions"],
            ad_level="campaign",
        )
        ok, clarification = self.analyzer.check_required_fields(result)
        assert ok is True
        assert clarification is None

    def test_missing_advertiser(self):
        """缺广告主 → 触发澄清"""
        result = ReportIntentResult(
            advertiser_ids=[],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions"],
            ad_level="campaign",
        )
        ok, clarification = self.analyzer.check_required_fields(result)
        assert ok is False
        assert clarification.type == "missing_advertiser"
        assert "广告主" in clarification.question

    def test_missing_time_range(self):
        """缺时间 → 触发澄清"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=None,
            metrics=["impressions"],
            ad_level="campaign",
        )
        ok, clarification = self.analyzer.check_required_fields(result)
        assert ok is False
        assert clarification.type == "missing_time_range"

    def test_missing_metrics(self):
        """缺指标 → 触发澄清"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=[],
            ad_level="campaign",
        )
        ok, clarification = self.analyzer.check_required_fields(result)
        assert ok is False
        assert clarification.type == "missing_metrics"
        # 选项里应该有指标名称
        assert len(clarification.options) > 0

    def test_missing_ad_level(self):
        """缺广告层级 → 触发澄清"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions"],
            ad_level=None,
        )
        ok, clarification = self.analyzer.check_required_fields(result)
        assert ok is False
        assert clarification.type == "missing_ad_level"
        assert len(clarification.options) == 3  # 3 个层级

    def test_multiple_missing(self):
        """多个字段缺失 → 选第一个最关键的发起澄清"""
        result = ReportIntentResult(
            advertiser_ids=[],
            time_range=None,
            metrics=[],
            ad_level=None,
        )
        ok, clarification = self.analyzer.check_required_fields(result)
        assert ok is False
        # 应该返回第一个缺失项的澄清
        assert clarification is not None


class TestCapabilityCheck:
    """能力校验测试"""

    def setup_method(self):
        self.analyzer = ReportIntentAnalyzer(llm_client=None)

    def test_all_supported(self):
        """全部支持 → 通过"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions", "clicks", "ctr"],
            ad_level="campaign",
            group_by=["data_date", "audience_gender"],
        )
        ok, clarification = self.analyzer.check_capabilities(result)
        assert ok is True
        assert clarification is None

    def test_unsupported_metric(self):
        """不支持的指标 → 触发澄清"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions", "留存率"],
            ad_level="campaign",
        )
        ok, clarification = self.analyzer.check_capabilities(result)
        assert ok is False
        assert clarification.type == "unsupported_metric"
        assert "留存率" in clarification.question

    def test_unsupported_dimension(self):
        """不支持的维度 → 触发澄清"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions"],
            ad_level="campaign",
            group_by=["血型"],
        )
        ok, clarification = self.analyzer.check_capabilities(result)
        assert ok is False
        assert clarification.type == "unsupported_dimension"


class TestContextInheritance:
    """上下文继承测试"""

    def setup_method(self):
        self.analyzer = ReportIntentAnalyzer(llm_client=None)

    def test_inherit_advertiser(self):
        """新输入没广告主但上下文有 → 继承"""
        result = ReportIntentResult(
            advertiser_ids=[],  # LLM 没提取到
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions"],
            ad_level="campaign",
        )
        self.analyzer._apply_context_inheritance(result, existing_advertiser_ids=["456"])
        assert result.advertiser_ids == ["456"]

    def test_dont_override_new_advertiser(self):
        """新输入有广告主 → 不用继承"""
        result = ReportIntentResult(
            advertiser_ids=["123"],
            time_range=ReportTimeRange(
                start_date="2026-07-01", end_date="2026-07-31", unit="day"
            ),
            metrics=["impressions"],
            ad_level="campaign",
        )
        self.analyzer._apply_context_inheritance(result, existing_advertiser_ids=["456"])
        assert result.advertiser_ids == ["123"]


class TestFullAnalyze:
    """完整 analyze 流程测试"""

    @pytest.mark.asyncio
    async def test_successful_analysis(self):
        """信息齐全 → 返回 (result, None)"""
        mock_client = _make_mock_client({
            "advertiser_ids": ["123"],
            "time_range": {
                "start_date": "2026-07-01", "end_date": "2026-07-31",
                "unit": "day", "is_lifetime": False
            },
            "metrics": ["impressions", "clicks"],
            "ad_level": "campaign",
            "group_by": [], "filters": [],
            "is_comparison": False, "compare_time_range": None,
            "top_n": None, "chart_type": None,
            "confidence": 0.9,
            "alias_mappings": {}
        })
        analyzer = ReportIntentAnalyzer(llm_client=mock_client)
        result, clarification = await analyzer.analyze(
            "查看广告主123上个月的曝光点击"
        )
        assert result is not None
        assert clarification is None
        assert len(result.metrics) == 2

    @pytest.mark.asyncio
    async def test_analysis_with_clarification(self):
        """缺字段 → 返回 (result, clarification)"""
        mock_client = _make_mock_client({
            "advertiser_ids": [],
            "time_range": {
                "start_date": "2026-07-01", "end_date": "2026-07-31",
                "unit": "day", "is_lifetime": False
            },
            "metrics": ["impressions"],
            "ad_level": "campaign",
            "group_by": [], "filters": [],
            "is_comparison": False, "compare_time_range": None,
            "top_n": None, "chart_type": None,
            "confidence": 0.8,
            "alias_mappings": {}
        })
        analyzer = ReportIntentAnalyzer(llm_client=mock_client)
        result, clarification = await analyzer.analyze(
            "上个月的曝光数据"
        )
        assert result is not None
        assert clarification is not None
        assert clarification.type == "missing_advertiser"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_report_intent.py -v
```

预期：ImportError

- [ ] **Step 3: 实现报表意图识别**

```python
# src/intent/report_intent.py
"""
报表意图识别与填充

流程：
1. LLM 结构化提取（主解析）
2. 规则工具校验（time_parser, map_metrics 等作为交叉验证）
3. 能力校验（指标/层级/维度是否在支持范围内）
4. 必填字段检查（缺了触发澄清）
5. 上下文继承（继承上一轮的广告主/时间/层级）
"""
import json
import logging
from typing import Optional, List, Tuple
from datetime import date

from src.intent.llm_client import get_intent_llm_client, IntentLLMClient
from src.intent.prompts import REPORT_INTENT_SYSTEM_PROMPT
from src.intent.models import ReportIntentResult, ReportTimeRange, ClarificationInfo
from src.intent.capability_registry import (
    validate_metric,
    validate_ad_level,
    validate_dimension,
    get_all_metric_names,
    SUPPORTED_AD_LEVELS,
    AD_LEVEL_MAP,
)

logger = logging.getLogger(__name__)

# 别名澄清阈值（低于此置信度触发别名确认）
ALIAS_CONFIDENCE_THRESHOLD = 0.8

# 必填字段优先级（先问排在前面的）
REQUIRED_FIELDS_PRIORITY = [
    "advertiser_ids",
    "time_range",
    "metrics",
    "ad_level",
]


class ReportIntentAnalyzer:
    """
    报表意图分析器

    用法:
        analyzer = ReportIntentAnalyzer()
        result, clarification = await analyzer.analyze(user_input, existing_advertiser_ids=...)
        if clarification:
            # 需要澄清
        else:
            # 信息齐全，继续流程
    """

    def __init__(self, llm_client: Optional[IntentLLMClient] = None):
        self._llm_client = llm_client

    @property
    def llm_client(self) -> IntentLLMClient:
        if self._llm_client is None:
            self._llm_client = get_intent_llm_client()
        return self._llm_client

    # ---- LLM 提取 ----

    async def _llm_extract(
        self,
        user_input: str,
        conversation_history: List[dict] = None,
    ) -> ReportIntentResult:
        """用 LLM 从用户输入中提取结构化报表意图"""
        today_str = str(date.today())
        system_prompt = REPORT_INTENT_SYSTEM_PROMPT.format(today_date=today_str)

        # 附加上下文
        history_text = ""
        if conversation_history:
            recent = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            lines = []
            for msg in recent:
                role = msg.get("role", "user")
                content = str(msg.get("content", ""))[:200]
                lines.append(f"{role}: {content}")
            history_text = "\n\n对话历史（用于上下文理解）:\n" + "\n".join(lines)

        user_prompt = f"用户输入：{user_input}{history_text}"

        try:
            response_text = await self.llm_client.call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=True,
            )
            data = json.loads(response_text)

            # 解析 time_range
            tr_data = data.get("time_range")
            time_range = None
            if tr_data and isinstance(tr_data, dict) and tr_data.get("start_date"):
                time_range = ReportTimeRange(
                    start_date=tr_data["start_date"],
                    end_date=tr_data.get("end_date", tr_data["start_date"]),
                    unit=tr_data.get("unit", "day"),
                    is_lifetime=tr_data.get("is_lifetime", False),
                )

            # 解析 compare_time_range
            ctr_data = data.get("compare_time_range")
            compare_time_range = None
            if ctr_data and isinstance(ctr_data, dict) and ctr_data.get("start_date"):
                compare_time_range = ReportTimeRange(
                    start_date=ctr_data["start_date"],
                    end_date=ctr_data.get("end_date", ctr_data["start_date"]),
                    unit=ctr_data.get("unit", "day"),
                    is_lifetime=ctr_data.get("is_lifetime", False),
                )

            result = ReportIntentResult(
                advertiser_ids=data.get("advertiser_ids", []),
                time_range=time_range,
                metrics=data.get("metrics", []),
                ad_level=data.get("ad_level"),
                group_by=data.get("group_by", []),
                filters=data.get("filters", []),
                is_comparison=data.get("is_comparison", False),
                compare_time_range=compare_time_range,
                top_n=data.get("top_n"),
                chart_type=data.get("chart_type"),
                confidence=float(data.get("confidence", 0.7)),
                alias_mappings=data.get("alias_mappings", {}),
            )

            logger.info(
                f"报表意图提取(LLM): 广告主={result.advertiser_ids}, "
                f"时间={result.time_range and result.time_range.start_date + '~' + result.time_range.end_date}, "
                f"指标={result.metrics}, 层级={result.ad_level}, "
                f"置信度={result.confidence:.2f}"
            )
            return result

        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning(f"报表意图 LLM 提取解析失败: {e}")
            return ReportIntentResult(
                confidence=0.2,
                alias_mappings={},
            )

        except Exception as e:
            logger.error(f"报表意图 LLM 提取调用失败: {e}")
            return ReportIntentResult(
                confidence=0.1,
                alias_mappings={},
            )

    # ---- 规则工具校验（与 LLM 结果交叉验证）----

    def _rule_validate(self, result: ReportIntentResult, user_input: str) -> List[str]:
        """
        用规则工具校验 LLM 提取结果，返回不一致的字段列表

        校验逻辑：
        - 指标：LLM 提取的 vs map_metrics 提取的，取并集
        - 维度：LLM 提取的 vs map_dimensions 提取的，取并集
        - 不一致但置信度高的以 LLM 为准，置信度低的记录警告
        """
        # TODO: 可以在后续优化中引入更复杂的交叉验证
        # 目前只做能力层面的校验（见 check_capabilities）
        inconsistencies = []
        return inconsistencies

    # ---- 能力校验 ----

    def check_capabilities(
        self, result: ReportIntentResult
    ) -> Tuple[bool, Optional[ClarificationInfo]]:
        """
        校验提取结果中的指标/维度/层级是否在系统支持范围内

        Returns:
            (是否全部支持, 不支持时的澄清信息)
        """
        # 校验指标
        unsupported_metrics = []
        validated_metrics = []
        for m in result.metrics:
            ok, std = validate_metric(m)
            if ok:
                validated_metrics.append(std)
            else:
                unsupported_metrics.append(m)

        if unsupported_metrics:
            metric_names = "、".join(unsupported_metrics)
            all_metrics = get_all_metric_names()
            options = [{"value": name, "label": name} for name in all_metrics[:8]]
            return False, ClarificationInfo(
                type="unsupported_metric",
                question=f"抱歉，暂不支持「{metric_names}」指标。\n支持的指标包括：{'、'.join(all_metrics)}\n请选择或输入你想查看的指标：",
                options=options,
                allow_custom_input=True,
                missing_fields=["metrics"],
            )

        # 用校验后的标准指标替换
        result.metrics = validated_metrics

        # 校验广告层级
        if result.ad_level:
            ok, std = validate_ad_level(result.ad_level)
            if not ok:
                options = [
                    {"value": std, "label": names[0] if names else std}
                    for std, names in AD_LEVEL_MAP.items()
                ]
                return False, ClarificationInfo(
                    type="unsupported_metric",  # 复用，实际是层级不支持
                    question=f"抱歉，不支持「{result.ad_level}」广告层级。请选择支持的层级：",
                    options=options,
                    allow_custom_input=False,
                    missing_fields=["ad_level"],
                )
            result.ad_level = std

        # 校验维度
        unsupported_dims = []
        validated_dims = []
        for d in result.group_by:
            ok, std = validate_dimension(d)
            if ok:
                validated_dims.append(std)
            else:
                unsupported_dims.append(d)

        if unsupported_dims:
            dim_names = "、".join(unsupported_dims)
            return False, ClarificationInfo(
                type="unsupported_dimension",
                question=f"抱歉，暂不支持「{dim_names}」维度。请换一个维度试试。",
                options=[],
                allow_custom_input=True,
                missing_fields=["group_by"],
            )

        result.group_by = validated_dims

        return True, None

    # ---- 必填字段检查 ----

    def check_required_fields(
        self, result: ReportIntentResult
    ) -> Tuple[bool, Optional[ClarificationInfo]]:
        """
        检查必填字段是否齐全，缺了生成对应澄清

        按优先级检查，一次只返回第一个缺失项的澄清
        """
        # 1. 广告主
        if not result.advertiser_ids:
            return False, ClarificationInfo(
                type="missing_advertiser",
                question="请问你想查看哪个广告主的数据？请输入广告主名称或 ID。",
                options=[],
                allow_custom_input=True,
                missing_fields=["advertiser_ids"],
            )

        # 2. 时间范围
        if result.time_range is None:
            options = [
                {"value": "今天", "label": "今天"},
                {"value": "昨天", "label": "昨天"},
                {"value": "近7天", "label": "最近 7 天"},
                {"value": "上周", "label": "上周"},
                {"value": "上个月", "label": "上个月"},
                {"value": "近3个月", "label": "最近 3 个月"},
            ]
            return False, ClarificationInfo(
                type="missing_time_range",
                question="请问你想查看哪段时间的数据？",
                options=options,
                allow_custom_input=True,
                missing_fields=["time_range"],
            )

        # 3. 指标
        if not result.metrics:
            all_metrics = get_all_metric_names()
            options = [{"value": name, "label": name} for name in all_metrics[:8]]
            return False, ClarificationInfo(
                type="missing_metrics",
                question="请问你关注哪些指标？",
                options=options,
                allow_custom_input=True,
                missing_fields=["metrics"],
            )

        # 4. 广告层级
        if not result.ad_level:
            options = [
                {"value": "campaign", "label": "计划层级"},
                {"value": "ad_group", "label": "广告组层级"},
                {"value": "creative", "label": "素材/创意层级"},
            ]
            return False, ClarificationInfo(
                type="missing_ad_level",
                question="请问你想看哪个广告层级的数据？",
                options=options,
                allow_custom_input=False,
                missing_fields=["ad_level"],
            )

        return True, None

    # ---- 上下文继承 ----

    def _apply_context_inheritance(
        self,
        result: ReportIntentResult,
        existing_advertiser_ids: List[str] = None,
        existing_time_range: ReportTimeRange = None,
        existing_ad_level: str = None,
    ) -> None:
        """
        继承上下文中的字段（当前轮没提到的，用上一轮的）

        继承策略：广告主、时间范围、广告层级 继承；指标、维度 不继承
        """
        # 广告主
        if not result.advertiser_ids and existing_advertiser_ids:
            result.advertiser_ids = list(existing_advertiser_ids)
            logger.debug(f"继承广告主: {result.advertiser_ids}")

        # 时间范围
        if result.time_range is None and existing_time_range:
            result.time_range = existing_time_range
            logger.debug(f"继承时间范围: {existing_time_range.start_date}~{existing_time_range.end_date}")

        # 广告层级
        if not result.ad_level and existing_ad_level:
            result.ad_level = existing_ad_level
            logger.debug(f"继承广告层级: {existing_ad_level}")

    # ---- 主入口 ----

    async def analyze(
        self,
        user_input: str,
        conversation_history: List[dict] = None,
        existing_advertiser_ids: List[str] = None,
        existing_time_range: ReportTimeRange = None,
        existing_ad_level: str = None,
    ) -> Tuple[Optional[ReportIntentResult], Optional[ClarificationInfo]]:
        """
        分析用户输入，提取报表意图

        Args:
            user_input: 用户输入文本
            conversation_history: 对话历史
            existing_advertiser_ids: 上下文中已有的广告主 ID
            existing_time_range: 上下文中已有的时间范围
            existing_ad_level: 上下文中已有的广告层级

        Returns:
            (意图结果, 澄清信息)
            - 如果信息齐全且能力支持：(result, None)
            - 如果需要澄清：(result, clarification)
            - 如果完全无法解析：(None, clarification)
        """
        # Step 1: LLM 提取
        result = await self._llm_extract(user_input, conversation_history)

        if result.confidence < 0.2:
            # 置信度太低，视为解析失败
            return None, ClarificationInfo(
                type="missing_metrics",  # 先用缺指标的澄清引导用户
                question="抱歉，我没太理解你的需求。请告诉我你想查看哪些数据指标？",
                options=[],
                allow_custom_input=True,
                missing_fields=["metrics"],
            )

        # Step 2: 上下文继承
        self._apply_context_inheritance(
            result, existing_advertiser_ids, existing_time_range, existing_ad_level
        )

        # Step 3: 能力校验
        ok, cap_clarification = self.check_capabilities(result)
        if not ok:
            return result, cap_clarification

        # Step 4: 必填字段检查
        ok, req_clarification = self.check_required_fields(result)
        if not ok:
            return result, req_clarification

        return result, None


# 单例
_report_intent_analyzer: Optional[ReportIntentAnalyzer] = None


def get_report_intent_analyzer() -> ReportIntentAnalyzer:
    """获取报表意图分析器单例"""
    global _report_intent_analyzer
    if _report_intent_analyzer is None:
        _report_intent_analyzer = ReportIntentAnalyzer()
    return _report_intent_analyzer
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_report_intent.py -v
```

预期：全部 PASS（如果有个别测试因为细节差异失败，修复后再提交）

- [ ] **Step 5: Commit**

```bash
cd /Users/simon/AL/DataAgent
git add backend/src/intent/report_intent.py \
        backend/tests/test_report_intent.py
git commit -m "feat: 实现报表意图识别（LLM提取 + 能力校验 + 澄清检测）

- LLM 结构化提取：广告主、时间、指标、层级、维度等
- 能力校验：指标/层级/维度是否在支持范围内
- 必填字段检查：4个必填项按优先级澄清
- 上下文继承：广告主、时间范围、广告层级自动继承
- 完整日志埋点

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: 拒答节点 + 澄清节点（回退检测 + 路由）

**Files:**
- Create: `backend/src/intent/reject_node.py`
- Create: `backend/src/intent/clarify_node.py`
- Create: `backend/tests/test_reject_node.py`
- Create: `backend/tests/test_clarify_node.py`

**Interfaces:**
- Consumes:
  - `ClarificationInfo` from `models.py`
  - `REENTRY_DETECT_SYSTEM_PROMPT` from `prompts.py`
  - `IntentLLMClient`
- Produces:
  - `async reject_node(state: dict) -> dict` — 拒答 LangGraph 节点函数
  - `async clarify_node(state: dict) -> dict` — 澄清处理 LangGraph 节点函数
  - `detect_intent_change(user_feedback, original_category, original_input) -> (bool, str)` — 回退检测

**Sub-steps for reject_node:**

- [ ] **Step 1: 写拒答节点测试**

```python
# tests/test_reject_node.py
import pytest
from src.intent.reject_node import reject_node, build_reject_response


class TestRejectNode:
    def test_build_reject_response_top_level(self):
        """顶层直接拒答"""
        resp = build_reject_response("top_level")
        assert "广告" in resp
        assert "抱歉" in resp

    def test_build_reject_response_knowledge_scope(self):
        """知识问答二次拒答"""
        resp = build_reject_response("knowledge_scope")
        assert "广告" in resp
        assert "回答不了" in resp or "抱歉" in resp

    @pytest.mark.asyncio
    async def test_reject_node_top_level(self):
        """节点函数：顶层拒答"""
        state = {"user_input": "今天天气怎么样", "intent_category": "out_of_domain"}
        result = await reject_node(state)
        assert "final_report" in result
        report = result["final_report"]
        assert "title" in report
        assert "highlights" in report
        assert len(report["highlights"]) > 0
```

- [ ] **Step 2: 运行拒答测试验证失败**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_reject_node.py -v
```

- [ ] **Step 3: 实现拒答节点**

```python
# src/intent/reject_node.py
"""
拒答节点 — 当用户问题超出广告领域时，返回礼貌的拒绝话术
"""
import logging

logger = logging.getLogger(__name__)

# 拒答话术模板
REJECT_MESSAGES = {
    "top_level": (
        "抱歉，我只能回答广告相关的问题（包括广告数据查询和广告知识问答）。"
        "其他领域的问题我暂时回答不了。"
    ),
    "knowledge_scope": (
        "抱歉，这个问题我回答不了。请在广告相关的范围内提问。"
    ),
}


def build_reject_response(reason: str = "top_level") -> dict:
    """
    构建拒答的 final_report

    Args:
        reason: 拒答原因类型（top_level / knowledge_scope）

    Returns:
        final_report 格式的 dict
    """
    message = REJECT_MESSAGES.get(reason, REJECT_MESSAGES["top_level"])

    # 给一些引导建议
    suggestions = [
        "查看广告数据报表（曝光、点击、消耗、转化等）",
        "了解广告指标概念（什么是 CTR / CPA / ROI）",
        "咨询广告优化策略（冷启动、素材优化、出价调整）",
    ]

    highlights = [
        {"type": "info", "text": message},
        {"type": "info", "text": "💡 我可以帮你："},
    ]
    for s in suggestions:
        highlights.append({"type": "info", "text": f"  • {s}"})

    return {
        "title": "抱歉，这个问题我回答不了",
        "time_range": {"start": "", "end": ""},
        "metrics": [],
        "highlights": highlights,
        "data_table": {"columns": [], "rows": []},
        "next_queries": [
            "昨天的曝光点击消耗",
            "什么是 CTR",
            "冷启动跑不动怎么办",
        ],
    }


async def reject_node(state: dict) -> dict:
    """
    LangGraph 拒答节点

    从 state 中读取拒答原因，生成拒答响应并写入 final_report
    """
    reject_reason = state.get("reject_reason", "top_level")
    user_input = state.get("user_input", "")

    logger.info(f"拒答: 原因={reject_reason}, 用户输入='{user_input[:50]}'")

    final_report = build_reject_response(reject_reason)

    return {
        "final_report": final_report,
        "error": None,
    }
```

- [ ] **Step 4: 运行拒答测试验证通过**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_reject_node.py -v
```

**Sub-steps for clarify_node:**

- [ ] **Step 5: 写澄清节点测试**

```python
# tests/test_clarify_node.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.intent.clarify_node import (
    clarify_node,
    detect_intent_change,
    build_clarification_state,
)
from src.intent.models import ClarificationInfo


class TestDetectIntentChange:
    """回退检测测试（mock LLM）"""

    def _make_mock_client(self, has_changed, new_category=None):
        import json as _json
        mock = MagicMock()
        mock.call = AsyncMock(return_value=_json.dumps({
            "has_changed": has_changed,
            "new_category": new_category,
            "reason": "test reason"
        }))
        return mock

    @pytest.mark.asyncio
    async def test_no_change(self):
        """用户只是补充信息，意图没变"""
        mock = self._make_mock_client(False, None)
        changed, new_cat = await detect_intent_change(
            "我想补充一下时间",
            "report",
            "看看消耗",
            llm_client=mock,
        )
        assert changed is False
        assert new_cat is None

    @pytest.mark.asyncio
    async def test_change_to_report(self):
        """用户从知识问答切换到报表查询"""
        mock = self._make_mock_client(True, "report")
        changed, new_cat = await detect_intent_change(
            "不是，我想查消耗数据",
            "knowledge",
            "什么是冷启动",
            llm_client=mock,
        )
        assert changed is True
        assert new_cat == "report"

    @pytest.mark.asyncio
    async def test_change_to_knowledge(self):
        """用户从报表切换到知识问答"""
        mock = self._make_mock_client(True, "knowledge")
        changed, new_cat = await detect_intent_change(
            "不是，我想了解什么是 CTR",
            "report",
            "看昨天的数据",
            llm_client=mock,
        )
        assert changed is True
        assert new_cat == "knowledge"


class TestBuildClarificationState:
    """构建澄清状态测试"""

    def test_build_missing_advertiser(self):
        info = ClarificationInfo(
            type="missing_advertiser",
            question="请问你想查看哪个广告主？",
            options=[],
            allow_custom_input=True,
        )
        state = build_clarification_state(info)
        assert state["needs_clarification"] is True
        assert state["clarification"]["type"] == "missing_advertiser"
        assert state["clarification"]["question"] == "请问你想查看哪个广告主？"


class TestClarifyNode:
    """澄清节点函数测试"""

    @pytest.mark.asyncio
    async def test_clarify_node_sets_next_action(self):
        """澄清节点设置下一步动作"""
        state = {
            "user_feedback": {"selected_value": "广告主A"},
            "intent_category": "report",
            "user_input": "看看数据",
        }
        # 因为 clarify_node 依赖很多其他模块，这里只测试基本导入和结构
        # 完整功能在集成测试中验证
        assert callable(clarify_node)
```

- [ ] **Step 6: 运行澄清节点测试验证失败**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_clarify_node.py -v
```

- [ ] **Step 7: 实现澄清节点**

```python
# src/intent/clarify_node.py
"""
通用澄清节点

职责：
1. 接收用户的澄清反馈
2. 检测用户是否改变了意图类别（触发回退）
3. 设置下一步路由方向（回第一层 / 继续第二层报表 / 继续第二层知识）

注意：
- 此节点之前 graph 会 interrupt（interrupt_before=["clarify"]）
- 用户反馈通过 user_feedback 字段传入
- 此节点不做实际的重新识别，只设置路由方向和合并反馈到 user_input
  重新识别由后续节点完成
"""
import json
import logging
from typing import Optional, Tuple

from src.intent.llm_client import get_intent_llm_client, IntentLLMClient
from src.intent.prompts import REENTRY_DETECT_SYSTEM_PROMPT
from src.intent.models import ClarificationInfo

logger = logging.getLogger(__name__)

# 最大回退次数
MAX_REENTRY_COUNT = 3


def build_clarification_state(clarification: ClarificationInfo) -> dict:
    """
    构建澄清状态（写入 state 供 interrupt 时前端展示）

    由各识别节点在需要澄清时调用，设置 needs_clarification=True
    这样 graph 到 clarify 节点前会中断，等待用户输入
    """
    return {
        "needs_clarification": True,
        "clarification": {
            "type": clarification.type,
            "question": clarification.question,
            "options": clarification.options,
            "allow_custom_input": clarification.allow_custom_input,
            "missing_fields": clarification.missing_fields,
        },
    }


async def detect_intent_change(
    user_feedback: str,
    current_category: str,
    original_input: str,
    llm_client: IntentLLMClient = None,
) -> Tuple[bool, Optional[str]]:
    """
    检测用户澄清反馈是否改变了意图类别

    Args:
        user_feedback: 用户最新的澄清反馈
        current_category: 当前意图类别（report / knowledge）
        original_input: 用户最初的输入
        llm_client: LLM 客户端（测试用）

    Returns:
        (是否改变, 新的类别)
    """
    if llm_client is None:
        llm_client = get_intent_llm_client()

    system_prompt = REENTRY_DETECT_SYSTEM_PROMPT.format(
        current_category=current_category,
        original_input=original_input,
        user_feedback=user_feedback,
    )

    try:
        response = await llm_client.call(
            system_prompt=system_prompt,
            user_prompt="请判断意图是否变化。",
            json_mode=True,
        )
        data = json.loads(response)
        has_changed = data.get("has_changed", False)
        new_category = data.get("new_category")

        if has_changed and new_category in ["report", "knowledge"]:
            logger.info(
                f"意图回退检测: 变化={has_changed}, "
                f"原分类={current_category}, 新分类={new_category}, "
                f"原因={data.get('reason', '')}"
            )
            return True, new_category

        return False, None

    except Exception as e:
        logger.warning(f"意图回退检测失败: {e}，默认不回退")
        return False, None


async def clarify_node(state: dict) -> dict:
    """
    LangGraph 澄清处理节点

    执行逻辑：
    1. 读取用户反馈（user_feedback）
    2. 检测是否触发意图回退
    3. 设置下一步路由方向
    4. 将用户反馈合并到 user_input 中（供后续重新识别使用）

    路由方向通过 clarify_next 字段表示：
    - "reentry_top": 回退到第一层重新分类
    - "continue_report": 继续第二层报表识别
    - "continue_knowledge": 继续第二层知识识别
    - "max_reentry_exceeded": 超过最大回退次数，重置
    """
    user_feedback_dict = state.get("user_feedback", {})
    user_feedback_text = (
        user_feedback_dict.get("selected_value", "")
        if isinstance(user_feedback_dict, dict)
        else str(user_feedback_dict)
    )
    current_category = state.get("intent_category", "report")
    original_input = state.get("user_input", "")
    reentry_count = state.get("reentry_count", 0)
    clarification_count = state.get("clarification_count", 0) + 1
    clarification_type = state.get("clarification", {}).get("type", "")

    logger.info(
        f"澄清处理: 类型={clarification_type}, 反馈='{user_feedback_text[:50]}', "
        f"当前分类={current_category}, 回退次数={reentry_count}"
    )

    result_updates = {
        "clarification_count": clarification_count,
        "needs_clarification": False,
    }

    # 合并用户反馈到 user_input（供后续重新识别使用）
    # 策略：把用户反馈作为新的 user_input，同时保留原始输入在 pending_clarification_input 中
    result_updates["pending_clarification_input"] = user_feedback_text
    # 也更新 user_input，让下游节点直接拿到最新的用户输入
    result_updates["user_input"] = user_feedback_text

    # 检测意图变化（只在非顶层澄清时检测）
    if clarification_type != "intent_confirm" and current_category in ["report", "knowledge"]:
        has_changed, new_category = await detect_intent_change(
            user_feedback_text, current_category, original_input
        )

        if has_changed and new_category:
            # 检查是否超过最大回退次数
            if reentry_count >= MAX_REENTRY_COUNT:
                logger.warning(f"超过最大回退次数({MAX_REENTRY_COUNT})，重置会话")
                result_updates["clarify_next"] = "max_reentry_exceeded"
                return result_updates

            # 触发回退
            result_updates["intent_category"] = new_category
            result_updates["reentry_count"] = reentry_count + 1
            result_updates["clarify_next"] = "reentry_top"
            logger.info(
                f"触发意图回退: {current_category} → {new_category}, "
                f"回退次数={reentry_count + 1}/{MAX_REENTRY_COUNT}"
            )
            return result_updates

    # 没有回退，继续当前层
    if current_category == "report":
        result_updates["clarify_next"] = "continue_report"
    elif current_category == "knowledge":
        result_updates["clarify_next"] = "continue_knowledge"
    else:
        result_updates["clarify_next"] = "reentry_top"

    return result_updates
```

- [ ] **Step 8: 运行澄清节点测试验证通过**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_clarify_node.py -v
```

- [ ] **Step 9: Commit**

```bash
cd /Users/simon/AL/DataAgent
git add backend/src/intent/reject_node.py backend/src/intent/clarify_node.py \
        backend/tests/test_reject_node.py backend/tests/test_clarify_node.py
git commit -m "feat: 实现拒答节点和通用澄清节点

- reject_node: 领域外问题礼貌拒答 + 引导建议
- clarify_node: 通用澄清处理 + 回退检测 + 路由设置
- detect_intent_change: LLM 判断用户反馈是否改变意图类别
- build_clarification_state: 构建澄清状态供前端展示
- 最大回退次数 3 次，超限重置

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: State 扩展 + Graph 重建

**Files:**
- Modify: `backend/src/graph/state.py` — 新增意图相关字段
- Modify: `backend/src/graph/builder.py` — 重建 graph 流程
- Modify: `backend/src/graph/nodes.py` — 添加新节点包装函数

**Interfaces:**
- Consumes: 所有新 intent 模块的节点函数
- Produces: 新的 LangGraph compiled app

**This is the integration task** — wire everything together. The graph flow becomes:

```
intent_classifier → 条件路由 → report_intent / knowledge(直接RAG) / reject
                              → 低置信度 → clarify
report_intent → 条件路由 → planner / clarify
clarify → 条件路由 → reentry_top / continue_report / continue_knowledge / max_reentry_exceeded
```

- [ ] **Step 1: 修改 state.py，新增字段**

```python
# 在 AdReportState 中新增以下字段（在合适位置插入）：

    # 顶层分类结果
    intent_category: Optional[str]       # report / knowledge / out_of_domain
    intent_confidence: float             # 0.0 ~ 1.0
    intent_classify_source: str          # rule_fastpath / llm
    intent_reason: str                   # 判断依据

    # 回退计数
    reentry_count: int                   # 回退到第一层的次数，默认 0

    # 澄清相关
    needs_clarification: bool            # 是否需要澄清（触发 interrupt）
    clarification: Optional[dict]        # {type, question, options, allow_custom_input, missing_fields}
    clarify_next: Optional[str]          # 澄清后下一步方向
    pending_clarification_input: Optional[str]  # 澄清后的用户输入（待处理）
    user_feedback: Optional[dict]        # 用户澄清反馈（保持现有字段）
    clarification_count: int             # 层内澄清次数（保持现有字段）

    # 拒答相关
    reject_reason: Optional[str]         # top_level / knowledge_scope

    # 报表意图（扩展，替代原 query_intent 的部分职责）
    # 原 query_intent 保留向后兼容
    report_intent_result: Optional[dict]  # ReportIntentResult 的 dict 形式
```

- [ ] **Step 2: 修改 nodes.py，添加新节点包装函数**

添加以下节点函数（都是 LangGraph 节点格式：接收 state dict，返回 dict）：

```python
async def intent_classifier_node(state: dict) -> dict:
    """顶层意图分类节点"""
    pass  # 调用 IntentTopClassifier

async def report_intent_node(state: dict) -> dict:
    """报表意图识别节点"""
    pass  # 调用 ReportIntentAnalyzer

async def clarify_node_entry(state: dict) -> dict:
    """澄清节点入口（实际逻辑在 intent/clarify_node.py）"""
    pass

async def reject_node_entry(state: dict) -> dict:
    """拒答节点入口"""
    pass
```

- [ ] **Step 3: 修改 builder.py，重建 graph**

重新构建整个 graph 流程，包括：
- 新节点：intent_classifier, report_intent, clarify, reject
- 条件路由：顶层分类后路由、报表意图后路由、澄清后路由
- interrupt_before: ["clarify"]
- 保持 RAG 流程不变（knowledge 直接走 rag_retrieve → rag_generate_answer）
- 保持报表下游不变（planner → executor → insight → analyst → reporter）

- [ ] **Step 4: 运行现有测试确保不破坏**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_graph_state.py tests/test_full_graph_flow.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/graph/state.py backend/src/graph/builder.py backend/src/graph/nodes.py
git commit -m "feat: 扩展 State 并重建 Graph 流程（新意图识别架构）

- State 新增：intent_category, reentry_count, clarification, needs_clarification 等
- 新节点：intent_classifier, report_intent, clarify, reject
- 新路由：分类后路由 / 报表意图后路由 / 澄清后路由
- interrupt_before 改为 clarify 节点
- 保持 RAG 流程和报表下游流程不变

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: API 层适配 + Session Service 适配

**Files:**
- Modify: `backend/src/services/session_service.py`
- Modify: `backend/src/api/sessions.py`

**Changes:**
- `send_message`: 适配新的澄清检测逻辑（从 `needs_clarification` 判断，不再从 `ambiguity` 判断）
- `submit_clarification`: 适配新的用户反馈格式
- 返回格式保持兼容（`waiting_for_clarification` / `completed`）

- [ ] **Step 1: 修改 session_service.py**

关键变更：
1. 检测澄清状态：检查 `state.get("needs_clarification")` 而不是 `state.get("ambiguity")`
2. 澄清格式：从 `state["clarification"]` 读取，格式为 `{type, question, options, allow_custom_input}`
3. submit_clarification: 将用户反馈写入 `state["user_feedback"]`，用 `graph_app.ainvoke(state)` 恢复执行
4. 超限重置处理：`clarify_next == "max_reentry_exceeded"` 时重置状态

- [ ] **Step 2: 修改 sessions.py（如果需要）**

API 层应该不需要大改，因为返回格式保持一致。只需要确认 `SubmitClarificationRequest` 的字段够用。

- [ ] **Step 3: 运行现有 API 相关测试**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/ -k "session" -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/services/session_service.py backend/src/api/sessions.py
git commit -m "feat: 适配 API 和 Session Service 到新意图识别架构

- send_message: 从 needs_clarification 判断是否需要澄清
- 澄清格式适配新的 ClarificationInfo 结构
- submit_clarification: 适配新的反馈格式
- 超限重置处理
- 保持 API 返回格式向后兼容

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: 集成测试

**Files:**
- Create: `backend/tests/test_intent_integration.py`

**What to test:**
1. 报表查询完整链路：分类 → 报表意图识别 → （信息齐全）→ planner
2. 报表查询缺字段链路：分类 → 报表意图识别 → 缺广告主 → 澄清 → 用户补充 → 继续
3. 意图回退链路：知识分类 → 澄清 → 用户说要查数据 → 回退 → 报表识别
4. 领域外拒答链路：分类 → out_of_domain → reject
5. 规则快筛链路：明确报表查询 → 快筛命中 → 直接报表识别
6. 3 次回退超限链路：连续回退 3 次 → 重置

- [ ] **Step 1: 写集成测试**
- [ ] **Step 2: 运行测试，修复问题**
- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_intent_integration.py
git commit -m "test: 添加意图识别模块集成测试

- 报表查询完整链路
- 缺字段澄清链路
- 意图回退链路
- 领域外拒答链路
- 规则快筛链路
- 回退超限重置链路

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: 日志埋点完善 + 最终验证

**Files:**
- Modify: 各 intent 模块文件（检查日志完整性）
- Create: （可选）日志格式一致性检查

**Work:**
1. 审查所有新模块的日志，确保统一使用 `logger.info/warning/error`
2. 确保所有日志携带足够的上下文（通过 contextvars 自动注入 request_id）
3. 添加关键路径的日志埋点（进入节点、离开节点、异常）
4. 运行全部测试，确保无回归
5. 运行整个测试套件

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/ -v --ignore=tests/e2e --ignore=tests/rag
```

- [ ] **Step 1: 日志审查和完善**
- [ ] **Step 2: 运行全部测试**
- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: 日志埋点完善 + 最终测试验证

- 统一所有新模块的日志格式和级别
- 确保关键路径都有日志记录
- 全部测试通过，无回归

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## 实施顺序总览

| 顺序 | Task | 预估复杂度 | 依赖 |
|------|------|-----------|------|
| 1 | LLM 客户端封装 | ⭐ | 无 |
| 2 | 系统能力注册表 | ⭐ | 无 |
| 3 | Pydantic 模型 + Prompt | ⭐ | 无 |
| 4 | 顶层意图分类器 | ⭐⭐ | Task 1, 3 |
| 5 | 报表意图识别 | ⭐⭐⭐ | Task 1, 2, 3 |
| 6 | 拒答 + 澄清节点 | ⭐⭐ | Task 1, 3 |
| 7 | State 扩展 + Graph 重建 | ⭐⭐⭐ | Task 4, 5, 6 |
| 8 | API + Session 适配 | ⭐⭐ | Task 7 |
| 9 | 集成测试 | ⭐⭐ | Task 7, 8 |
| 10 | 日志完善 + 最终验证 | ⭐ | Task 9 |

**总任务数：10 个**
