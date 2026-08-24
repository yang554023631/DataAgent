"""
各节点实现占位符
"""

import time
import logging
import sys
import os
import asyncio
# Add backend directory to sys.path to import src.analysis and src.nl_dsl
# src folder is inside backend directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from typing import Dict, Any, Optional, List
from src.tools.executor import execute_ad_report_query
from src.agents.nlu_agent import nlu_agent
from src.agents.planner_agent import planner_agent
from src.agents.analyst_agent import analyst_agent
from src.agents.reporter_agent import reporter_agent, format_comparison_report
from src.agents.insight_agent import insight_agent, insights_to_highlights
from src.services.advertiser_service import get_all_advertisers
from src.services.streaming_context import get_sse_queue
from src.intent.top_classifier import get_top_classifier
from src.intent.report_intent import get_report_intent_analyzer
from src.intent.clarify_node import clarify_node as clarify_node_impl, build_clarification_state
from src.intent.reject_node import reject_node as reject_node_impl

logger = logging.getLogger(__name__)


async def _push_sse_event(event: Dict[str, Any]) -> None:
    """推送事件到 SSE 队列（如果当前是流式请求）"""
    queue = get_sse_queue()
    if queue is not None:
        try:
            import time
            from datetime import datetime
            # 根据步骤类型转换事件类型
            event_type = None
            status = event.get("status")
            if status == "started":
                event_type = "step_start"
            else:
                event_type = "step_complete"

            sse_event = {
                "type": event_type,
                "step": event.get("step"),
                "status": status,
                "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],  # 服务器端时间，方便观测推送时机
            }
            # 复制其他字段
            for k, v in event.items():
                if k not in sse_event:
                    sse_event[k] = v

            await queue.put(sse_event)
            # 让出控制权给事件循环，确保消费者能立即取出并发送这个事件
            # 避免多个事件攒在一起最后一次性发送
            await asyncio.sleep(0)
        except Exception as e:
            # 推送失败不影响主流程，只打日志
            logger.warning(f"Failed to push SSE event: {e}")


def _generate_suggested_queries(advertiser_name: str) -> list:
    """为广告主生成多样化的推荐查询"""
    templates = [
        "{name} 最近三个月哪些广告表现好？哪些广告表现不好？",
        "{name} 最近三个月的点击量按性别和月细分",
        "{name} 最近三个月 CTR 表现最好和最差的广告分别是哪些？",
    ]
    return [t.format(name=advertiser_name) for t in templates]


async def _resolve_advertiser_from_feedback(feedback: str) -> list:
    """
    解析用户澄清反馈中的广告主信息，返回广告主ID列表。

    支持：
    - 纯数字字符串 → 当作广告主ID
    - 非纯数字 → 当作名称，调用名称搜索
    """
    if not feedback:
        return []

    # 纯数字 → 直接当作ID
    if feedback.isdigit():
        return [feedback]

    # 非数字 → 当作名称搜索
    from src.services.advertiser_service import get_advertiser_by_name
    results = await get_advertiser_by_name(feedback)
    return [r["id"] for r in results]

async def nlu_node(state: dict) -> dict:
    """意图理解节点"""
    user_input = state.get("user_input", "")
    conversation_history = state.get("conversation_history", [])
    existing_advertiser_ids = state.get("advertiser_ids") or []

    try:
        query_intent = await nlu_agent(user_input, conversation_history, existing_advertiser_ids)

        result = {
            "query_intent": query_intent,
            "ambiguity": query_intent.get("ambiguity"),
            "error": None
        }

        # 广告主 ID 处理：
        # 1. 如果新检测到广告主，使用新的
        # 2. 如果没有检测到新的，但之前有，保留之前的
        new_advertiser_ids = query_intent.get("advertiser_ids", [])
        if new_advertiser_ids:
            result["advertiser_ids"] = new_advertiser_ids
            # 同步更新 query_intent 中的 advertiser_ids
            result["query_intent"]["advertiser_ids"] = new_advertiser_ids
        elif existing_advertiser_ids:
            # 没有新的，但之前有，保留
            result["advertiser_ids"] = existing_advertiser_ids
            # 同步更新 query_intent 中的 advertiser_ids
            result["query_intent"]["advertiser_ids"] = existing_advertiser_ids

        # 日志：NLU 解析结果
        intent_summary = {
            "query_type": query_intent.get("query_type"),
            "metrics": query_intent.get("metrics"),
            "dimensions": query_intent.get("dimensions"),
            "time_range": query_intent.get("time_range"),
            "advertiser_ids": query_intent.get("advertiser_ids"),
            "filters": query_intent.get("filters"),
            "is_comparison": query_intent.get("is_comparison"),
        }
        logger.info(f"NLU解析完成: {intent_summary}")

        return result
    except Exception as e:
        logger.error(f"NLU解析失败: {e}")
        return {
            "query_intent": None,
            "ambiguity": None,
            "error": {"type": "nlu_error", "message": str(e)}
        }

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


async def advertiser_handle_node(state: dict) -> dict:
    """广告主处理节点：展示列表、提示选择、或给出相似名称建议"""
    query_intent = state.get("query_intent", {})
    show_advertiser_list = query_intent.get("show_advertiser_list", False)
    need_advertiser_selection = query_intent.get("need_advertiser_selection", False)
    ambiguity = query_intent.get("ambiguity", {})
    has_ambiguous_advertiser = ambiguity and ambiguity.get("has_ambiguity") and ambiguity.get("type") == "advertiser_not_found"

    if show_advertiser_list:
        # 展示广告主列表
        advertisers = await get_all_advertisers()
        final_report = {
            "title": "可用的广告主列表",
            "time_range": {"start": "", "end": ""},
            "metrics": [],
            "highlights": [
                {"type": "info", "text": "💡 点击以下广告主名称即可查看对应数据"}
            ],
            "data_table": {
                "columns": ["广告主ID", "广告主名称"],
                "rows": [[adv["id"], adv["name"]] for adv in advertisers]
            },
            "next_queries": _generate_suggested_queries(advertisers[0]['name']) if advertisers else []
        }
        return {
            "final_report": final_report,
            "error": None,
            "ambiguity": None,
            "need_advertiser_selection": False
        }

    if has_ambiguous_advertiser:
        # 广告主未找到，给出相似名称建议
        similar_advertisers = ambiguity.get("options", [])
        reason = ambiguity.get("reason", "未找到匹配的广告主")

        if similar_advertisers:
            # 有相似建议
            highlights = [
                {"type": "warning", "text": f"⚠️ {reason} 您可能想选择："},
            ]
            for adv in similar_advertisers:
                highlights.append({"type": "info", "text": f"• {adv['name']} (ID: {adv['id']})"})

            final_report = {
                "title": "未找到匹配的广告主",
                "time_range": {"start": "", "end": ""},
                "metrics": [],
                "highlights": highlights,
                "next_queries": _generate_suggested_queries(similar_advertisers[0]['name']) if similar_advertisers else []
            }
        else:
            # 没有相似建议，展示所有广告主列表
            advertisers = await get_all_advertisers()
            final_report = {
                "title": "未找到匹配的广告主，请选择正确的名称",
                "time_range": {"start": "", "end": ""},
                "metrics": [],
                "highlights": [
                    {"type": "warning", "text": "⚠️ 未找到匹配的广告主，请从以下列表中选择："}
                ],
                "data_table": {
                    "columns": ["广告主ID", "广告主名称"],
                    "rows": [[adv["id"], adv["name"]] for adv in advertisers]
                },
                "next_queries": _generate_suggested_queries(advertisers[0]['name']) if advertisers else []
            }
        return {
            "final_report": final_report,
            "error": None,
            "ambiguity": None,
            "need_advertiser_selection": False
        }

    if need_advertiser_selection:
        # 提示用户选择广告主
        advertisers = await get_all_advertisers()
        final_report = {
            "title": "请选择要查看的广告主",
            "time_range": {"start": "", "end": ""},
            "metrics": [],
            "highlights": [
                {"type": "info", "text": "💡 请从以下广告主中选择，点击名称即可查看对应数据"}
            ],
            "data_table": {
                "columns": ["广告主ID", "广告主名称"],
                "rows": [[adv["id"], adv["name"]] for adv in advertisers]
            },
            "next_queries": _generate_suggested_queries(advertisers[0]['name']) if advertisers else []
        }
        return {
            "final_report": final_report,
            "error": None,
            "ambiguity": None,
            "need_advertiser_selection": False
        }

    # 不需要处理，继续往下走
    return {}

