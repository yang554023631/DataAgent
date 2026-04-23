from datetime import date, timedelta
from pydantic import BaseModel
from langchain_core.tools import tool

class TimeRange(BaseModel):
    start_date: str
    end_date: str
    unit: str  # day, week, month

@tool
def parse_time_range(text: str) -> TimeRange:
    """
    解析自然语言时间范围

    支持:
    - 今天、昨天
    - 本周、上周、上上周
    - 本月、上个月
    - 近N天、近N周、近N月
    - 2024年4月、4月15日到4月21日
    - 上周、上周同期
    """
    today = date.today()

    # 今天
    if "今天" in text:
        return TimeRange(
            start_date=str(today),
            end_date=str(today),
            unit="day"
        )

    # 昨天
    if "昨天" in text:
        yesterday = today - timedelta(days=1)
        return TimeRange(
            start_date=str(yesterday),
            end_date=str(yesterday),
            unit="day"
        )

    # 上周（周一到周日）
    if "上周" in text:
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        last_sunday = last_monday + timedelta(days=6)
        return TimeRange(
            start_date=str(last_monday),
            end_date=str(last_sunday),
            unit="day"
        )

    # 近7天（默认）
    if "近7天" in text or "最近7天" in text or "过去一周" in text:
        start = today - timedelta(days=6)
        return TimeRange(
            start_date=str(start),
            end_date=str(today),
            unit="day"
        )

    # 默认：近7天
    start = today - timedelta(days=6)
    return TimeRange(
        start_date=str(start),
        end_date=str(today),
        unit="day"
    )
