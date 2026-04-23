import pytest
from src.tools.formatters import (
    format_number,
    format_percent,
    format_currency,
    format_change,
    get_metric_display_name
)
from src.agents.reporter_agent import reporter_agent, get_trend


class TestFormatters:
    """测试格式化工具"""

    def test_format_number_integer(self):
        """测试整数格式化"""
        result = format_number.func(1000000)
        assert result == "1,000,000"

    def test_format_number_decimal(self):
        """测试小数格式化"""
        result = format_number.func(1234.5678, decimals=2)
        assert result == "1,234.57"

    def test_format_number_string_input(self):
        """测试字符串输入"""
        result = format_number.func("12345")
        assert result == "12,345"

    def test_format_number_invalid(self):
        """测试无效输入"""
        result = format_number.func(None)
        assert result == "None"
        result = format_number.func("not-a-number")
        assert result == "not-a-number"

    def test_format_percent(self):
        """测试百分比格式化"""
        result = format_percent.func(0.1234)
        assert result == "12.34%"
        result = format_percent.func(0.5, decimals=1)
        assert result == "50.0%"

    def test_format_percent_invalid(self):
        """测试百分比无效输入"""
        result = format_percent.func(None)
        assert result == "None"

    def test_format_currency_default(self):
        """测试默认货币格式化"""
        result = format_currency.func(1234.56)
        assert result == "¥1,234.56"

    def test_format_currency_custom_symbol(self):
        """测试自定义货币符号"""
        result = format_currency.func(1234.56, symbol="$")
        assert result == "$1,234.56"

    def test_format_currency_invalid(self):
        """测试货币格式化无效输入"""
        result = format_currency.func("abc")
        assert result == "abc"

    def test_format_change_positive(self):
        """测试正变化格式化"""
        result = format_change.func(0.125)
        assert result == "+12.50%"

    def test_format_change_negative(self):
        """测试负变化格式化"""
        result = format_change.func(-0.055)
        assert result == "-5.50%"

    def test_format_change_zero(self):
        """测试零变化"""
        result = format_change.func(0.0)
        assert result == "+0.00%"

    def test_format_change_invalid(self):
        """测试变化格式化无效输入"""
        result = format_change.func(None)
        assert result == "None"

    def test_get_metric_display_name_known(self):
        """测试已知指标名称映射"""
        assert get_metric_display_name.func("impressions") == "曝光量"
        assert get_metric_display_name.func("clicks") == "点击量"
        assert get_metric_display_name.func("cost") == "花费"
        assert get_metric_display_name.func("ctr") == "CTR"
        assert get_metric_display_name.func("cvr") == "CVR"
        assert get_metric_display_name.func("roi") == "ROI"

    def test_get_metric_display_name_unknown(self):
        """测试未知指标名称"""
        assert get_metric_display_name.func("unknown_metric") == "unknown_metric"


class TestGetTrend:
    """测试趋势判断"""

    def test_trend_up(self):
        """测试上升趋势"""
        assert get_trend(0.1) == "up"
        assert get_trend(0.06) == "up"

    def test_trend_down(self):
        """测试下降趋势"""
        assert get_trend(-0.1) == "down"
        assert get_trend(-0.06) == "down"

    def test_trend_flat(self):
        """测试平稳趋势"""
        assert get_trend(0.0) == "flat"
        assert get_trend(0.03) == "flat"
        assert get_trend(-0.03) == "flat"
        assert get_trend(None) == "flat"