async def planner_node(state: dict) -> dict:
    """查询规划节点"""
    query_intent = state.get("query_intent", {})
    user_feedback = state.get("user_feedback")

    try:
        result = await planner_agent(query_intent, user_feedback)

        is_comparison = query_intent.get("is_comparison", False)
        compare_time_range = query_intent.get("compare_time_range")

        query_requests = []

        # 第一个查询：主时间范围
        query_requests.append(result["query_request"])

        # 第二个查询：对比时间范围（如果是对比查询）
        if is_comparison and compare_time_range:
            compare_query = result["query_request"].copy()
            compare_query["time_range"] = compare_time_range
            query_requests.append(compare_query)

        # 日志：规划结果摘要
        logger.info(
            f"查询规划完成: 指标={result['query_request'].get('metrics')}, "
            f"维度={result['query_request'].get('group_by')}, "
            f"警告数={len(result['query_warnings'])}"
        )

        return {
            "query_request": result["query_request"],  # 向后兼容
            "query_requests": query_requests,
            "query_warnings": result["query_warnings"],
            "insight_queries": result.get("insight_queries", {}),
            "error": None
        }
    except Exception as e:
        logger.error(f"查询规划失败: {e}")
        return {
            "query_request": None,
            "query_requests": [],
            "query_warnings": [],
            "error": {"type": "planner_error", "message": str(e)}
        }

async def executor_node(state: dict) -> dict:
    """数据执行节点：调用 CustomReport 接口（支持对比查询并行执行）"""
    query_request = state.get("query_request")
    query_requests = state.get("query_requests", [])

    if not query_request and not query_requests:
        return {
            "query_result": None,
            "query_results": [],
            "execution_time_ms": 0,
            "error": {"type": "no_query", "message": "没有查询请求"}
        }

    start_time = time.time()

    try:
        # 如果有多个查询请求（对比查询），并行执行
        if query_requests and len(query_requests) > 1:
            import asyncio
            tasks = [execute_ad_report_query.ainvoke({"query_request": qr}) for qr in query_requests]
            results = await asyncio.gather(*tasks)

            execution_time = int((time.time() - start_time) * 1000)

            # 检查所有查询是否成功
            all_success = all(r["success"] for r in results)
            first_error = next((
                {"type": r.get("error_type"), "message": r.get("message"), "suggestions": r.get("suggestions", [])}
                for r in results if not r["success"]
            ), None)

            # 日志：ES 查询结果（对比查询）
            total_data = sum(
                len(r.get("data", [])) if r.get("data") else 0
                for r in results
            )
            logger.info(f"ES查询完成(对比查询): 查询数={len(results)}, 总条数={total_data}, 耗时={execution_time}ms")

            return {
                "query_result": results[0] if results else None,  # 向后兼容
                "query_results": results,
                "execution_time_ms": execution_time,
                "error": None if all_success else first_error
            }
        else:
            # 单个查询的情况（向后兼容）
            result = await execute_ad_report_query.ainvoke({"query_request": query_request})

            execution_time = int((time.time() - start_time) * 1000)

            # 日志：ES 查询结果（单个查询）
            data_count = len(result.get("data", [])) if result.get("data") else 0
            logger.info(f"ES查询完成: 结果条数={data_count}, 耗时={execution_time}ms")

            return {
                "query_result": result,
                "query_results": [result] if result else [],
                "execution_time_ms": execution_time,
                "error": None if result["success"] else {
                    "type": result.get("error_type"),
                    "message": result.get("message"),
                    "suggestions": result.get("suggestions", [])
                }
            }
    except Exception as e:
        logger.exception(f"ES查询异常: error={e}")
        return {
            "query_result": None,
            "query_results": [],
            "execution_time_ms": 0,
            "error": {"type": "exception", "message": str(e)}
        }

async def analyst_node(state: dict) -> dict:
    """数据分析节点"""
    query_result = state.get("query_result", {})
    query_request = state.get("query_request", {})

    try:
        result = await analyst_agent(query_result, query_request)

        # 日志：分析完成摘要
        logger.info(f"分析完成: needs_drill_down={result.get('needs_drill_down', False)}")

        return {
            "analysis_result": result,
            "drill_down_level": state.get("drill_down_level", 0),
            "needs_drill_down": result.get("needs_drill_down", False),
            "error": None
        }
    except Exception as e:
        logger.exception(f"分析异常: error={e}")
        return {
            "analysis_result": None,
            "drill_down_level": state.get("drill_down_level", 0),
            "needs_drill_down": False,
            "error": {"type": "analyst_error", "message": str(e)}
        }

async def reporter_node(state: dict) -> dict:
    """报告生成节点（支持对比查询 + 洞察高亮）"""
    # 如果 final_report 已经存在（如广告主查询直接生成的），直接返回
    existing_final_report = state.get("final_report")
    if existing_final_report is not None:
        logger.info(f"报告生成: final_report已存在，直接返回，标题='{existing_final_report.get('title', '')}'")
        return {
            "final_report": existing_final_report,
            "error": None,
        }

    query_intent = state.get("query_intent", {})
    query_request = state.get("query_request", {})
    query_result = state.get("query_result") or {}
    query_results = state.get("query_results", [])
    analysis_result = state.get("analysis_result") or {}
    insights = state.get("insights")

    try:
        # 检查是否为对比查询（有多个查询结果）
        is_comparison = query_intent.get("is_comparison", False) and len(query_results) >= 2

        if is_comparison:
            # 使用对比查询格式化
            query_requests = state.get("query_requests", [query_request])
            final_report = format_comparison_report(
                query_intent,
                query_requests,
                query_results
            )
        else:
            # 普通查询（原有逻辑）
            final_report = await reporter_agent(
                query_intent,
                query_request,
                query_result,
                analysis_result
            )

        # 合并洞察结果到 highlights
        if insights:
            # 添加完整的洞察对象（用于前端渲染高级可折叠卡片，包含数据证据和建议）
            final_report["insights"] = {
                "problems": [p.model_dump() for p in insights.problems],
                "highlights": [h.model_dump() for h in insights.highlights],
                "summary": insights.summary
            }
            # 同时添加简化的 highlights 文本（向下兼容）
            insight_highlights = insights_to_highlights(insights)
            existing_highlights = final_report.get("highlights", [])
            final_report["highlights"] = insight_highlights + existing_highlights

        # 日志：报告生成完成摘要
        title = final_report.get("title", "")
        metric_count = len(final_report.get("metrics", []))
        highlight_count = len(final_report.get("highlights", []))
        logger.info(
            f"报告生成完成: 标题='{title}', 指标数={metric_count}, 亮点数={highlight_count}"
        )

        return {
            "final_report": final_report,
            "error": None
        }
    except Exception as e:
        logger.exception(f"报告生成异常: error={e}")
        return {
            "final_report": None,
            "error": {"type": "reporter_error", "message": str(e)}
        }

