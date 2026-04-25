import pytest
from src.agents.analyst_agent import analyst_agent


@pytest.mark.asyncio
async def test_analyst_agent():
    query_result = {
        "data": [
            {"name": "渠道A", "impressions": 1000, "wow_change": 0.5},
            {"name": "渠道B", "impressions": 2000, "wow_change": -0.1},
        ]
    }
    query_request = {"metrics": ["impressions"]}

    result = await analyst_agent(query_result, query_request)
    assert "anomalies" in result
    assert "rankings" in result


@pytest.mark.asyncio
async def test_analyst_agent_no_anomalies():
    query_result = {
        "data": [
            {"name": "渠道A", "impressions": 1000, "wow_change": 0.1},
            {"name": "渠道B", "impressions": 2000, "wow_change": -0.1},
            {"name": "渠道C", "impressions": 1500, "wow_change": 0.05},
        ]
    }
    query_request = {"metrics": ["impressions"]}

    result = await analyst_agent(query_result, query_request)
    assert len(result["anomalies"]) == 0
    assert "数据表现平稳，未发现显著异常" in result["insights"]
    assert result["summary"] == "整体数据表现平稳"


@pytest.mark.asyncio
async def test_analyst_agent_multiple_metrics():
    query_result = {
        "data": [
            {"name": "渠道A", "impressions": 1000, "ctr": 0.01, "wow_change": 0.3},
            {"name": "渠道B", "impressions": 2000, "ctr": 0.02, "wow_change": -0.1},
            {"name": "渠道C", "impressions": 1500, "ctr": 0.015, "wow_change": 0.5},
            {"name": "渠道D", "impressions": 800, "ctr": 0.10, "wow_change": -0.25},
        ]
    }
    query_request = {"metrics": ["impressions", "ctr"]}

    result = await analyst_agent(query_result, query_request)
    assert len(result["anomalies"]) > 0
    assert "rankings" in result