class TestReporterAgent:
    """测试报告生成Agent"""

    @pytest.mark.asyncio
    async def test_empty_data(self):
        """测试空数据情况"""
        query_intent = {}
        query_request = {
            "metrics": ["impressions", "clicks"],
            "time_range": {"start_date": "2024-01-01", "end_date": "2024-01-07"}
        }
        query_result = {"data": []}
        analysis_result = {"anomalies": [], "insights": [], "recommendations": [], "rankings": {}}

        result = await reporter_agent(query_intent, query_request, query_result, analysis_result)

        assert result["title"] == "2024-01-01 ~ 2024-01-07 广告报表分析"
        assert len(result["metrics"]) == 2
        assert result["metrics"][0]["value"] == "0"
        assert result["highlights"] == []
        assert result["data_table"]["columns"] == []
        assert result["data_table"]["rows"] == []

    @pytest.mark.asyncio
    async def test_full_data_with_anomalies(self):
        """测试完整数据包含异常"""
        query_intent = {}
        query_request = {
            "metrics": ["impressions", "clicks", "cost", "ctr"],
            "time_range": {"start_date": "2024-01-01", "end_date": "2024-01-07"}
        }
        query_result = {
            "data": [
                {"dimension": "A渠道", "impressions": 10000, "clicks": 500, "cost": 1000.50, "ctr": 0.05},
                {"dimension": "B渠道", "impressions": 20000, "clicks": 800, "cost": 1600.00, "ctr": 0.04},
                {"dimension": "C渠道", "impressions": 5000, "clicks": 300, "cost": 600.25, "ctr": 0.06},
            ]
        }
        analysis_result = {
            "anomalies": [
                {
                    "metric": "impressions",
                    "dimension_value": "C渠道",
                    "change_percent": -0.3,
                },
                {
                    "metric": "ctr",
                    "dimension_value": "A渠道",
                    "change_percent": 0.25,
                }
            ],
            "insights": ["检测到 2 个异常点"],
            "recommendations": ["建议关注C渠道的异常下滑"],
            "rankings": {
                "top": [{"name": "B渠道", "value": 20000}]
            }
        }

        result = await reporter_agent(query_intent, query_request, query_result, analysis_result)

        # 验证汇总指标
        assert len(result["metrics"]) == 4
        # impressions: 10000 + 20000 + 5000 = 35000
        assert result["metrics"][0]["value"] == "35,000"
        # clicks: 500 + 800 + 300 = 1600
        assert result["metrics"][1]["value"] == "1,600"
        # cost: 1000.50 + 1600 + 600.25 = 3200.75
        assert result["metrics"][2]["value"] == "¥3,200.75"
        # ctr: 平均值
        assert "%" in result["metrics"][3]["value"]

        # 验证亮点/告警
        assert len(result["highlights"]) == 4  # 2 anomalies + 1 insight + 1 recommendation
        assert any("C渠道" in h["text"] and "🔴" in h["text"] for h in result["highlights"])
        assert any("A渠道" in h["text"] and "🟢" in h["text"] for h in result["highlights"])
        assert any("💡" in h["text"] for h in result["highlights"])
        assert any("ℹ️" in h["text"] for h in result["highlights"])

        # 验证表格数据
        assert len(result["data_table"]["columns"]) == 5
        assert len(result["data_table"]["rows"]) == 3

        # 验证推荐查询
        assert len(result["next_queries"]) == 2
        assert "查看 B渠道 的详细数据" in result["next_queries"]
        assert "按创意维度下钻分析异常点" in result["next_queries"]

    @pytest.mark.asyncio
    async def test_correct_formatting_by_metric_type(self):
        """测试不同指标类型的格式化是否正确"""
        query_intent = {}
        query_request = {
            "metrics": ["ctr", "cvr", "cost", "impressions", "roi"],
            "time_range": {"start_date": "2024-01-01", "end_date": "2024-01-01"}
        }
        query_result = {
            "data": [
                {"ctr": 0.10, "cvr": 0.02, "cost": 5000, "impressions": 100000, "roi": 3.2}
            ]
        }
        analysis_result = {"anomalies": [], "insights": [], "recommendations": [], "rankings": {}}

        result = await reporter_agent(query_intent, query_request, query_result, analysis_result)

        metrics = result["metrics"]
        # ctr 应该是百分比，平均值还是0.10 = 10%
        assert metrics[0]["value"] == "10.00%"
        # cvr 应该是百分比，平均值0.02 = 2%
        assert metrics[1]["value"] == "2.00%"
        # cost 应该是货币
        assert metrics[2]["value"] == "¥5,000.00"
        # impressions 应该是千分位整数
        assert metrics[3]["value"] == "100,000"
        # roi 应该是千分位数字
        assert metrics[4]["value"] == "3"