async def insight_node(state: dict) -> dict:
    """洞察分析节点：对 Creative 和 Ad Group 两个维度分别执行规则+LLM洞察分析"""
    from src.tools.executor import execute_ad_report_query
    from src.models.insight import InsightResult

    query_request = state.get("query_request", {})

    # 生成两个维度的洞察查询（直接生成，不依赖传递）
    base_query = {
        "index_type": query_request.get("index_type", "general"),
        "time_range": query_request.get("time_range", {}),
        "advertiser_ids": query_request.get("advertiser_ids", []),
        "metrics": query_request.get("metrics", ["impressions", "clicks", "cost", "conversions"]),
        "filters": query_request.get("filters", []),
    }

    insight_queries = {
        "creative": {**base_query, "group_by": ["creative_id"]},
        "ad_group": {**base_query, "group_by": ["ad_group_id"]}
    }

    try:
        # 构建查询上下文（基准值、配置等）
        query_context = {
            "query_request": query_request,
            "advertiser_ids": query_request.get("advertiser_ids", []),
            "time_range": query_request.get("time_range", {}),
            "baseline_values": {}  # 可扩展基准值配置
        }

        # 并行执行两个维度的查询并跑规则
        dimension_insights = {}

        for dimension, query in insight_queries.items():
            # 执行该维度的 ES 查询
            query_result = await execute_ad_report_query.ainvoke({"query_request": query})

            # 调用洞察Agent分析该维度
            context = query_context.copy()
            context["dimension"] = dimension
            insights = await insight_agent(query_result, context, enable_llm_scan=False)
            dimension_insights[dimension] = insights

        # 合并两个维度的洞察结果
        all_problems = []
        all_highlights = []

        # 素材维度（优先显示）
        creative_insights = dimension_insights.get("creative", InsightResult(problems=[], highlights=[], summary="", llm_insights=[]))
        for p in creative_insights.problems:
            p.dimension = "creative"
            p.name = f"[素材] {p.name}"
        for h in creative_insights.highlights:
            h.dimension = "creative"
            h.name = f"[素材] {h.name}"
        all_problems.extend(creative_insights.problems)
        all_highlights.extend(creative_insights.highlights)

        # 广告组维度
        adgroup_insights = dimension_insights.get("ad_group", InsightResult(problems=[], highlights=[], summary="", llm_insights=[]))
        for p in adgroup_insights.problems:
            p.dimension = "ad_group"
            p.name = f"[广告组] {p.name}"
        for h in adgroup_insights.highlights:
            h.dimension = "ad_group"
            h.name = f"[广告组] {h.name}"
        all_problems.extend(adgroup_insights.problems)
        all_highlights.extend(adgroup_insights.highlights)

        # 构建最终的 InsightResult
        summary_parts = []
        if all_problems:
            summary_parts.append(f"发现 {len(all_problems)} 个需关注的问题")
        if all_highlights:
            summary_parts.append(f"发现 {len(all_highlights)} 个数据亮点")

        merged_result = InsightResult(
            problems=all_problems,
            highlights=all_highlights,
            summary="，".join(summary_parts) if summary_parts else "",
            llm_insights=[]
        )
        merged_result.dimension_insights = dimension_insights

        # 日志：洞察命中情况
        problem_ids = [p.id for p in all_problems]
        highlight_ids = [h.id for h in all_highlights]
        logger.info(
            f"洞察分析完成: 问题命中={problem_ids} ({len(all_problems)}条), "
            f"亮点命中={highlight_ids} ({len(all_highlights)}条)"
        )

        return {
            "insights": merged_result,
            "error": None
        }
    except Exception as e:
        logger.exception(f"洞察分析异常: error={e}")
        return {
            "insights": None,
            "error": {"type": "insight_error", "message": str(e)}
        }


# ========== 新意图识别架构的节点包装函数 ==========

async def intent_classifier_node(state: dict) -> dict:
    """顶层意图分类节点"""
    user_input = state.get("user_input", "")
    conversation_history = state.get("conversation_history", [])

    # 获取已有的 execution_trace
    execution_trace: List[Dict[str, Any]] = state.get("execution_trace", [])

    step_start = time.time()
    event = {"step": "intent_classifier", "status": "started"}
    execution_trace.append(event)
    await _push_sse_event(event)

    logger.info(f"开始顶层意图分类: 用户输入='{user_input[:100]}'")

    classifier = get_top_classifier()
    result = await classifier.classify(user_input, conversation_history)

    updates = {
        "execution_trace": execution_trace,
        "intent_category": result.category,
        "intent_confidence": result.confidence,
        "intent_classify_source": result.source,
        "intent_reason": result.reason,
        # 保持向后兼容，同时设置旧字段
        "query_type": "knowledge" if result.category == "knowledge" else "report",
    }

    # 低置信度触发澄清
    if result.confidence < classifier.confidence_threshold:
        from src.intent.models import ClarificationInfo
        clarification = ClarificationInfo(
            type="intent_confirm",
            question=f"我不确定你是想查询广告数据还是了解广告知识。你能明确一下吗？",
            options=[
                {"value": "report", "label": "查询广告数据"},
                {"value": "knowledge", "label": "了解广告知识"},
            ],
            allow_custom_input=False,
            missing_fields=[],
        )
        updates.update(build_clarification_state(clarification))
        event = {
            "step": "intent_classifier",
            "status": "needs_clarification",
            "duration_ms": int((time.time() - step_start) * 1000),
        }
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"顶层意图分类完成: 分类={result.category}, 置信度={result.confidence:.2f}, 触发澄清=True")
    else:
        event = {
            "step": "intent_classifier",
            "status": "success",
            "duration_ms": int((time.time() - step_start) * 1000),
            "category": result.category,
            "confidence": result.confidence,
        }
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"顶层意图分类完成: 分类={result.category}, 置信度={result.confidence:.2f}, 来源={result.source}")

    return updates


async def report_intent_node(state: dict) -> dict:
    """报表意图识别节点"""
    user_input = state.get("user_input", "")
    conversation_history = state.get("conversation_history", [])
    existing_advertiser_ids = list(state.get("advertiser_ids") or [])

    # 获取已有的 execution_trace
    execution_trace: List[Dict[str, Any]] = state.get("execution_trace", [])

    # --- 澄清回填：上一轮是 missing_advertiser 澄清时，把用户选择的广告主直接填入 ---
    clarification_info = state.get("clarification") or {}
    last_clarification_type = clarification_info.get("type", "")
    pending_input = state.get("pending_clarification_input", "")

    step_start = time.time()
    event = {"step": "report_intent", "status": "started"}
    execution_trace.append(event)
    await _push_sse_event(event)

    if last_clarification_type == "missing_advertiser" and pending_input:
        resolved_ids = _resolve_advertiser_from_feedback(pending_input)
        if resolved_ids:
            existing_advertiser_ids = list(set(existing_advertiser_ids + resolved_ids))
            logger.info(f"澄清回填广告主: 反馈='{pending_input}', 解析出IDs={resolved_ids}")

    logger.info(f"开始报表意图识别: 用户输入='{user_input[:100]}', 已有广告主={existing_advertiser_ids}")

    # 从上下文中获取已有的时间范围和层级
    existing_time_range = None
    existing_ad_level = None
    report_intent_result = state.get("report_intent_result")
    if report_intent_result:
        existing_time_range = report_intent_result.get("time_range")
        existing_ad_level = report_intent_result.get("ad_level")

    analyzer = get_report_intent_analyzer()
    result, clarification, final_report, route_info = await analyzer.analyze(
        user_input,
        conversation_history,
        existing_advertiser_ids=existing_advertiser_ids,
        existing_time_range=existing_time_range,
        existing_ad_level=existing_ad_level,
    )

    updates = {
        "execution_trace": execution_trace,
    }

    # 写入路由信息到 state（所有路径都有 route_info）
    if route_info:
        updates["query_route"] = route_info["route"]
        updates["route_reason"] = route_info["reason"]
        updates["analysis_type"] = route_info["analysis_type"]

    if final_report:
        # 纯广告主查询，直接返回 final_report
        updates["final_report"] = final_report
        updates["needs_clarification"] = False
        event = {
            "step": "report_intent",
            "status": "success",
            "duration_ms": int((time.time() - step_start) * 1000),
            "route": route_info["route"],
            "has_final_report": True,
        }
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"报表意图识别完成: 检测到纯广告主查询, 路由={route_info['route']}")
    else:
        # 非纯广告主查询路径，清除旧的 final_report（避免 state 中残留上一轮的结果）
        updates["final_report"] = None

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
            updates.update(build_clarification_state(clarification))
            event = {
                "step": "report_intent",
                "status": "needs_clarification",
                "duration_ms": int((time.time() - step_start) * 1000),
            }
            execution_trace.append(event)
            await _push_sse_event(event)
            logger.info(f"报表意图识别完成: 触发澄清=True, 类型={clarification.type}, 路由={route_info['route']}")
        else:
            # 不需要澄清，确保标志位为 False
            updates["needs_clarification"] = False
            if result:
                event = {
                    "step": "report_intent",
                    "status": "success",
                    "duration_ms": int((time.time() - step_start) * 1000),
                    "route": route_info["route"],
                }
                execution_trace.append(event)
                await _push_sse_event(event)
                log_msg = f"报表意图识别完成: 广告主={result.advertiser_ids}, 时间={result.time_range and result.time_range.start_date + '~' + result.time_range.end_date}, 指标={result.metrics}, 层级={result.ad_level}"
                log_msg += f", 路由={route_info['route']}, 原因={route_info['reason']}"
                logger.info(log_msg)
            else:
                event = {
                    "step": "report_intent",
                    "status": "success",
                    "duration_ms": int((time.time() - step_start) * 1000),
                    "route": route_info["route"],
                    "result_empty": True,
                }
                execution_trace.append(event)
                await _push_sse_event(event)
                logger.info(f"报表意图识别完成: 结果为空, 路由={route_info['route']}")

    return updates


