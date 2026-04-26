from src.tools.term_mapper import map_metrics, map_dimensions

def test_map_metrics_basic():
    result = map_metrics.invoke("看曝光和点击率")
    assert "impressions" in result
    assert "ctr" in result

def test_map_metrics_empty():
    result = map_metrics.invoke("随便看看")
    assert "impressions" in result  # defaults

def test_map_dimensions():
    result = map_dimensions.invoke("按渠道看效果")
    assert "campaign_id" in result


def test_map_dimensions_gender_only():
    """只按性别细分，不应该包含月份"""
    result = map_dimensions.invoke("电商家居_40_new 最近三个月的数据 按 性别 细分")
    assert result == ["audience_gender"], f"期望只包含性别，实际: {result}"


def test_map_dimensions_gender_and_month():
    """按性别和月份细分，应该同时包含两个维度"""
    result = map_dimensions.invoke("电商家居_40_new 最近三个月的数据 按 性别 和 月细分")
    assert "audience_gender" in result, f"应该包含性别，实际: {result}"
    assert "data_month" in result, f"应该包含月份，实际: {result}"
    assert len(result) == 2, f"应该只有2个维度，实际: {result}"


def test_map_dimensions_month_only():
    """只按月份细分，应该只包含月份"""
    result = map_dimensions.invoke("电商家居_40_new 最近三个月的数据 按月细分")
    assert result == ["data_month"], f"期望只包含月份，实际: {result}"


def test_map_dimensions_gender_and_age():
    """按性别和年龄细分"""
    result = map_dimensions.invoke("最近三个月的点击量按性别和年龄细分")
    assert "audience_gender" in result
    assert "audience_age" in result
    assert len(result) == 2


def test_map_dimensions_three_months_no_month():
    """\"三个月\"中的\"月\"不应该被误匹配为月份维度"""
    result = map_dimensions.invoke("看最近三个月的数据")
    assert result == [], f"不应该匹配任何维度，实际: {result}"


def test_map_dimensions_with_spaces():
    """用户输入带有空格，如\"按 性别 细分\"应该能正确匹配"""
    result = map_dimensions.invoke("按 性别 细分")
    assert result == ["audience_gender"], f"期望只包含性别，实际: {result}"

    result2 = map_dimensions.invoke("按 月份 细分")
    assert result2 == ["data_month"], f"期望只包含月份，实际: {result2}"


def test_map_dimensions_chinese_comma():
    """中文逗号\"、\"作为分隔符，如\"按性别、月细分\"应该能正确匹配两个维度"""
    result = map_dimensions.invoke("按性别、月细分")
    assert "audience_gender" in result, f"应该包含性别，实际: {result}"
    assert "data_month" in result, f"应该包含月份，实际: {result}"
    assert len(result) == 2, f"应该有2个维度，实际: {result}"

    result2 = map_dimensions.invoke("按年龄、性别细分")
    assert "audience_age" in result2, f"应该包含年龄，实际: {result2}"
    assert "audience_gender" in result2, f"应该包含性别，实际: {result2}"
    assert len(result2) == 2, f"应该有2个维度，实际: {result2}"

    result3 = map_dimensions.invoke("电商家居_40_new 最近三个月的点击，按性别、月细分")
    assert "audience_gender" in result3, f"应该包含性别，实际: {result3}"
    assert "data_month" in result3, f"应该包含月份，实际: {result3}"
    assert len(result3) == 2, f"应该有2个维度，实际: {result3}"


def test_map_dimensions_hour_combinations():
    """小时维度的各种组合"""
    result = map_dimensions.invoke("按小时细分")
    assert result == ["data_hour"], f"期望只包含小时，实际: {result}"

    result2 = map_dimensions.invoke("按性别和小时细分")
    assert "audience_gender" in result2, f"应该包含性别，实际: {result2}"
    assert "data_hour" in result2, f"应该包含小时，实际: {result2}"
    assert len(result2) == 2, f"应该有2个维度，实际: {result2}"

    result3 = map_dimensions.invoke("按性别、小时细分")
    assert "audience_gender" in result3, f"应该包含性别，实际: {result3}"
    assert "data_hour" in result3, f"应该包含小时，实际: {result3}"
    assert len(result3) == 2, f"应该有2个维度，实际: {result3}"


def test_map_dimensions_day_combinations():
    """天维度的各种组合"""
    result = map_dimensions.invoke("按天细分")
    assert result == ["data_date"], f"期望只包含天，实际: {result}"

    result2 = map_dimensions.invoke("按性别和天细分")
    assert "audience_gender" in result2, f"应该包含性别，实际: {result2}"
    assert "data_date" in result2, f"应该包含天，实际: {result2}"
    assert len(result2) == 2, f"应该有2个维度，实际: {result2}"

    result3 = map_dimensions.invoke("按性别、天细分")
    assert "audience_gender" in result3, f"应该包含性别，实际: {result3}"
    assert "data_date" in result3, f"应该包含天，实际: {result3}"
    assert len(result3) == 2, f"应该有2个维度，实际: {result3}"


def test_map_dimensions_platform_combinations():
    """平台维度的各种组合"""
    result = map_dimensions.invoke("按平台细分")
    assert result == ["audience_os"], f"期望只包含平台，实际: {result}"

    result2 = map_dimensions.invoke("按性别和平台细分")
    assert "audience_gender" in result2, f"应该包含性别，实际: {result2}"
    assert "audience_os" in result2, f"应该包含平台，实际: {result2}"
    assert len(result2) == 2, f"应该有2个维度，实际: {result2}"

    result3 = map_dimensions.invoke("按平台和小时细分")
    assert "audience_os" in result3, f"应该包含平台，实际: {result3}"
    assert "data_hour" in result3, f"应该包含小时，实际: {result3}"
    assert len(result3) == 2, f"应该有2个维度，实际: {result3}"


def test_map_dimensions_interest_combinations():
    """兴趣维度的各种组合"""
    result = map_dimensions.invoke("按兴趣细分")
    assert result == ["audience_interest"], f"期望只包含兴趣，实际: {result}"

    result2 = map_dimensions.invoke("按性别和兴趣细分")
    assert "audience_gender" in result2, f"应该包含性别，实际: {result2}"
    assert "audience_interest" in result2, f"应该包含兴趣，实际: {result2}"
    assert len(result2) == 2, f"应该有2个维度，实际: {result2}"


def test_map_dimensions_three_dimensions():
    """三个维度的组合"""
    result = map_dimensions.invoke("按性别、年龄、平台细分")
    assert "audience_gender" in result, f"应该包含性别，实际: {result}"
    assert "audience_age" in result, f"应该包含年龄，实际: {result}"
    assert "audience_os" in result, f"应该包含平台，实际: {result}"
    assert len(result) == 3, f"应该有3个维度，实际: {result}"

    result2 = map_dimensions.invoke("按年龄、天、平台细分")
    assert "audience_age" in result2, f"应该包含年龄，实际: {result2}"
    assert "data_date" in result2, f"应该包含天，实际: {result2}"
    assert "audience_os" in result2, f"应该包含平台，实际: {result2}"
    assert len(result2) == 3, f"应该有3个维度，实际: {result2}"
