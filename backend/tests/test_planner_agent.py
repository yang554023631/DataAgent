import pytest
import asyncio
from src.agents.planner_agent import planner_agent

@pytest.mark.asyncio
async def test_planner_agent_basic():
    query_intent = {
        "time_range": {"start_date": "2024-04-15", "end_date": "2024-04-21", "unit": "day"},
        "metrics": ["impressions", "clicks"],
        "group_by": ["campaign_id"],
        "filters": []
    }
    result = await planner_agent(query_intent)
    assert "query_request" in result
    assert "query_warnings" in result
    assert result["query_request"]["index_type"] == "general"

@pytest.mark.asyncio
async def test_planner_agent_with_audience_dim():
    query_intent = {
        "time_range": {"start_date": "2024-04-15", "end_date": "2024-04-21", "unit": "day"},
        "metrics": ["impressions", "ctr"],
        "group_by": ["audience_os"],
        "filters": []
    }
    result = await planner_agent(query_intent)
    assert result["query_request"]["index_type"] == "audience"
    # Should have auto-added audience_type filter
    assert len(result["query_request"]["filters"]) == 1