async def clarify_node_entry(state: dict) -> dict:
    """澄清节点入口（包装 clarify_node）"""
    return await clarify_node_impl(state)


async def reject_node_entry(state: dict) -> dict:
    """拒答节点入口（包装 reject_node）"""
    return await reject_node_impl(state)


async def _build_nl_dsl_final_report(result, user_input: str, report_intent: dict) -> dict:
    """
    构建 NL→DSL 成功的 final_report

    Args:
        result: NlDslResult 对象或 dict
        user_input: 用户原始输入
        report_intent: report_intent_result dict

    Returns:
        final_report dict，格式与 reporter_agent 一致
    """
    from src.config.context import truncate_log
    from src.nl_dsl.field_mapping import (
        get_dimension_display_name,
        get_metric_display_name,
        get_metric_by_data_type,
        resolve_metric_from_query,
        extract_data_types_from_dsl,
        extract_agg_field_mapping,
        METRICS,
    )

    # 处理 result 可能是对象或 dict
    if hasattr(result, 'model_dump'):
        result_dict = result.model_dump()
    else:
        result_dict = result

    columns = result_dict.get('columns', [])
    rows = result_dict.get('rows', [])
    metadata = result_dict.get('metadata', {})
    display_type = result_dict.get('display_type', 'list')

    # 将 exploratory_query 等非渲染类型规范化为实际呈现类型
    if display_type in ("exploratory_query", "detail", "comparison"):
        has_aggs = metadata.get('has_aggregations', False)
        if has_aggs and rows:
            display_type = "list"  # 聚合列表（按维度分组的指标对比）
        elif rows:
            display_type = "list"
        else:
            display_type = "qa"

    # ---- 列名映射：原始字段名 → 用户友好的显示名 ----
    # 从 DSL（如果有）中提取实际查询的 data_type，用于映射 data_value 列名
    query_context = result_dict.get("query_context") or {}
    base_dsl = query_context.get("base_dsl") if isinstance(query_context, dict) else None

    # 尝试从 DSL 提取 data_type 来确定指标
    primary_metric = None
    data_types = extract_data_types_from_dsl(base_dsl) if base_dsl else []
    if len(data_types) == 1:
        metric_info = get_metric_by_data_type(data_types[0])
        if metric_info:
            primary_metric = metric_info["name"]

    # DSL 里没找到或多个 data_type 时，fallback 到 report_intent 和用户 query
    if not primary_metric:
        intent_metrics = (report_intent or {}).get("metrics", []) or []
        if intent_metrics and intent_metrics[0] in METRICS:
            primary_metric = intent_metrics[0]
        else:
            resolved = resolve_metric_from_query(user_input)
            if resolved:
                primary_metric = resolved

    # 从 DSL 的 aggs 中提取「聚合名称 → 实际字段名」映射
    # 用于聚合结果中列名是聚合名（如 by_campaign）而非字段名的情况
    agg_field_map = extract_agg_field_mapping(base_dsl) if base_dsl else {}

    # ID 维度字段 -> (name列显示名, entity_type)
    # 定义在此处供后续多处使用（列映射、聚合去重、名称补充）
    id_to_name_map = {
        "campaign_id": ("计划名称", "campaign"),
        "adgroup_id": ("广告组名称", "adgroup"),
        "advertiser_id": ("广告主名称", "advertiser"),
        "creative_id": ("创意名称", "creative"),
    }

    def _map_column(col: str):
        # data_type 列对用户没意义，跳过（不展示）
        if col == "data_type":
            return None

        # 如果是聚合名称（不是原始字段名），先映射到实际字段名
        actual_field = agg_field_map.get(col, col)

        # 特殊处理：长表模型的 data_value 列 → 替换为实际指标名
        if actual_field == "data_value" and primary_metric:
            return get_metric_display_name(primary_metric)
        # 维度字段映射
        cn_name = get_dimension_display_name(actual_field)
        if cn_name != actual_field:
            return cn_name
        # 指标字段名（如果列名恰好是指标英文名）
        metric_cn = get_metric_display_name(actual_field)
        if metric_cn != actual_field:
            return metric_cn
        return col

    display_columns = []
    keep_indices = []
    for i, col in enumerate(columns):
        mapped = _map_column(col)
        if mapped is None:
            continue  # 跳过不需要展示的列（如 data_type）
        display_columns.append(mapped)
        keep_indices.append(i)

    # 对应地过滤 row 中的列
    if keep_indices != list(range(len(columns))):
        rows = [[row[i] for i in keep_indices] for row in rows]
        columns = display_columns
    else:
        columns = display_columns

    # ---- 明细数据自动聚合去重 ----
    # 场景：用户问"消耗>10的计划有哪些"，LLM 可能生成明细查询（每天每行），
    # 导致同一计划重复出现且消耗是单日值。这里检测到明细数据包含维度ID+指标时，
    # 按维度聚合汇总指标，确保每个维度实体只有一行。
    if rows and base_dsl and metadata.get("has_aggregations") is False:
        # 找出维度列和指标列的索引（基于映射后的 display_columns）
        dim_field_to_idx = {}
        metric_indices = []
        orig_columns_raw = result_dict.get('columns', [])

        for i, col in enumerate(orig_columns_raw):
            actual_field = agg_field_map.get(col, col)
            if actual_field in id_to_name_map:
                dim_field_to_idx[actual_field] = i
            elif actual_field == "data_value":
                metric_indices.append(i)

        # 只有在同时有维度列和指标列、且数据行数明显大于维度去重数时才聚合
        if dim_field_to_idx and metric_indices:
            # 取第一个维度列作为主键（通常最左边的维度是主要分组维度）
            primary_dim_field = None
            for field in id_to_name_map.keys():
                if field in dim_field_to_idx:
                    primary_dim_field = field
                    break

            if primary_dim_field:
                dim_idx = dim_field_to_idx[primary_dim_field]
                # 检查是否存在重复（简单用前几行采样判断）
                sample_keys = set()
                has_duplicates = False
                for row in rows[:min(100, len(rows))]:
                    if dim_idx < len(row):
                        key = row[dim_idx]
                        if key in sample_keys:
                            has_duplicates = True
                            break
                        sample_keys.add(key)

                if has_duplicates:
                    # 按维度聚合：指标列求和，其他列（如日期）丢弃
                    aggregated = {}
                    for row in rows:
                        if dim_idx >= len(row):
                            continue
                        key = row[dim_idx]
                        if key not in aggregated:
                            # 保留维度列的值，指标列初始化为 0
                            new_row = list(row)
                            for mi in metric_indices:
                                if mi < len(new_row):
                                    new_row[mi] = 0
                            aggregated[key] = new_row
                        # 累加指标列
                        agg_row = aggregated[key]
                        for mi in metric_indices:
                            if mi < len(agg_row) and mi < len(row):
                                try:
                                    agg_row[mi] = (agg_row[mi] or 0) + (row[mi] or 0)
                                except (TypeError, ValueError):
                                    pass

                    rows = list(aggregated.values())
                    # 去掉纯明细列（如 data_date 等非维度非指标的列）
                    # 保留维度列和指标列
                    keep = []
                    new_columns = []
                    for i, col in enumerate(orig_columns_raw):
                        actual = agg_field_map.get(col, col)
                        if actual in id_to_name_map or actual == "data_value":
                            keep.append(i)
                            new_columns.append(col)
                    if keep != list(range(len(orig_columns_raw))):
                        rows = [[r[i] for i in keep if i < len(r)] for r in rows]
                        # 同步更新 display_columns 和 columns
                        display_columns = [display_columns[i] for i in keep if i < len(display_columns)]
                        columns = display_columns
                        # 重建 agg_field_map 对应的列映射（列数减少了）
                        # 这里我们用 new_columns 重新映射
                        orig_columns = new_columns
                    # 更新总行数
                    total_rows = len(rows)

    # ---- 自动补充维度名称列（campaign_id → campaign_name 等） ----
    # 检测原始列中哪些是 ID 维度，然后批量查询对应的 name 并插入到 ID 列后面

    if rows and base_dsl:
        from src.tools.hierarchy_utils import get_entity_names

        # 如果 orig_columns 还不存在（聚合去重没发生），
        # 需要根据第一步过滤得到的 keep_indices 过滤原始列，得到和当前 rows/columns 对应的原始列
        if 'orig_columns' not in locals():
            # orig_columns 初始化为原始列，然后过滤
            orig_columns = result_dict.get('columns', [])
            if keep_indices != list(range(len(orig_columns))):
                orig_columns = [orig_columns[i] for i in keep_indices]

        # 找出所有需要补充 name 的 ID 列（通过 agg_field_map 反查实际字段名）
        # 当前 orig_columns 和 rows 已经过滤过，索引一一对应
        name_insertions = []  # [(insert_after_idx, entity_type, name_col_name)]

        for current_idx, orig_col in enumerate(orig_columns):
            actual_field = agg_field_map.get(orig_col, orig_col)
            if actual_field in id_to_name_map:
                name_display, entity_type = id_to_name_map[actual_field]
                # current_idx 就是当前 rows 中的索引，直接使用
                name_insertions.append((current_idx, entity_type, name_display))

        if name_insertions:
            # 收集所有需要查询的实体和 ID
            entity_ids_by_type = {}
            for _, entity_type, _ in name_insertions:
                if entity_type not in entity_ids_by_type:
                    entity_ids_by_type[entity_type] = set()

            # 从每行提取对应列的 ID 值
            # 需要找到原始列在当前 rows 中的索引
            col_entity_types = {}  # col_idx -> entity_type
            for current_idx, entity_type, _ in name_insertions:
                col_entity_types[current_idx] = entity_type
                for row in rows:
                    if current_idx < len(row):
                        val = row[current_idx]
                        if val is not None and val != "":
                            try:
                                entity_ids_by_type[entity_type].add(int(val))
                            except (ValueError, TypeError):
                                pass

            # Debug: print to console because logging may be buffered
            print(f"[debug-name] after collecting ids: entity_ids_by_type={entity_ids_by_type}")
            logger.info(f"[debug-name] after collecting ids: entity_ids_by_type={entity_ids_by_type}")

            # 批量查询所有 name
            name_maps = {}
            for entity_type, ids in entity_ids_by_type.items():
                if ids:
                    name_maps[entity_type] = await get_entity_names(entity_type, list(ids))
                    print(f"[debug-name] got {entity_type} names: {len(name_maps[entity_type])} names for {sorted(list(ids))} → {name_maps[entity_type]}")
                    logger.info(f"[debug-name] got {entity_type} names: {len(name_maps[entity_type])} names for {sorted(list(ids))} → {name_maps[entity_type]}")
                else:
                    name_maps[entity_type] = {}
            print(f"[debug-name] name_insertions={name_insertions}, final columns before insert: {columns}, rows sample[0]={rows[0] if rows else '[]'}")
            logger.info(f"[debug-name] name_insertions={name_insertions}, final columns before insert: {columns}, rows sample[0]={rows[0] if rows else 'empty'}")

            # 按位置从后往前插入（避免索引偏移）
            for current_idx, entity_type, name_display in sorted(name_insertions, key=lambda x: -x[0]):
                name_map = name_maps.get(entity_type, {})
                columns.insert(current_idx + 1, name_display)
                for row in rows:
                    if current_idx < len(row):
                        try:
                            eid = int(row[current_idx])
                            ename = name_map.get(eid, "")
                        except (ValueError, TypeError):
                            ename = ""
                        row.insert(current_idx + 1, ename)
            if name_insertions:
                logger.info(f"[debug-name] after insert: columns={columns}, rows[0]={rows[0] if rows else 'empty'}")

    # 生成标题
    time_range = report_intent.get('time_range', {}) if report_intent else {}
    start = time_range.get('start_date', '')
    end = time_range.get('end_date', '')
    if start and end:
        title = f"{start} ~ {end} 查询结果"
    else:
        title = "查询结果"

    # 生成 highlights
    highlights = []
    total_rows = metadata.get('total_rows', len(rows))
    if metadata.get('is_empty_result'):
        empty_reason = metadata.get('empty_reason', '查询结果为空')
        highlights.append({
            "type": "negative",
            "text": f"⚠️ {empty_reason}"
        })
    else:
        highlights.append({
            "type": "info",
            "text": f"✅ 查询完成，共 {total_rows} 条结果"
        })

    # 生成 next_queries
    next_queries = [
        "查看更多维度分析",
        "添加过滤条件缩小范围",
        "对比不同时间段数据"
    ]

    # 根据 display_type 调整格式
    data_table = {"columns": columns, "rows": rows}

    # 图表配置（暂时简单处理）
    chart_config = None
    if display_type == "chart" or display_type == "line" or display_type == "bar":
        chart_config = {
            "type": display_type if display_type in ["line", "bar"] else "bar",
            "series": [{"name": col, "color": "#3b82f6"} for col in columns[1:]] if len(columns) > 1 else [],
            "metrics": []
        }

    return {
        "title": title,
        "time_range": {"start": start, "end": end},
        "metrics": [],  # NL→DSL 暂时不单独展示总指标
        "highlights": highlights,
        "data_table": data_table,
        "chart_config": chart_config,
        "next_queries": next_queries,
        "insights": None
    }


