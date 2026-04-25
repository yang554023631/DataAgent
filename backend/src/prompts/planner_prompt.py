PLANNER_PROMPT = """
你是广告报表查询规划专家。

请把查询意图转换成合法的 QueryRequest。

查询意图：
{query_intent}

用户澄清反馈：
{user_feedback}

请输出：
{
    "query_request": {
        "index_type": "general",
        "time_range": {},
        "metrics": [],
        "group_by": [],
        "filters": [],
        "chart_config": {}
    },
    "query_warnings": []
}
"""
