from src.tools.time_parser import parse_time_range

def test_parse_time_range_today():
    result = parse_time_range.invoke("看今天的数据")
    assert result.unit == "day"
    assert result.start_date == result.end_date

def test_parse_time_range_yesterday():
    result = parse_time_range.invoke("看昨天的CTR")
    assert result.unit == "day"
    assert result.start_date == result.end_date

def test_parse_time_range_last_week():
    result = parse_time_range.invoke("上周的曝光")
    assert result.unit == "day"
    assert result.start_date != result.end_date

def test_parse_time_range_default():
    result = parse_time_range.invoke("看数据")
    assert result.unit == "day"
    # Should default to last 7 days

def test_parse_time_range_last_3_months():
    result = parse_time_range.invoke("最近三个月的点击")
    assert result.unit == "month"
    # Start date should be 3 months ago, first day of month
    assert result.start_date.endswith("-01")
    assert result.start_date != result.end_date

def test_parse_time_range_last_3_months_variations():
    variants = [
        "近3个月的曝光",
        "最近三个月的数据",
        "近三个月的CTR",
        "最近3个月的花费"
    ]
    for query in variants:
        result = parse_time_range.invoke(query)
        assert result.unit == "month", f"Failed for: {query}"
        assert result.start_date.endswith("-01"), f"Failed for: {query}"

def test_parse_time_range_this_month():
    result = parse_time_range.invoke("本月的点击")
    assert result.unit == "day"
    assert result.start_date.endswith("-01")

def test_parse_time_range_last_month():
    result = parse_time_range.invoke("上个月的曝光")
    assert result.unit == "day"
    assert result.start_date.endswith("-01")
    # Should be previous month's first day to last day
