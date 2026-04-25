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
