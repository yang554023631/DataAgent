"""
各节点实现占位符
"""

import time
import logging
from src.tools.executor import execute_ad_report_query
from src.agents.nlu_agent import nlu_agent
from src.agents.planner_agent import planner_agent
from src.agents.analyst_agent import analyst_agent
from src.agents.reporter_agent import reporter_agent, format_comparison_report
from src.agents.insight_agent import insight_agent, insights_to_highlights
from src.services.advertiser_service import get_all_advertisers
from src.intent.top_classifier import get_top_classifier
from src.intent.report_intent import get_report_intent_analyzer
from src.intent.clarify_node import clarify_node as clarify_node_impl, build_clarification_state
from src.intent.reject_node import reject_node as reject_node_impl

logger = logging.getLogger(__name__)


def _generate_suggested_queries(advertiser_name: str) -> list:
    """为广告主生成多样化的推荐查询"""
    templates = [
        "{name} 最近三个月哪些广告表现好？哪些广告表现不好？",
        "{name} 最近三个月的点击量按性别和月细分",
        "{name} 最近三个月 CTR 表现最好和最差的广告分别是哪些？",
    ]
    return [t.format(name=advertiser_name) for t in templates]


def _resolve_advertiser_from_feedback(feedback: str) -> list:
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
    results = get_advertiser_by_name(feedback)
    return [r["id"] for r in results]

async def nlu_node(state: dict) -> dict:
    """意图理解节点"""
    user_input = state.get("user_input", "")
    conversation_history = state.get("conversation_history", [])
    existing_advertiser_ids = state.get("advertiser_ids", [])

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
        advertisers = get_all_advertisers()
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
            advertisers = get_all_advertisers()
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
        advertisers = get_all_advertisers()
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

    logger.info(f"开始顶层意图分类: 用户输入='{user_input[:100]}'")

    classifier = get_top_classifier()
    result = await classifier.classify(user_input, conversation_history)

    updates = {
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
        logger.info(f"顶层意图分类完成: 分类={result.category}, 置信度={result.confidence:.2f}, 触发澄清=True")
    else:
        logger.info(f"顶层意图分类完成: 分类={result.category}, 置信度={result.confidence:.2f}, 来源={result.source}")

    return updates


async def report_intent_node(state: dict) -> dict:
    """报表意图识别节点"""
    user_input = state.get("user_input", "")
    conversation_history = state.get("conversation_history", [])
    existing_advertiser_ids = list(state.get("advertiser_ids", []))

    # --- 澄清回填：上一轮是 missing_advertiser 澄清时，把用户选择的广告主直接填入 ---
    clarification_info = state.get("clarification", {})
    last_clarification_type = clarification_info.get("type", "")
    pending_input = state.get("pending_clarification_input", "")

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

    updates = {}

    # 写入路由信息到 state（所有路径都有 route_info）
    if route_info:
        updates["query_route"] = route_info["route"]
        updates["route_reason"] = route_info["reason"]
        updates["analysis_type"] = route_info["analysis_type"]

    if final_report:
        # 纯广告主查询，直接返回 final_report
        updates["final_report"] = final_report
        updates["needs_clarification"] = False
        logger.info(f"报表意图识别完成: 检测到纯广告主查询, 路由={route_info['route']}")
    else:
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
            logger.info(f"报表意图识别完成: 触发澄清=True, 类型={clarification.type}, 路由={route_info['route']}")
        else:
            # 不需要澄清，确保标志位为 False
            updates["needs_clarification"] = False
            if result:
                log_msg = f"报表意图识别完成: 广告主={result.advertiser_ids}, 时间={result.time_range and result.time_range.start_date + '~' + result.time_range.end_date}, 指标={result.metrics}, 层级={result.ad_level}"
                log_msg += f", 路由={route_info['route']}, 原因={route_info['reason']}"
                logger.info(log_msg)
            else:
                logger.info(f"报表意图识别完成: 结果为空, 路由={route_info['route']}")

    return updates


async def clarify_node_entry(state: dict) -> dict:
    """澄清节点入口（包装 clarify_node）"""
    return await clarify_node_impl(state)


async def reject_node_entry(state: dict) -> dict:
    """拒答节点入口（包装 reject_node）"""
    return await reject_node_impl(state)
