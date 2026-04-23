import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch, AsyncMock
from src.graph.nodes import executor_node

@pytest.mark.asyncio
async def test_executor_node_with_valid_query():
    with patch("src.graph.nodes.execute_ad_report_query") as mock_tool:
        mock_tool.ainvoke = AsyncMock(return_value={
            "success": True,
            "total_rows": 10,
            "data": [{"date": "2024-04-01", "impressions": 1000}],
            "execution_time_ms": 150
        })

        state = {
            "query_request": {
                "time_range": {"start": "2024-04-01", "end": "2024-04-07"},
                "metrics": ["impressions"]
            }
        }

        result = await executor_node(state)
        assert result["query_result"]["success"] is True
        assert result["query_result"]["total_rows"] == 10
        assert result["error"] is None

@pytest.mark.asyncio
async def test_executor_node_no_query():
    state = {"query_request": None}
    result = await executor_node(state)
    assert result["query_result"] is None
    assert result["error"] is not None
