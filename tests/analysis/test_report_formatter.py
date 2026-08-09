"""ReportFormatter 测试"""
import pytest
from datetime import datetime
from src.analysis.report_formatter import ReportFormatter
from src.analysis.models import (
    AnalysisPlan,
    AnalysisType,
    ChartType,
    AnalysisTimeRange,
    AnalysisPlanResult,
    EntityLevel,
    FilterPlan,
    FilterType,
    CotReasoning,
    CotStep,
)
from src.nl_dsl.models import (
    FilterResult,
    QualityResult,
    QualityIssue,
    QualityCheckType,
    QualityAction,
    AnalysisResult,
    AnalysisChartConfig,
    AnalysisDataTable,
)


class TestReportFormatter:
    """ReportFormatter 测试类"""

    def test_format_success_report_time_trend(self):
        """测试格式化成功的时间趋势报告"""
        # 准备测试数据
        analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost", "impressions"],
            time_range=AnalysisTimeRange(
                start_date="2026-01-01",
                end_date="2026-01-07",
                granularity="day"
            ),
            time_granularity="day"
        )

        chart_data = {
            "chart_config": {
                "type": "line",
                "title": "消耗与曝光趋势",
                "x_axis": {"field": "date", "name": "日期"},
                "y_axis": {"field": "value", "name": "数值"},
                "series": [
                    {"name": "消耗", "field": "cost", "color": "#3b82f6"},
                    {"name": "曝光", "field": "impressions", "color": "#10b981"}
                ]
            },
            "data": [
                {"date": "2026-01-01", "cost": 1000, "impressions": 50000},
                {"date": "2026-01-02", "cost": 1200, "impressions": 60000},
                {"date": "2026-01-03", "cost": 1100, "impressions": 55000},
            ]
        }

        filter_result = FilterResult(
            entity_ids=[1, 2, 3],
            entity_level="advertiser",
            total_count=3
        )

        quality_result = QualityResult(
            passed=True,
            issues=[],
            warnings=[]
        )

        cot_reasoning = CotReasoning(
            steps=[
                CotStep(step_id="step_1", step_name="问题理解", content="用户想查看时间趋势"),
                CotStep(step_id="step_2", step_name="指标选择", content="选择消耗和曝光指标"),
            ],
            summary="分析时间趋势，选择消耗和曝光指标"
        )

        # 执行格式化
        report = ReportFormatter.format(
            analysis_plan=analysis_plan,
            chart_data=chart_data,
            filter_result=filter_result,
            quality_result=quality_result,
            cot_reasoning=cot_reasoning
        )

        # 验证结果
        assert report["report_type"] == "success"
        assert "时间趋势分析" in report["title"]
        assert "2026-01-01" in report["title"]
        assert report["chart_config"] is not None
        assert report["data"] is not None
        assert len(report["data"]) == 3
        assert report["data_table"] is not None
        assert report["quality_info"] is not None
        assert len(report["highlights"]) >= 2  # 至少有2个数据亮点
        assert report["cot_reasoning_summary"] is not None
        assert "metadata" in report

    def test_format_success_report_entity_table(self):
        """测试格式化成功的实体表格报告"""
        analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.ENTITY_TABLE,
            chart_type=ChartType.TABLE,
            metrics=["cost", "impressions", "ctr"],
            time_range=AnalysisTimeRange(
                start_date="2026-01-01",
                end_date="2026-01-07"
            ),
            group_by="campaign_id",
            order_by="cost",
            order_dir="desc",
            limit=10
        )

        chart_data = {
            "chart_config": {
                "type": "table",
                "title": "广告计划数据"
            },
            "data": [
                {"campaign_id": 1, "campaign_name": "计划A", "cost": 5000, "impressions": 100000, "ctr": 0.05},
                {"campaign_id": 2, "campaign_name": "计划B", "cost": 3000, "impressions": 80000, "ctr": 0.04},
                {"campaign_id": 3, "campaign_name": "计划C", "cost": 2000, "impressions": 50000, "ctr": 0.03},
            ]
        }

        filter_result = FilterResult(
            entity_ids=[1, 2, 3],
            entity_level="campaign",
            total_count=3
        )

        quality_result = QualityResult(passed=True)

        report = ReportFormatter.format(
            analysis_plan=analysis_plan,
            chart_data=chart_data,
            filter_result=filter_result,
            quality_result=quality_result
        )

        assert report["report_type"] == "success"
        assert "实体表格分析" in report["title"]
        assert len(report["highlights"]) >= 2

    def test_format_report_with_warnings(self):
        """测试带有警告的报告"""
        analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=AnalysisTimeRange(
                start_date="2026-01-01",
                end_date="2026-01-07"
            )
        )

        chart_data = {
            "chart_config": {"type": "line", "title": "消耗趋势"},
            "data": [{"date": "2026-01-01", "cost": 100}]
        }

        filter_result = FilterResult(
            entity_ids=[1],
            entity_level="advertiser",
            total_count=1
        )

        quality_result = QualityResult(
            passed=False,
            issues=[
                QualityIssue(
                    check_type=QualityCheckType.MIN_DATA_POINTS,
                    severity="warning",
                    message="数据点较少，可能影响分析准确性",
                    suggested_action=QualityAction.WARN,
                    threshold=7,
                    actual=1
                )
            ],
            warnings=["数据点较少"]
        )

        report = ReportFormatter.format(
            analysis_plan=analysis_plan,
            chart_data=chart_data,
            filter_result=filter_result,
            quality_result=quality_result
        )

        assert report["report_type"] == "success"
        assert len(report["quality_info"]["warnings"]) >= 1
        assert any("数据点较少" in h["text"] for h in report["highlights"])

    def test_format_hitl_report(self):
        """测试需要人工介入的报告"""
        analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=AnalysisTimeRange(
                start_date="2026-01-01",
                end_date="2026-01-07"
            )
        )

        chart_data = {
            "chart_config": {"type": "line", "title": "消耗趋势"},
            "data": []
        }

        filter_result = FilterResult(
            entity_ids=[],
            entity_level="advertiser",
            total_count=0
        )

        quality_result = QualityResult(
            passed=False,
            issues=[
                QualityIssue(
                    check_type=QualityCheckType.EMPTY_RESULT,
                    severity="hitl_required",
                    message="未找到数据，需要人工确认筛选条件",
                    suggested_action=QualityAction.HITL
                )
            ]
        )

        report = ReportFormatter.format(
            analysis_plan=analysis_plan,
            chart_data=chart_data,
            filter_result=filter_result,
            quality_result=quality_result
        )

        assert report["report_type"] == "hitl"
        assert "人工介入" in report["title"]

    def test_format_error_report(self):
        """测试错误报告"""
        analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=AnalysisTimeRange(
                start_date="2026-01-01",
                end_date="2026-01-07"
            )
        )

        report = ReportFormatter.format_error(
            error_type="query_failed",
            message="查询执行失败",
            reason="数据库连接超时",
            suggestions=["检查数据库连接", "稍后重试", "简化查询条件"],
            recommended_queries=["查看昨天的消耗数据", "查看本周的整体数据"]
        )

        assert report["report_type"] == "error"
        assert report["error_type"] == "query_failed"
        assert report["message"] == "查询执行失败"
        assert report["reason"] == "数据库连接超时"
        assert len(report["suggestions"]) == 3
        assert len(report["recommended_queries"]) == 2

    def test_generate_highlights_rule_based(self):
        """测试基于规则的亮点生成"""
        data = [
                {"date": "2026-01-01", "cost": 1000, "impressions": 50000, "ctr": 0.05},
                {"date": "2026-01-02", "cost": 1200, "impressions": 60000, "ctr": 0.04},
                {"date": "2026-01-03", "cost": 1500, "impressions": 75000, "ctr": 0.06},
                {"date": "2026-01-04", "cost": 1300, "impressions": 65000, "ctr": 0.05},
                {"date": "2026-01-05", "cost": 1100, "impressions": 55000, "ctr": 0.04},
            ]

        highlights = ReportFormatter._generate_highlights_from_data(data, ["cost", "impressions", "ctr"])

        assert len(highlights) >= 2
        # 应该包含消耗的描述
        assert any("消耗" in h["text"] for h in highlights)
        # 应该包含曝光的描述
        assert any("曝光" in h["text"] for h in highlights)

    def test_generate_title_from_plan(self):
        """测试从分析计划生成标题"""
        # 时间趋势
        plan1 = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=AnalysisTimeRange(
                start_date="2026-01-01",
                end_date="2026-01-07"
            )
        )
        title1 = ReportFormatter._generate_title_from_plan(plan1)
        assert "时间趋势" in title1
        assert "2026-01-01" in title1

        # 实体表格
        plan2 = AnalysisPlan(
            analysis_type=AnalysisType.ENTITY_TABLE,
            chart_type=ChartType.TABLE,
            metrics=["cost", "impressions"],
            time_range=AnalysisTimeRange(
                start_date="2026-01-01",
                end_date="2026-01-07"
            ),
            group_by="campaign_id"
        )
        title2 = ReportFormatter._generate_title_from_plan(plan2)
        assert "实体表格" in title2

        # 时期对比
        plan3 = AnalysisPlan(
            analysis_type=AnalysisType.PERIOD_COMPARISON,
            chart_type=ChartType.BAR,
            metrics=["cost"],
            time_range=AnalysisTimeRange(
                start_date="2026-01-08",
                end_date="2026-01-14"
            )
        )
        title3 = ReportFormatter._generate_title_from_plan(plan3)
        assert "对比" in title3

    def test_format_data_table(self):
        """测试格式化数据表格"""
        data = [
            {"campaign_id": 1, "name": "计划A", "cost": 1000.5, "ctr": 0.052},
            {"campaign_id": 2, "name": "计划B", "cost": 2000.75, "ctr": 0.048},
        ]

        data_table = ReportFormatter._format_data_table(data, ["cost", "ctr"])

        assert len(data_table["columns"]) == 4
        assert len(data_table["rows"]) == 2
        # 验证百分比格式化
        assert any("5.2%" in str(row) for row in data_table["rows"])

    def test_empty_data_handling(self):
        """测试空数据处理"""
        analysis_plan = AnalysisPlan(
            analysis_type=AnalysisType.TIME_TREND,
            chart_type=ChartType.LINE,
            metrics=["cost"],
            time_range=AnalysisTimeRange(
                start_date="2026-01-01",
                end_date="2026-01-07"
            )
        )

        chart_data = {
            "chart_config": {"type": "line", "title": "消耗趋势"},
            "data": []
        }

        filter_result = FilterResult(
            entity_ids=[],
            entity_level="advertiser",
            total_count=0
        )

        quality_result = QualityResult(passed=True)

        report = ReportFormatter.format(
            analysis_plan=analysis_plan,
            chart_data=chart_data,
            filter_result=filter_result,
            quality_result=quality_result
        )

        assert report["report_type"] == "success"
        assert report["data"] == []
        assert len(report["highlights"]) >= 1  # 至少有一个空数据提示
