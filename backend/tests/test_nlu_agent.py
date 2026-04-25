import pytest
import asyncio
from src.agents.nlu_agent import nlu_agent

@pytest.mark.asyncio
async def test_nlu_agent_simple():
    result = await nlu_agent("看上周的曝光点击")
    assert "metrics" in result
    assert "time_range" in result
    assert result["is_incremental"] == False
    assert "ambiguity" in result
