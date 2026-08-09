"""质量检查引擎测试"""
import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any, List
from src.nl_dsl.quality_checker import QualityChecker
from src.nl_dsl.models import (
    AnalysisResult,
    AnalysisChartConfig,
    AnalysisDataTable,
    QualityCheckType,
    QualityAction,
    QualityIssue,
    QualityResult,
)


@pytest.fixture
def quality_checker():
    """Quality checker instance"""
    return QualityChecker()


@pytest.fixture
def sample_chart_config_line():
    """Sample line chart config"""
    return AnalysisChartConfig(
        type="line",
        title="Cost Trend",
        x_axis={"field": "date", "label": "Date"},
        y_axis={"field": "cost", "label": "Cost"},
    )


@pytest.fixture
def sample_chart_config_pie():
    """Sample pie chart config"""
    return AnalysisChartConfig(
        type="pie",
        title="Audience Distribution",
    )


@pytest.fixture
def sample_data_table():
    """Sample data table"""
    return AnalysisDataTable(
        columns=[
            {"key": "campaign_id", "label": "Campaign ID"},
            {"key": "campaign_name", "label": "Campaign Name"},
            {"key": "cost", "label": "Cost"},
        ],
        rows=[
            {"campaign_id": 101, "campaign_name": "Campaign 1", "cost": 1000},
            {"campaign_id": 102, "campaign_name": "Campaign 2", "cost": 2000},
            {"campaign_id": 103, "campaign_name": "Campaign 3", "cost": 1500},
        ],
    )


