# 广告主查询功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在新意图识别架构中补全纯广告主查询功能支持，包括查询所有广告主列表、根据ID查名称、根据名称搜索ID。

**Architecture:** 在 `report_intent` 分析阶段开头增加纯广告主查询检测逻辑，检测命中后直接调用 `advertiser_service` 查询并生成 `final_report`，修改 Graph 路由直接跳转到 `reporter` 返回结果，不进入常规报表流程。改动集中在现有文件，不新增节点。

**Tech Stack:** Python 3.10+, LangGraph, Elasticsearch

## Global Constraints

- 复用现有 `advertiser_service.py` 中的查询函数，不重复实现
- 复用现有 `final_report` 数据格式，前端无需修改
- 只有纯广告主查询才直接返回，包含广告主的报表查询走正常流程

---

## File Changes Overview

| File | Change |
|------|--------|
| `backend/src/graph/builder.py` | 修改 `route_after_report_intent` 路由，增加 `final_report` 存在时跳转到 `reporter` 的判断 |
| `backend/src/intent/report_intent.py` | 在 `ReportIntentAnalyzer.analyze()` 开头增加纯广告主查询检测和响应生成逻辑 |
| `backend/src/graph/nodes.py` | 修改 `report_intent_node`，处理 `final_report` 写入 state |

---

### Task 1: 修改 Graph 路由逻辑

**Files:**
- Modify: `backend/src/graph/builder.py:67-75`

**Interfaces:**
- Consumes: None (router function, no external dependencies)
- Produces: Updated `route_after_report_intent` function with new routing logic

- [ ] **Step 1: Read current function**

Read lines 67-84 to see the existing implementation.

- [ ] **Step 2: Modify the function to add final_report check**

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

- [ ] **Step 3: Verify syntax and commit**

```bash
cd /Users/simon/AL/DataAgent && python -m py_compile backend/src/graph/builder.py && git add backend/src/graph/builder.py && git commit -m "feat: add direct return route for advertiser lookup in report_intent"
```

---

### Task 2: 在 report_intent.py 增加广告主查询检测逻辑

**Files:**
- Modify: `backend/src/intent/report_intent.py`

**Interfaces:**
- Consumes:
  - `src/services/advertiser_service.py`: `is_advertiser_list_query`, `get_all_advertisers`, `get_advertiser_by_id`, `get_advertiser_by_name`, `get_similar_advertiser_names`
  - `src/graph/nodes.py`: `_generate_suggested_queries` (reuse)
- Produces: `detect_advertiser_lookup` function that returns `final_report` if detected, else `None`

- [ ] **Step 1: Add imports**

At the top of the file, after existing imports, add:

```python
from src.services.advertiser_service import (
    is_advertiser_list_query,
    get_all_advertisers,
    get_advertiser_by_id,
    get_advertiser_by_name,
    get_similar_advertiser_names,
)
from src.intent.models import ClarificationInfo
```

- [ ] **Step 2: Add detect_advertiser_lookup function**

After the `_apply_context_inheritance` method, add:

```python
def _detect_advertiser_lookup(self, user_input: str) -> Optional[dict]:
    """
    检测是否为纯广告主查询，如果是则生成 final_report 返回

    Returns:
        纯广告查询 → final_report dict
        不是纯广告查询 → None
    """
    import re
    from src.graph.nodes import _generate_suggested_queries

    # Case 1: 查询广告主列表
    if is_advertiser_list_query(user_input):
        advertisers = get_all_advertisers()
        if not advertisers:
            return {
                "title": "暂无可用广告主",
                "time_range": {"start": "", "end": ""},
                "metrics": [],
                "highlights": [{"type": "info", "text": "⚠️ 当前没有查询到任何可用广告主"}],
                "data_table": {"columns": ["广告主ID", "广告主名称"], "rows": []},
                "next_queries": [],
            }

        return {
            "title": "可用广告主列表",
            "time_range": {"start": "", "end": ""},
            "metrics": [],
            "highlights": [
                {"type": "info", "text": "💡 点击以下广告主名称即可查看对应数据"}
            ],
            "data_table": {
                "columns": ["广告主ID", "广告主名称"],
                "rows": [[adv["id"], adv["name"]] for adv in advertisers]
            },
            "next_queries": _generate_suggested_queries(advertisers[0]['name']) if advertisers else [],
        }

    # Case 2: ID 查询名称 - patterns like:
    # "123叫什么" / "广告主123叫什么名字" / "123的名称是什么"
    id_match = re.search(r'(\d+)\s*(叫什么|名字|名称|是什么)', user_input.lower())
    if id_match:
        adv_id = id_match.group(1)
        adv = get_advertiser_by_id(adv_id)
        if adv:
            return {
                "title": f"广告主 {adv_id} 信息",
                "time_range": {"start": "", "end": ""},
                "metrics": [],
                "highlights": [
                    {"type": "info", "text": f"广告主ID: `{adv['id']}`"},
                    {"type": "info", "text": f"广告主名称: **{adv['name']}**"},
                ],
                "data_table": {"columns": [], "rows": []},
                "next_queries": _generate_suggested_queries(adv['name']),
            }
        else:
            return {
                "title": "未找到广告主",
                "time_range": {"start": "", "end": ""},
                "metrics": [],
                "highlights": [{"type": "warning", "text": f"⚠️ 未找到ID为 `{adv_id}` 的广告主"}],
                "data_table": {"columns": [], "rows": []},
                "next_queries": ["有哪些广告主"],
            }

    # Case 3: 名称查询ID - patterns like:
    # "ABC的ID" / "ABC广告主编号是多少" / "叫ABC的广告主ID是什么"
    name_match = re.search(r'(id|ID|编号)\s*(是多少|是什么|查询|找)', user_input.lower())
    if name_match:
        # 提取名称关键词：去掉问句部分，剩下的就是名称
        query_words = {"id", "ID", "编号", "是多少", "是什么", "查询", "找", "广告主"}
        tokens = re.findall(r'[a-zA-Z0-9_一-鿿]+', user_input)
        name_candidate = "".join([t for t in tokens if t.lower() not in query_words])

        if name_candidate:
            advertisers = get_advertiser_by_name(name_candidate)
            if advertisers:
                if len(advertisers) == 1:
                    adv = advertisers[0]
                    return {
                        "title": f"广告主「{name_candidate}」信息",
                        "time_range": {"start": "", "end": ""},
                        "metrics": [],
                        "highlights": [
                            {"type": "info", "text": f"匹配到广告主:"},
                            {"type": "info", "text": f"• ID: `{adv['id']}` 名称: **{adv['name']}**"},
                        ],
                        "data_table": {"columns": [], "rows": []},
                        "next_queries": _generate_suggested_queries(adv['name']),
                    }
                else:
                    highlights = [
                        {"type": "info", "text": f"匹配到 {len(advertisers)} 个广告主:"}
                    ]
                    for adv in advertisers:
                        highlights.append({"type": "info", "text": f"• ID: `{adv['id']}` 名称: **{adv['name']}**"})
                    return {
                        "title": f"广告主「{name_candidate}」搜索结果",
                        "time_range": {"start": "", "end": ""},
                        "metrics": [],
                        "highlights": highlights,
                        "data_table": {
                            "columns": ["广告主ID", "广告主名称"],
                            "rows": [[adv["id"], adv["name"]] for adv in advertisers]
                        },
                        "next_queries": _generate_suggested_queries(advertisers[0]['name']),
                    }
            else:
                # 无匹配，返回相似建议
                similar = get_similar_advertiser_names(user_input, top_n=5)
                if similar:
                    highlights = [
                        {"type": "warning", "text": f"⚠️ 未找到完全匹配「{name_candidate}」的广告主，你可能想找:"}
                    ]
                    for adv in similar:
                        highlights.append({"type": "info", "text": f"• ID: `{adv['id']}` 名称: **{adv['name']}**"})
                    return {
                        "title": "未找到匹配广告主",
                        "time_range": {"start": "", "end": ""},
                        "metrics": [],
                        "highlights": highlights,
                        "data_table": {"columns": [], "rows": []},
                        "next_queries": ["有哪些广告主"],
                    }
                else:
                    return {
                        "title": "未找到匹配广告主",
                        "time_range": {"start": "", "end": ""},
                        "metrics": [],
                        "highlights": [{"type": "warning", "text": f"⚠️ 未找到匹配「{name_candidate}」的广告主"}],
                        "data_table": {"columns": [], "rows": []},
                        "next_queries": ["有哪些广告主"],
                    }

    # 不是纯广告主查询，返回 None 继续正常流程
    return None
```

- [ ] **Step 3: Modify analyze method to call detection**

In the `analyze` method, after `Step 1: LLM extract` (around line 361), add:

```python
        # Step 1.5: 检测是否为纯广告主查询（列表查询/ID查名称/名称查ID）
        # 如果是，直接生成 final_report 返回，不走后续报表流程
        final_report = self._detect_advertiser_lookup(user_input)
        if final_report is not None:
            # 纯广告查询，直接返回 final_report
            logger.info(f"报表意图识别: 检测到纯广告主查询，直接返回结果")
            return None, None, final_report  # result, clarification, final_report
```

Adjust the return type annotation at function definition:

```python
async def analyze(
    self,
    user_input: str,
    conversation_history: List[dict] = None,
    existing_advertiser_ids: List[str] = None,
    existing_time_range: ReportTimeRange = None,
    existing_ad_level: str = None,
) -> Tuple[Optional[ReportIntentResult], Optional[ClarificationInfo], Optional[dict]]:
```