def _build_failure_guide_report(error_info, user_input: str) -> dict:
    """
    构建 NL→DSL 失败时的引导报告

    Args:
        error_info: 可以是 NlDslResult、异常对象、或错误字符串
        user_input: 用户原始输入

    Returns:
        final_report dict，引导用户使用结构化查询
    """
    from src.config.context import truncate_log

    # 提取错误信息
    error_msg = "未知错误"
    if hasattr(error_info, 'metadata'):
        # NlDslResult 对象
        error_msg = error_info.metadata.get('final_error', str(error_info))
    elif hasattr(error_info, 'get'):
        # dict
        error_msg = error_info.get('metadata', {}).get('final_error', str(error_info))
    elif isinstance(error_info, Exception):
        error_msg = f"{type(error_info).__name__}: {str(error_info)}"
    else:
        error_msg = str(error_info)

    error_msg = truncate_log(error_msg, 200)

    # 生成失败引导报告
    return {
        "title": "查询遇到问题",
        "time_range": {"start": "", "end": ""},
        "metrics": [],
        "highlights": [
            {
                "type": "negative",
                "text": f"⚠️ 自然语言查询暂时无法处理这个请求：{error_msg}"
            },
            {
                "type": "info",
                "text": "💡 你可以尝试用结构化方式提问，例如："
            },
            {
                "type": "info",
                "text": "  • \"查看 [广告主] 近7天的展示、点击、消耗\""
            },
            {
                "type": "info",
                "text": "  • \"[广告主] 昨天按计划维度的消耗排名\""
            },
            {
                "type": "info",
                "text": "  • \"对比 [广告主] 本月和上月的 CTR 变化\""
            },
        ],
        "data_table": {"columns": [], "rows": []},
        "chart_config": None,
        "next_queries": [
            "查看近7天的广告报表",
            "按计划维度分析数据",
            "对比两个时间段的数据"
        ],
        "insights": None
    }