class TestQualityChecker:
    """质量检查引擎测试"""

    def test_check_passed_result(
        self,
        quality_checker,
        sample_chart_config_line,
    ):
        """测试通过的结果"""
        analysis_result = AnalysisResult(
            success=True,
            chart_data={
                "chart_config": sample_chart_config_line.model_dump(),
                "data": [
                    {"date": "2026-04-01", "cost": 100},
                    {"date": "2026-04-02", "cost": 150},
                    {"date": "2026-04-03", "cost": 120},
                ],
            },
        )

        result = quality_checker.check(analysis_result)

        assert result.passed is True
        assert len(result.issues) == 0

    def test_check_empty_result(self, quality_checker):
        """测试空结果"""
        analysis_result = AnalysisResult(
            success=True,
            chart_data={"data": []},
            data_table=AnalysisDataTable(columns=[], rows=[]),
        )

        result = quality_checker.check(analysis_result)

        assert result.passed is True  # 警告不影响 passed 状态
        assert len(result.issues) == 1
        assert result.issues[0].check_type == QualityCheckType.EMPTY_RESULT
        assert result.issues[0].severity == "warning"
        assert "没有数据" in result.issues[0].message

    def test_check_failed_analysis(self, quality_checker):
        """测试失败的分析"""
        analysis_result = AnalysisResult(
            success=False,
            error="Some error occurred",
        )

        result = quality_checker.check(analysis_result)

        assert result.passed is False
        assert len(result.issues) == 1
        assert result.issues[0].check_type == QualityCheckType.EMPTY_RESULT
        assert result.issues[0].severity == "error"
        assert "分析失败" in result.issues[0].message

    def test_check_max_series_count(self, quality_checker):
        """测试趋势图系列过多"""
        # 构建 25 个系列的数据
        data_points = []
        for day in range(3):
            point = {"date": f"2026-04-0{day+1}"}
            for i in range(25):
                point[f"series_{i}"] = 100 + i * 10
            data_points.append(point)

        analysis_result = AnalysisResult(
            success=True,
            chart_data={
                "chart_config": {"type": "line", "title": "Multi-series Trend"},
                "data": data_points,
            },
        )

        result = quality_checker.check(analysis_result)

        assert result.passed is False
        assert any(
            issue.check_type == QualityCheckType.MAX_SERIES_COUNT
            for issue in result.issues
        )
        hitl_issue = next(
            i for i in result.issues if i.check_type == QualityCheckType.MAX_SERIES_COUNT
        )
        assert hitl_issue.severity == "hitl_required"
        assert hitl_issue.suggested_action == QualityAction.HITL
        assert hitl_issue.actual == 25
        assert hitl_issue.threshold == 20

    def test_check_max_rows(self, quality_checker, sample_data_table):
        """测试表格行数过多"""
        # 构建 150 行数据
        many_rows = []
        for i in range(150):
            many_rows.append({
                "campaign_id": 100 + i,
                "campaign_name": f"Campaign {i}",
                "cost": 1000 + i * 10,
            })
        sample_data_table.rows = many_rows

        analysis_result = AnalysisResult(
            success=True,
            data_table=sample_data_table,
        )

        result = quality_checker.check(analysis_result)

        assert result.passed is True  # 警告不影响 passed 状态
        assert any(
            issue.check_type == QualityCheckType.MAX_ROWS
            for issue in result.issues
        )
        rows_issue = next(
            i for i in result.issues if i.check_type == QualityCheckType.MAX_ROWS
        )
        assert rows_issue.severity == "warning"
        assert rows_issue.suggested_action == QualityAction.TRIM_TOP

    def test_check_max_categories(self, quality_checker, sample_chart_config_pie):
        """测试饼图分类过多"""
        # 构建 15 个分类
        data_points = []
        for i in range(15):
            data_points.append({
                "category": f"Category {i}",
                "value": 100 + i * 50,
            })

        analysis_result = AnalysisResult(
            success=True,
            chart_data={
                "chart_config": sample_chart_config_pie.model_dump(),
                "data": data_points,
            },
        )

        result = quality_checker.check(analysis_result)

        assert result.passed is True
        assert any(
            issue.check_type == QualityCheckType.MAX_CATEGORIES
            for issue in result.issues
        )
        cat_issue = next(
            i for i in result.issues if i.check_type == QualityCheckType.MAX_CATEGORIES
        )
        assert cat_issue.severity == "warning"
        assert cat_issue.suggested_action == QualityAction.TRIM_OTHERS

    def test_check_min_data_points(self, quality_checker, sample_chart_config_line):
        """测试数据点过少"""
        analysis_result = AnalysisResult(
            success=True,
            chart_data={
                "chart_config": sample_chart_config_line.model_dump(),
                "data": [
                    {"date": "2026-04-01", "cost": 100},
                ],
            },
        )

        result = quality_checker.check(analysis_result)

        assert result.passed is True
        assert any(
            issue.check_type == QualityCheckType.MIN_DATA_POINTS
            for issue in result.issues
        )

    def test_check_all_zero_chart_data(self, quality_checker, sample_chart_config_line):
        """测试全零数据（图表）"""
        analysis_result = AnalysisResult(
            success=True,
            chart_data={
                "chart_config": sample_chart_config_line.model_dump(),
                "data": [
                    {"date": "2026-04-01", "cost": 0},
                    {"date": "2026-04-02", "cost": 0},
                    {"date": "2026-04-03", "cost": 0},
                ],
            },
        )

        result = quality_checker.check(analysis_result)

        assert result.passed is True
        assert any(
            issue.check_type == QualityCheckType.ALL_ZERO
            for issue in result.issues
        )

    def test_check_all_zero_table_data(self, quality_checker, sample_data_table):
        """测试全零数据（表格）"""
        for row in sample_data_table.rows:
            row["cost"] = 0

        analysis_result = AnalysisResult(
            success=True,
            data_table=sample_data_table,
        )

        result = quality_checker.check(analysis_result)

        assert result.passed is True
        assert any(
            issue.check_type == QualityCheckType.ALL_ZERO
            for issue in result.issues
        )

    def test_apply_fixes_trim_top_rows(
        self,
        quality_checker,
        sample_data_table,
    ):
        """测试应用修复：截断表格前N行"""
        # 构建 150 行数据
        many_rows = []
        for i in range(150):
            many_rows.append({
                "campaign_id": 100 + i,
                "campaign_name": f"Campaign {i}",
                "cost": 1000 + i * 10,
            })
        sample_data_table.rows = many_rows

        analysis_result = AnalysisResult(
            success=True,
            data_table=sample_data_table,
        )

        # 先检查得到 issues
        quality_result = quality_checker.check(analysis_result)

        # 应用修复
        fixed_result = quality_checker.apply_fixes(analysis_result, quality_result)

        # 验证
        assert len(fixed_result.data_table.rows) == 100

    def test_apply_fixes_trim_others_categories(
        self,
        quality_checker,
        sample_chart_config_pie,
    ):
        """测试应用修复：保留前N个分类，其余合并为'其他'"""
        # 构建 15 个分类，包含排序
        data_points = []
        for i in range(15):
            data_points.append({
                "category": f"Category {i}",
                "value": 15 - i,  # 倒序，确保 Category 0 最大
            })

        analysis_result = AnalysisResult(
            success=True,
            chart_data={
                "chart_config": sample_chart_config_pie.model_dump(),
                "data": data_points,
            },
            data_table=AnalysisDataTable(
                columns=[
                    {"key": "category", "label": "Category"},
                    {"key": "value", "label": "Value"},
                    {"key": "percentage", "label": "Percentage"},
                ],
                rows=[{
                    "category": f"Category {i}",
                    "value": 15 - i,
                    "percentage": (15 - i) / 120 * 100,  # sum 120
                } for i in range(15)],
            ),
        )

        # 先检查得到 issues
        quality_result = quality_checker.check(analysis_result)

        # 应用修复
        fixed_result = quality_checker.apply_fixes(analysis_result, quality_result)

        # 验证图表数据
        assert len(fixed_result.chart_data["data"]) == 9  # 8 + 1 其他
        assert any(p["category"] == "其他" for p in fixed_result.chart_data["data"])

        # 验证表格数据
        assert len(fixed_result.data_table.rows) == 9
        assert any(r["category"] == "其他" for r in fixed_result.data_table.rows)

    def test_custom_thresholds(self):
        """测试自定义阈值"""
        from src.nl_dsl.models import QualityCheckType
        checker = QualityChecker(
            thresholds={
                QualityCheckType.MAX_SERIES_COUNT: 10,
                QualityCheckType.MAX_ROWS: 50,
            }
        )

        assert checker.thresholds[QualityCheckType.MAX_SERIES_COUNT] == 10
        assert checker.thresholds[QualityCheckType.MAX_ROWS] == 50
        # 未自定义的使用默认值
        assert checker.thresholds[QualityCheckType.MAX_CATEGORIES] == 8
