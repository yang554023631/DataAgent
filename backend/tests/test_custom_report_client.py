import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import httpx
import pytest
from unittest.mock import AsyncMock, patch
from src.tools.custom_report_client import CustomReportClient
from src.models import QueryRequest

@pytest.mark.asyncio
async def test_execute_query_timeout():
    client = CustomReportClient(base_url="http://test")

    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.TimeoutException("Timeout")

    with patch("httpx.AsyncClient", return_value=mock_client):
        mock_client.__aenter__.return_value = mock_client

        result = await client.execute_query(
            QueryRequest(
                time_range={"start_date": "2024-04-01", "end_date": "2024-04-07"},
                metrics=["impressions"]
            )
        )

        assert result.success is False
        assert result.error_type == "timeout"
        assert len(result.suggestions) > 0

@pytest.mark.asyncio
async def test_execute_query_success():
    client = CustomReportClient(base_url="http://test")

    # Use regular Mock for response since raise_for_status and json are sync
    from unittest.mock import Mock
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "data": [
            {"date": "2024-04-01", "impressions": 1000},
            {"date": "2024-04-02", "impressions": 2000},
        ]
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_client):
        mock_client.__aenter__.return_value = mock_client

        result = await client.execute_query(
            QueryRequest(
                time_range={"start_date": "2024-04-01", "end_date": "2024-04-07"},
                metrics=["impressions"]
            )
        )

        assert result.success is True
        assert result.total_rows == 2
        assert len(result.data) == 2
        assert result.execution_time_ms is not None

@pytest.mark.asyncio
async def test_execute_query_404():
    client = CustomReportClient(base_url="http://test")

    response_mock = AsyncMock()
    response_mock.status_code = 404
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.HTTPStatusError(
        "Not found", request=AsyncMock(), response=response_mock
    )

    with patch("httpx.AsyncClient", return_value=mock_client):
        mock_client.__aenter__.return_value = mock_client

        result = await client.execute_query(
            QueryRequest(
                time_range={"start_date": "2024-04-01", "end_date": "2024-04-07"},
                metrics=["impressions"]
            )
        )

        assert result.success is False
        assert result.error_type == "empty"
        assert len(result.suggestions) > 0