async def nl_dsl_node(state: dict) -> dict:
    """NL→DSL 查询节点

    封装 Schema RAG 检索 + 查询规划 + DSL 生成 + 安全校验 + 自反思执行 + 结果格式化
    """
    from src.config.context import truncate_log
    from src.nl_dsl.self_reflection_executor import get_self_reflection_executor
    from src.nl_dsl.dsl_generator import get_dsl_generator

    user_input = state.get("user_input", "")
    report_intent = state.get("report_intent_result", {}) or {}
    advertiser_ids = state.get("advertiser_ids", [])

    # 获取已有的 execution_trace
    execution_trace: List[Dict[str, Any]] = state.get("execution_trace", [])

    step_start = time.time()
    event = {"step": "nl_dsl", "status": "started"}
    execution_trace.append(event)
    await _push_sse_event(event)

    logger.info(f"开始NL→DSL查询: 用户输入='{truncate_log(user_input, 100)}', 广告主={advertiser_ids}")

    updates = {
        "execution_trace": execution_trace,
    }

    try:
        # 1. 构造约束
        time_range = report_intent.get("time_range") or {}
        metrics = report_intent.get("metrics", [])
        analysis_type = report_intent.get("chart_type") or state.get("analysis_type", "")

        constraints = {
            "advertiser_ids": advertiser_ids,
            "time_range": time_range,
            "metrics": metrics,
            "analysis_type": analysis_type,
        }

        # 2. 查询规划
        generator = get_dsl_generator()
        plan = await generator.plan_query(user_input, constraints)

        # 3. 执行（含自反思重试）
        executor = get_self_reflection_executor()
        result = await executor.execute_plan(
            plan=plan,
            advertiser_ids=advertiser_ids,
            time_range=time_range,
            display_type_hint=analysis_type,
        )

        # 4. 检查结果
        if not result.metadata.get("success", True):
            # 失败：生成失败引导报告
            final_error = result.metadata.get("final_error", "未知错误")
            final_report = _build_failure_guide_report(result, user_input)
            updates["final_report"] = final_report
            event = {
                "step": "nl_dsl",
                "status": "failed",
                "duration_ms": int((time.time() - step_start) * 1000),
                "error": final_error,
            }
            execution_trace.append(event)
            await _push_sse_event(event)
            logger.info(f"NL→DSL查询失败: 生成失败引导报告, 错误={final_error}, metadata={result.metadata}")
            return updates

        # 5. 成功：构建 final_report
        final_report = await _build_nl_dsl_final_report(result, user_input, report_intent)
        updates["final_report"] = final_report
        updates["nl_dsl_result"] = result.model_dump()

        # 保存 query_context（用于翻页）
        if result.query_context and isinstance(result.query_context, dict):
            updates["query_context"] = result.query_context
        else:
            updates["query_context"] = {}

        event = {
            "step": "nl_dsl",
            "status": "success",
            "duration_ms": int((time.time() - step_start) * 1000),
            "display_type": result.display_type,
            "total_rows": result.metadata.get('total_rows', 0),
        }
        execution_trace.append(event)
        await _push_sse_event(event)

        logger.info(
            f"NL→DSL查询完成: 呈现类型={result.display_type}, "
            f"行数={result.metadata.get('total_rows', 0)}"
        )

    except Exception as e:
        logger.exception(f"NL→DSL节点异常: error={e}")
        event = {
            "step": "nl_dsl",
            "status": "failed",
            "duration_ms": int((time.time() - step_start) * 1000),
            "error": str(e),
        }
        execution_trace.append(event)
        await _push_sse_event(event)
        # 失败引导
        final_report = _build_failure_guide_report(e, user_input)
        updates["final_report"] = final_report

    return updates


