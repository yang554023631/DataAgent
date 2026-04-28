"""
各节点实现占位符
"""

import time
from src.tools.executor import execute_ad_report_query
from src.agents.nlu_agent import nlu_agent
from src.agents.planner_agent import planner_agent
from src.agents.analyst_agent import analyst_agent
from src.agents.reporter_agent import reporter_agent, format_comparison_report
from src.agents.insight_agent import insight_agent, insights_to_highlights
from src.services.advertiser_service import get_all_advertisers


def _generate_suggested_queries(advertiser_name: str) -> list:
    """为广告主生成多样化的推荐查询"""
    templates = [
        "{name} 最近三个月哪些广告表现好？哪些广告表现不好？",
        "{name} 最近三个月的点击量按性别和月细分",
        "{name} 最近三个月 CTR 表现最好和最差的广告分别是哪些？",
    ]
    return [t.format(name=advertiser_name) for t in templates]

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

        return result
    except Exception as e:
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

        return {
            "query_request": result["query_request"],  # 向后兼容
            "query_requests": query_requests,
            "query_warnings": result["query_warnings"],
            "insight_queries": result.get("insight_queries", {}),
            "error": None
        }
    except Exception as e:
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

        return {
            "analysis_result": result,
            "drill_down_level": state.get("drill_down_level", 0),
            "needs_drill_down": False,
            "error": None
        }
    except Exception as e:
        return {
            "analysis_result": None,
            "drill_down_level": state.get("drill_down_level", 0),
            "needs_drill_down": False,
            "error": {"type": "analyst_error", "message": str(e)}
        }

async def reporter_node(state: dict) -> dict:
    """报告生成节点（支持对比查询 + 洞察高亮）"""
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

        return {
            "final_report": final_report,
            "error": None
        }
    except Exception as e:
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

        return {
            "insights": merged_result,
            "error": None
        }
    except Exception as e:
        return {
            "insights": None,
            "error": {"type": "insight_error", "message": str(e)}
        }
