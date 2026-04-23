from langchain_core.tools import tool
from src.models import QueryRequest
from .custom_report_client import custom_report_client

@tool
async def execute_ad_report_query(query_request: dict) -> dict:
    """
    调用 CustomReport 服务执行广告报表查询

    Args:
        query_request: 查询请求Dict，符合QueryRequest模型结构

    Returns:
        查询结果Dict
    """
    req = QueryRequest(**query_request)
    result = await custom_report_client.execute_query(req)
    return result.model_dump()
