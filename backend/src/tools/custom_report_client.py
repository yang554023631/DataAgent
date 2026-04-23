import httpx
import time
from typing import Optional
from src.config.settings import settings
from src.models import QueryRequest, QueryResult

class CustomReportClient:
    """CustomReport 服务 HTTP 客户端"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.CUSTOM_REPORT_URL
        self.timeout = settings.CUSTOM_REPORT_TIMEOUT

    async def execute_query(self, query_request: QueryRequest) -> QueryResult:
        """执行报表查询"""
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/report/query",
                    json=query_request.model_dump()
                )
                response.raise_for_status()
                data = response.json()

                execution_time = int((time.time() - start_time) * 1000)

                return QueryResult(
                    success=True,
                    total_rows=len(data.get("data", [])),
                    data=data.get("data", []),
                    execution_time_ms=execution_time
                )

        except httpx.TimeoutException:
            return QueryResult(
                success=False,
                error_type="timeout",
                message="查询超时，请缩小时间范围或减少维度",
                suggestions=["改成按月汇总", "减少分组维度", "缩小时间范围到最近7天"]
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return QueryResult(
                    success=False,
                    error_type="empty",
                    message="该条件下没有数据",
                    suggestions=["扩大时间范围", "调整过滤条件"]
                )
            return QueryResult(
                success=False,
                error_type="http_error",
                message=f"查询失败: {str(e)}"
            )

        except Exception as e:
            return QueryResult(
                success=False,
                error_type="unknown",
                message=f"未知错误: {str(e)}"
            )

# 单例
custom_report_client = CustomReportClient()
