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
