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
