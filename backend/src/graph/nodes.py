"""
各节点实现占位符
"""

import time
from src.tools.executor import execute_ad_report_query

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