And update the return at the end:

```python
        return result, None, None
```

- [ ] **Step 4: Verify syntax and commit**

```bash
cd /Users/simon/AL/DataAgent && python -m py_compile backend/src/intent/report_intent.py && git add backend/src/intent/report_intent.py && git commit -m "feat: add advertiser lookup detection in report_intent"
```

---

### Task 3: 修改 report_intent_node 处理 final_report

**Files:**
- Modify: `backend/src/graph/nodes.py:549-615`

**Interfaces:**
- Consumes: `report_intent.analyze()` now returns `(result, clarification, final_report)`
- Produces: Updates to state including `final_report` when available

- [ ] **Step 1: Modify the return handling in report_intent_node**

Current code calls:
```python
result, clarification = await analyzer.analyze(...)
```

Change to:

```python
result, clarification, final_report = await analyzer.analyze(
    user_input,
    conversation_history,
    existing_advertiser_ids=existing_advertiser_ids,
    existing_time_range=existing_time_range,
    existing_ad_level=existing_ad_level,
)
```

After processing `result` and `clarification`, add:

```python
# 如果是纯广告主查询，已经生成了 final_report，直接写入 state
if final_report is not None:
    updates["final_report"] = final_report
```

- [ ] **Step 2: Verify the full updated function**

The updated function should look like:

```python
async def report_intent_node(state: dict) -> dict:
    """报表意图识别节点"""
    user_input = state.get("user_input", "")
    conversation_history = state.get("conversation_history", [])
    existing_advertiser_ids = state.get("advertiser_ids", [])

    logger.info(f"开始报表意图识别: 用户输入='{user_input[:100]}', 已有广告主={existing_advertiser_ids}")

    # 从上下文中获取已有的时间范围和层级
    existing_time_range = None
    existing_ad_level = None
    report_intent_result = state.get("report_intent_result")
    if report_intent_result:
        existing_time_range = report_intent_result.get("time_range")
        existing_ad_level = report_intent_result.get("ad_level")

    analyzer = get_report_intent_analyzer()
    result, clarification, final_report = await analyzer.analyze(
        user_input,
        conversation_history,
        existing_advertiser_ids=existing_advertiser_ids,
        existing_time_range=existing_time_range,
        existing_ad_level=existing_ad_level,
    )

    updates = {}

    # 如果是纯广告主查询，已经生成了 final_report，直接写入 state
    if final_report is not None:
        updates["final_report"] = final_report
        logger.info(f"报表意图识别完成: 纯广告主查询，已生成final_report")
        return updates

    if result:
        # 将 ReportIntentResult 转换为 dict 存入 state
        result_dict = result.model_dump()
        updates["report_intent_result"] = result_dict

        # 同时填充旧的 query_intent 字段，保持向后兼容
        query_intent = {
            "advertiser_ids": result.advertiser_ids,
            "metrics": result.metrics,
            "dimensions": result.group_by,
            "filters": result.filters,
            "is_comparison": result.is_comparison,
        }
        if result.time_range:
            query_intent["time_range"] = {
                "start": result.time_range.start_date,
                "end": result.time_range.end_date,
            }
        if result.compare_time_range:
            query_intent["compare_time_range"] = {
                "start": result.compare_time_range.start_date,
                "end": result.compare_time_range.end_date,
            }
        query_intent["ad_level"] = result.ad_level or "campaign"
        updates["query_intent"] = query_intent
        updates["advertiser_ids"] = result.advertiser_ids

    if clarification:
        # 需要澄清
        from src.intent.clarify_node import build_clarification_state
        updates.update(build_clarification_state(clarification))
        logger.info(f"报表意图识别完成: 触发澄清=True, 类型={clarification.type}")
    else:
        # 不需要澄清，确保标志位为 False
        updates["needs_clarification"] = False
        if result:
            logger.info(f"报表意图识别完成: 广告主={result.advertiser_ids}, 时间={result.time_range and result.time_range.start_date + '~' + result.time_range.end_date}, 指标={result.metrics}, 层级={result.ad_level}")
        else:
            logger.info(f"报表意图识别完成: 结果为空")

    return updates
```

- [ ] **Step 3: Verify syntax and commit**

```bash
cd /Users/simon/AL/DataAgent && python -m py_compile backend/src/graph/nodes.py && git add backend/src/graph/nodes.py && git commit -m "feat: update report_intent_node to handle final_report from advertiser lookup"
```

---

## Self-Review

1. **Spec coverage:** ✓ All three scenarios (list query, id→name, name→id) covered. ✓ Route change covered. ✓ Mixed queries handled correctly.
2. **Placeholder scan:** ✓ No placeholders, all code shown.
3. **Type consistency:** ✓ All function signatures updated correctly. ✓ Return tuple matches consumer.

**No gaps found.**