async def analysis_node(state: dict) -> dict:
    """
    CoT 分析节点 - 整合所有分析模块的核心节点

    执行流程：
    1. IntentAnalyzer - 字段提取 + 场景识别
    2. CotPlanner - CoT 推理 + 结构化计划生成
    3. FilterExecutor - 执行筛选计划，获取实体 ID
    4. AnalysisExecutor - 执行分析计划，获取图表数据
    5. QualityChecker - 验证结果质量（可跳过）
    6. ReportFormatter - 包装最终报告

    支持 HITL（人机交互）：
    - 如果 CotPlanner 返回 clarification_request，设置 needs_clarification 并返回
    - 如果 QualityChecker 建议 HITL，也可以触发
    - 处理澄清后的重新进入（cot_clarification 和 quality_hitl）
    """
    import time
    from src.tools.custom_report_client import custom_report_client

    # 延迟导入 CoT 分析模块
    try:
        # Ensure backend is in sys.path
        if 'src' not in sys.modules:
            current_dir = os.path.dirname(__file__)
            backend_dir = os.path.join(current_dir, '..', '..')
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)
        from src.analysis.intent_analyzer import IntentAnalyzer, create_intent_analyzer
        from src.analysis.cot_planner import CotPlanner, CotResultStatus, get_cot_planner
        from src.analysis.report_formatter import ReportFormatter
        from src.nl_dsl.filter_executor import FilterExecutor
        from src.nl_dsl.analysis_executor import AnalysisExecutor
        from src.nl_dsl.quality_checker import QualityChecker
        from src.nl_dsl.empty_checker import EmptyResultChecker
        from src.analysis.models import (
            AnalysisPlanResult, FieldContext, CotReasoning, AnalysisTimeRange,
            FilterPlan, FilterResult, AnalysisResult, QualityResult
        )
    except ImportError as e:
        # 如果模块不存在，返回错误
        import traceback
        logger.error(f"CoT analysis modules not found: {e}")
        logger.error(f"sys.path: {sys.path}")
        logger.error(traceback.format_exc())
        return {
            "error": {"type": "analysis_error", "message": f"CoT analysis modules not available: {e}"},
            "execution_trace": [{"step": "init", "status": "failed", "error": "Modules not found"}]
        }

    # 从 state 中获取输入
    user_input = state.get("user_input", "")
    conversation_history = state.get("conversation_history", [])
    advertiser_ids = state.get("advertiser_ids", [])
    report_intent = state.get("report_intent_result", {})

    # 检查是否是澄清后重新进入
    pending_clarification_input = state.get("pending_clarification_input")
    clarification_type = (state.get("clarification") or {}).get("type")
    is_reentry = pending_clarification_input is not None and clarification_type in ["cot_clarification", "quality_hitl"]

    # 从 state 中恢复之前的上下文（如果是重新进入）
    previous_field_context = None
    if is_reentry and state.get("field_context"):
        try:
            previous_field_context = FieldContext(**state["field_context"])
        except Exception as e:
            logger.warning(f"Failed to reconstruct previous field_context: {e}")
            previous_field_context = None

    # 质量 HITL：检查是否选择继续（跳过 QualityChecker）
    skip_quality_check = False
    if clarification_type == "quality_hitl" and pending_clarification_input == "continue":
        skip_quality_check = True
        logger.info("[AnalysisNode] Quality HITL: user chose to continue, skipping QualityChecker")

    # 初始化执行追踪
    execution_trace: List[Dict[str, Any]] = []
    start_time = time.time()

    # 结果更新字典
    updates = {
        "execution_trace": execution_trace,
        "error": None,
        "needs_clarification": False,
        "hitl_request": None,
        "pending_clarification_input": None  # 清除待处理的澄清输入
    }

    try:
        # ========== 步骤 1: IntentAnalyzer - 字段提取 ==========
        step_start = time.time()
        event = {"step": "intent_analyzer", "status": "started"}
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"[AnalysisNode] Step 1: IntentAnalyzer started")

        # 如果 report_intent_result 已经存在（来自 report_intent_node），
        # 重用其中已经提取好的字段，特别是已经转换好的 advertiser_ids
        if report_intent:
            # 从 report_intent_result 中提取已处理好的信息
            ri_advertiser_ids = report_intent.get("advertiser_ids", [])
            ri_time_range = report_intent.get("time_range")
            ri_metrics = report_intent.get("metrics", [])
            ri_ad_level = report_intent.get("ad_level")

            # 转换时间范围格式
            converted_time_range = None
            if ri_time_range:
                # report_intent.time_range 已经是 dict 格式: {start_date, end_date, unit}
                converted_time_range = AnalysisTimeRange(
                    start_date=ri_time_range["start_date"],
                    end_date=ri_time_range["end_date"],
                    granularity=ri_time_range["unit"]
                )

            # 构建 FieldContext，重用已经提取的信息
            # 特别是 advertiser_ids 已经完成了名称→ID转换
            field_context = FieldContext(
                advertiser_ids=ri_advertiser_ids if ri_advertiser_ids else None,
                time_range=converted_time_range,
                target_level=ri_ad_level,
                metrics=ri_metrics if ri_metrics else None,
                audience_dimension=None,
                compare_time_range=None,
                entity_ids=None,
                additional_fields={}
            )

            updates["field_context"] = field_context.model_dump() if field_context else None

            event = {
                "step": "intent_analyzer",
                "status": "success",
                "duration_ms": int((time.time() - step_start) * 1000),
                "extracted_fields": {
                    "metrics": getattr(field_context, "metrics", []),
                    "target_level": getattr(field_context, "target_level", None),
                    "time_range": getattr(field_context, "time_range", None).model_dump()
                        if getattr(field_context, "time_range", None) is not None else None
                },
            }
            execution_trace.append(event)
            await _push_sse_event(event)
            logger.info(f"[AnalysisNode] Step 1: reused fields from report_intent, advertiser_ids={ri_advertiser_ids}")
        else:
            # 没有 report_intent，重新提取
            try:
                intent_analyzer = create_intent_analyzer()
                intent_result = intent_analyzer.analyze(
                    user_input=user_input,
                    conversation_history=conversation_history,
                )

                field_context = intent_result.field_context
                updates["field_context"] = field_context.model_dump() if field_context else None

                event = {
                    "step": "intent_analyzer",
                    "status": "success",
                    "duration_ms": int((time.time() - step_start) * 1000),
                    "extracted_fields": {
                        "metrics": getattr(field_context, "metrics", []),
                        "target_level": getattr(field_context, "target_level", None),
                        "time_range": getattr(field_context, "time_range", None).model_dump()
                            if getattr(field_context, "time_range", None) is not None else None
                    },
                }
                execution_trace.append(event)
                await _push_sse_event(event)
                logger.info(f"[AnalysisNode] Step 1: IntentAnalyzer completed")
            except Exception as e:
                logger.exception(f"[AnalysisNode] Step 1 failed: {e}")
                event = {
                    "step": "intent_analyzer",
                    "status": "failed",
                    "error": str(e),
                    "duration_ms": int((time.time() - step_start) * 1000),
                }
                execution_trace.append(event)
                await _push_sse_event(event)
                # 继续执行 - CotPlanner 可以处理没有 field_context 的情况
                field_context = None

        # 如果是重新进入且有之前的 field_context，优先使用之前的（结合新的）
        if is_reentry and previous_field_context:
            # 合并：保留之前的上下文，但使用新提取的字段（如果有）
            if field_context:
                # 简单的合并策略：如果新的 field_context 有字段，优先使用新的
                merged_metrics = list(set((previous_field_context.metrics or []) + (field_context.metrics or [])))
                previous_field_context.metrics = merged_metrics
                if field_context.target_level:
                    previous_field_context.target_level = field_context.target_level
                if field_context.time_range:
                    previous_field_context.time_range = field_context.time_range
            field_context = previous_field_context
            logger.info("[AnalysisNode] Re-entry: using merged previous field_context")

        # ========== 步骤 2: CotPlanner - 生成分析计划 ==========
        step_start = time.time()
        event = {"step": "cot_planner", "status": "started"}
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"[AnalysisNode] Step 2: CotPlanner started")

        cot_planner = get_cot_planner()
        cot_result = await cot_planner.plan(
            user_input=user_input,
            conversation_history=conversation_history,
            field_context=field_context,
            advertisers=[]  # TODO: pass actual advertiser dicts if needed
        )

        if cot_result.status == CotResultStatus.NEEDS_CLARIFICATION:
            # 需要澄清 - HITL 路径
            clarification = cot_result.clarification
            hitl_request = {
                "question": clarification.question,
                "missing_fields": clarification.missing_fields,
                "options": clarification.options
            }

            updates.update({
                "needs_clarification": True,
                "clarification": build_clarification_state({
                    "type": "cot_clarification",
                    "question": clarification.question,
                    "options": clarification.options,
                    "allow_custom_input": True,
                    "missing_fields": clarification.missing_fields
                }).get("clarification"),
                "hitl_request": hitl_request,
                "cot_reasoning": cot_result.reasoning.model_dump() if cot_result.reasoning else None
            })

            event = {
                "step": "cot_planner",
                "status": "hitl_required",
                "duration_ms": int((time.time() - step_start) * 1000),
            }
            execution_trace.append(event)
            await _push_sse_event(event)
            logger.info(f"[AnalysisNode] Step 2: HITL required - clarification needed")
            return updates

        if cot_result.status != CotResultStatus.SUCCESS:
            # 规划失败
            error_msg = f"CoT planning failed: {cot_result.status}"
            logger.error(f"[AnalysisNode] {error_msg}")

            event = {
                "step": "cot_planner",
                "status": "failed",
                "error": error_msg,
                "duration_ms": int((time.time() - step_start) * 1000),
            }
            execution_trace.append(event)
            await _push_sse_event(event)

            # 生成错误报告
            report_formatter = ReportFormatter()
            final_report = report_formatter.format_error(
                error_type="cot_planning_error",
                message="无法生成分析计划，请尝试重新表述您的问题",
                reason=error_msg,
                suggestions=["尝试用更简单的方式描述您的需求", "确认指标和时间范围是否正确"],
                recommended_queries=["查看近7天的广告报表", "按计划维度分析数据"]
            )

            updates.update({
                "final_report": final_report,
                "error": {"type": "cot_planning_error", "message": error_msg}
            })
            return updates

        # 规划成功
        analysis_plan_result = cot_result.plan
        updates.update({
            "analysis_plan": analysis_plan_result.model_dump(),
            "cot_reasoning": cot_result.reasoning.model_dump() if cot_result.reasoning else None
        })

        event = {
            "step": "cot_planner",
            "status": "success",
            "duration_ms": int((time.time() - step_start) * 1000),
            "analysis_type": analysis_plan_result.analysis_plan.analysis_type.value if hasattr(analysis_plan_result.analysis_plan.analysis_type, "value") else analysis_plan_result.analysis_plan.analysis_type
        }
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"[AnalysisNode] Step 2: CotPlanner completed successfully")

        # ========== 步骤 3: FilterExecutor - 执行筛选计划 ==========
        step_start = time.time()
        event = {"step": "filter_executor", "status": "started"}
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"[AnalysisNode] Step 3: FilterExecutor started")

        filter_executor = FilterExecutor(es_client=custom_report_client.es_client)

        # 构建时间范围
        plan_time_range = analysis_plan_result.analysis_plan.time_range
        time_range_dict = {
            "start_date": plan_time_range.start_date,
            "end_date": plan_time_range.end_date
        }

        filter_result = await filter_executor.execute(
            filter_plan=analysis_plan_result.filter_plan,
            advertiser_ids=advertiser_ids,
            time_range=time_range_dict
        )

        updates["filter_result"] = filter_result.model_dump()

        event = {
            "step": "filter_executor",
            "status": "success",
            "duration_ms": int((time.time() - step_start) * 1000),
            "entity_count": filter_result.total_count,
            "entity_level": filter_result.entity_level
        }
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"[AnalysisNode] Step 3: FilterExecutor completed, got {filter_result.total_count} entities")

        # ========== 步骤 3.5: EmptyResultChecker - 空结果检查 ==========
        step_start = time.time()
        event = {"step": "empty_result_checker", "status": "started"}
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"[AnalysisNode] Step 3.5: EmptyResultChecker started")

        empty_checker = EmptyResultChecker(es_client=custom_report_client.es_client)
        empty_check_result = await empty_checker.async_check(
            analysis_plan=analysis_plan_result.analysis_plan,
            advertiser_ids=advertiser_ids,
            filter_result=filter_result
        )

        if empty_check_result.found_error:
            event = {
                "step": "empty_result_checker",
                "status": "empty_data",
                "duration_ms": int((time.time() - step_start) * 1000),
                "error_type": empty_check_result.error_type.value if hasattr(empty_check_result.error_type, "value") else empty_check_result.error_type
            }
            execution_trace.append(event)
            await _push_sse_event(event)
            logger.info(f"[AnalysisNode] Step 3.5: EmptyResultChecker found empty data, skipping AnalysisExecutor")

            # 直接生成空结果报告
            report_formatter = ReportFormatter()
            final_report = report_formatter.format_empty_result(
                empty_check_result=empty_check_result,
                analysis_plan_result=analysis_plan_result,
                filter_result=filter_result,
                user_input=user_input
            )

            updates["final_report"] = final_report
            total_duration = int((time.time() - start_time) * 1000)
            event = {
                "step": "complete",
                "status": "empty",
                "total_duration_ms": total_duration
            }
            execution_trace.append(event)
            await _push_sse_event(event)
            return updates

        event = {
            "step": "empty_result_checker",
            "status": "success",
            "duration_ms": int((time.time() - step_start) * 1000),
        }
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"[AnalysisNode] Step 3.5: EmptyResultChecker passed, continuing to AnalysisExecutor")

        # ========== 步骤 4: AnalysisExecutor - 执行分析计划 ==========
        step_start = time.time()
        event = {"step": "analysis_executor", "status": "started"}
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"[AnalysisNode] Step 4: AnalysisExecutor started")

        # 构建 entity_name 映射：ID -> 名称
        from src.tools.hierarchy_utils import get_entity_names
        entity_name_resolver = {}
        entity_ids = filter_result.entity_ids
        entity_level = filter_result.entity_level
        if entity_ids and entity_level and len(entity_ids) > 0:
            entity_name_resolver = await get_entity_names(entity_level, entity_ids)

        analysis_executor = AnalysisExecutor(
            es_client=custom_report_client.es_client,
            entity_name_resolver=entity_name_resolver
        )

        analysis_result = await analysis_executor.execute(
            analysis_plan=analysis_plan_result.analysis_plan,
            entity_ids=filter_result.entity_ids,
            entity_level=filter_result.entity_level,
            advertiser_ids=advertiser_ids,
            time_range=time_range_dict
        )

        updates["chart_data"] = analysis_result.model_dump()

        event = {
            "step": "analysis_executor",
            "status": "success",
            "duration_ms": int((time.time() - step_start) * 1000),
            "has_data": analysis_result.success and (analysis_result.data_table is not None or analysis_result.chart_data is not None)
        }
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"[AnalysisNode] Step 4: AnalysisExecutor completed")

        # ========== 步骤 5: QualityChecker - 质量检查（可跳过） ==========
        quality_result = None
        if skip_quality_check:
            step_start = time.time()
            event = {"step": "quality_checker", "status": "skipped"}
            execution_trace.append(event)
            await _push_sse_event(event)
            logger.info("[AnalysisNode] Step 5: QualityChecker skipped (user chose to continue)")
            # 创建一个空的 QualityResult
            from src.nl_dsl.quality_checker import QualityResult as QCResult
            from src.analysis.models import QualityIssue
            quality_result = QCResult(passed=True, issues=[])
            updates["quality_result"] = quality_result.model_dump()
        else:
            step_start = time.time()
            event = {"step": "quality_checker", "status": "started"}
            execution_trace.append(event)
            await _push_sse_event(event)
            logger.info(f"[AnalysisNode] Step 5: QualityChecker started")

            quality_checker = QualityChecker()
            quality_result = quality_checker.check(
                analysis_result=analysis_result
            )

            updates["quality_result"] = quality_result.model_dump()

            # 检查是否需要 HITL
            needs_hitl = any(
                issue.severity == "error" and issue.suggested_action == "hitl"
                for issue in quality_result.issues
            )

            if needs_hitl:
                # 质量检查建议 HITL
                hitl_request = {
                    "question": "数据质量存在问题，是否继续查看结果？",
                    "missing_fields": [],
                    "options": [
                        {"value": "continue", "label": "继续查看结果"},
                        {"value": "rephrase", "label": "重新表述问题"}
                    ],
                    "quality_issues": [
                        {"type": issue.check_type.value, "message": issue.message, "severity": issue.severity}
                        for issue in quality_result.issues
                    ]
                }

                updates.update({
                    "needs_clarification": True,
                    "clarification": build_clarification_state({
                        "type": "quality_hitl",
                        "question": "数据质量存在问题，是否继续查看结果？",
                        "options": [
                            {"value": "continue", "label": "继续查看结果"},
                            {"value": "rephrase", "label": "重新表述问题"}
                        ],
                        "allow_custom_input": False,
                        "missing_fields": []
                    }).get("clarification"),
                    "hitl_request": hitl_request
                })

                event = {
                    "step": "quality_checker",
                    "status": "hitl_required",
                    "duration_ms": int((time.time() - step_start) * 1000),
                    "issue_count": len(quality_result.issues)
                }
                execution_trace.append(event)
                await _push_sse_event(event)
                logger.info(f"[AnalysisNode] Step 5: QualityChecker suggests HITL")
                return updates

            event = {
                "step": "quality_checker",
                "status": "success",
                "duration_ms": int((time.time() - step_start) * 1000),
                "issue_count": len(quality_result.issues),
                "warning_count": len([i for i in quality_result.issues if i.severity == "warning"])
            }
            execution_trace.append(event)
            await _push_sse_event(event)
            logger.info(f"[AnalysisNode] Step 5: QualityChecker completed with {len(quality_result.issues)} issues")

        # ========== 步骤 6: ReportFormatter - 生成最终报告 ==========
        step_start = time.time()
        event = {"step": "report_formatter", "status": "started"}
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"[AnalysisNode] Step 6: ReportFormatter started")

        report_formatter = ReportFormatter()
        final_report = await report_formatter.format(
            analysis_plan_result=analysis_plan_result,
            analysis_result=analysis_result,
            quality_result=quality_result,
            filter_result=filter_result,
            user_input=user_input,
            cot_reasoning=cot_result.reasoning
        )

        updates["final_report"] = final_report

        event = {
            "step": "report_formatter",
            "status": "success",
            "duration_ms": int((time.time() - step_start) * 1000),
            "report_type": final_report.get("report_type", "unknown")
        }
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"[AnalysisNode] Step 6: ReportFormatter completed")

        # ========== 完成 ==========
        total_duration = int((time.time() - start_time) * 1000)
        event = {
            "step": "complete",
            "status": "success",
            "total_duration_ms": total_duration
        }
        execution_trace.append(event)
        await _push_sse_event(event)
        logger.info(f"[AnalysisNode] All steps completed in {total_duration}ms")

        return updates

    except Exception as e:
        # 全局异常处理 - 生成友好的错误报告
        logger.exception(f"[AnalysisNode] Unexpected error: {e}")

        error_duration = int((time.time() - start_time) * 1000)
        event = {
            "step": "error",
            "status": "failed",
            "error": str(e),
            "duration_ms": error_duration
        }
        execution_trace.append(event)
        await _push_sse_event(event)

        # 尝试生成错误报告
        try:
            from src.analysis.report_formatter import ReportFormatter
            report_formatter = ReportFormatter()
            final_report = report_formatter.format_error(
                error_type="analysis_error",
                message="分析过程中发生错误",
                reason=str(e),
                suggestions=["请稍后重试", "尝试用更简单的方式描述您的需求"],
                recommended_queries=["查看近7天的广告报表", "按计划维度分析数据"]
            )
        except:
            # 如果 ReportFormatter 也失败，返回简单的错误报告
            final_report = {
                "report_type": "error",
                "title": "分析遇到问题",
                "highlights": [
                    {"type": "negative", "text": f"⚠️ 分析过程中发生错误: {str(e)}"}
                ],
                "data_table": {"columns": [], "rows": []},
                "next_queries": [
                    "查看近7天的广告报表",
                    "按计划维度分析数据"
                ]
            }

        updates.update({
            "final_report": final_report,
            "error": {"type": "analysis_error", "message": str(e)}
        })

        return updates
