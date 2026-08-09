"""质量检查引擎

检查分析结果的质量问题，如：
- 趋势图系列过多
- 表格行数过多
- 饼图分类过多
- 数据点过少
- 全零数据
- 空结果
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from .models import (
    QualityCheckType,
    QualityAction,
    QualityIssue,
    QualityResult,
    AnalysisResult,
    AnalysisChartConfig,
    AnalysisDataTable,
)

logger = logging.getLogger(__name__)

# 默认阈值配置
DEFAULT_THRESHOLDS = {
    QualityCheckType.MAX_SERIES_COUNT: 20,
    QualityCheckType.MAX_ROWS: 100,
    QualityCheckType.MAX_CATEGORIES: 8,
    QualityCheckType.MIN_DATA_POINTS: 2,
}


class QualityChecker:
    """质量检查引擎"""

    def __init__(self, thresholds: Optional[Dict[QualityCheckType, Any]] = None):
        """
        初始化质量检查引擎

        Args:
            thresholds: 自定义阈值配置
        """
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def check(
        self,
        analysis_result: AnalysisResult,
        chart_config: Optional[AnalysisChartConfig] = None,
        data_table: Optional[AnalysisDataTable] = None,
    ) -> QualityResult:
        """
        执行质量检查

        Args:
            analysis_result: 分析结果
            chart_config: 图表配置（可选，优先使用 analysis_result 中的）
            data_table: 数据表格（可选，优先使用 analysis_result 中的）

        Returns:
            QualityResult: 质量检查结果
        """
        issues: List[QualityIssue] = []
        warnings: List[str] = []
        actions: List[QualityAction] = []

        # 使用分析结果中的数据
        chart_data = analysis_result.chart_data
        table = data_table or analysis_result.data_table
        config = chart_config
        if chart_data and not config:
            config_dict = chart_data.get("chart_config")
            if config_dict:
                config = AnalysisChartConfig(**config_dict)

        # 检查 1: 空结果
        empty_issue = self._check_empty_result(analysis_result, chart_data, table)
        if empty_issue:
            issues.append(empty_issue)
            if empty_issue.suggested_action:
                actions.append(empty_issue.suggested_action)

        # 如果已经是空结果，其他检查可能不适用
        has_empty_issue = any(i.check_type == QualityCheckType.EMPTY_RESULT for i in issues)
        has_failed_issue = any(i.severity == "error" for i in issues)

        if chart_data and not has_empty_issue and not has_failed_issue:
            data_points = chart_data.get("data", [])
            has_chart_data = len(data_points) > 0

            # 检查 2: 趋势图系列过多
            if config and config.type in ("line", "bar") and has_chart_data:
                series_issue = self._check_max_series_count(chart_data)
                if series_issue:
                    issues.append(series_issue)
                    if series_issue.suggested_action:
                        actions.append(series_issue.suggested_action)

            # 检查 3: 饼图/受众分布分类过多
            if config and config.type in ("pie",) and has_chart_data:
                categories_issue = self._check_max_categories(chart_data)
                if categories_issue:
                    issues.append(categories_issue)
                    if categories_issue.suggested_action:
                        actions.append(categories_issue.suggested_action)

            # 检查 4: 数据点过少
            if has_chart_data:
                min_points_issue = self._check_min_data_points(chart_data, config)
                if min_points_issue:
                    issues.append(min_points_issue)
                    if min_points_issue.suggested_action:
                        actions.append(min_points_issue.suggested_action)

        # 检查 5: 全零数据
        if not has_empty_issue and not has_failed_issue:
            all_zero_issue = self._check_all_zero(chart_data, table)
            if all_zero_issue:
                issues.append(all_zero_issue)
                if all_zero_issue.suggested_action:
                    actions.append(all_zero_issue.suggested_action)

        # 检查 6: 表格行数过多
        if table:
            rows_issue = self._check_max_rows(table)
            if rows_issue:
                issues.append(rows_issue)
                if rows_issue.suggested_action:
                    actions.append(rows_issue.suggested_action)

        # 收集警告信息
        for issue in issues:
            if issue.severity == "warning":
                warnings.append(issue.message)

        # 去重 actions
        actions = list(dict.fromkeys(actions))

        passed = len(issues) == 0 or all(
            issue.severity == "warning" for issue in issues
        )

        return QualityResult(
            passed=passed,
            issues=issues,
            warnings=warnings,
            actions=actions,
        )

    def _check_empty_result(
        self,
        analysis_result: AnalysisResult,
        chart_data: Optional[Dict[str, Any]],
        data_table: Optional[AnalysisDataTable],
    ) -> Optional[QualityIssue]:
        """检查是否为空结果"""
        if not analysis_result.success:
            return QualityIssue(
                check_type=QualityCheckType.EMPTY_RESULT,
                severity="error",
                message=f"分析失败: {analysis_result.error}",
                suggested_action=QualityAction.FAIL,
            )

        is_empty = True

        if chart_data:
            data_points = chart_data.get("data", [])
            if data_points and len(data_points) > 0:
                is_empty = False

        if data_table and data_table.rows and len(data_table.rows) > 0:
            is_empty = False

        if is_empty:
            return QualityIssue(
                check_type=QualityCheckType.EMPTY_RESULT,
                severity="warning",
                message="分析结果为空，没有数据可以展示",
                suggested_action=QualityAction.WARN,
            )

        return None

    def _check_max_series_count(
        self,
        chart_data: Dict[str, Any],
    ) -> Optional[QualityIssue]:
        """检查趋势图系列数量是否过多"""
        threshold = self.thresholds[QualityCheckType.MAX_SERIES_COUNT]
        data_points = chart_data.get("data", [])

        if not data_points:
            return None

        # 计算系列数量：第一行数据的键数量（排除 x 轴字段）
        first_point = data_points[0]
        # 找出可能的 x 轴字段
        x_fields = {"date", "category", "metric"}
        series_fields = [k for k in first_point.keys() if k not in x_fields]
        series_count = len(series_fields)

        if series_count > threshold:
            return QualityIssue(
                check_type=QualityCheckType.MAX_SERIES_COUNT,
                severity="hitl_required",
                message=f"趋势图系列数量过多: {series_count} 个（阈值: {threshold}）",
                suggested_action=QualityAction.HITL,
                threshold=threshold,
                actual=series_count,
            )

        return None

    def _check_max_rows(
        self,
        data_table: AnalysisDataTable,
    ) -> Optional[QualityIssue]:
        """检查表格行数是否过多"""
        threshold = self.thresholds[QualityCheckType.MAX_ROWS]
        row_count = len(data_table.rows) if data_table.rows else 0

        if row_count > threshold:
            return QualityIssue(
                check_type=QualityCheckType.MAX_ROWS,
                severity="warning",
                message=f"表格行数过多: {row_count} 行（阈值: {threshold}）",
                suggested_action=QualityAction.TRIM_TOP,
                threshold=threshold,
                actual=row_count,
            )

        return None

    def _check_max_categories(
        self,
        chart_data: Dict[str, Any],
    ) -> Optional[QualityIssue]:
        """检查饼图/受众分布分类数量是否过多"""
        threshold = self.thresholds[QualityCheckType.MAX_CATEGORIES]
        data_points = chart_data.get("data", [])
        category_count = len(data_points)

        if category_count > threshold:
            return QualityIssue(
                check_type=QualityCheckType.MAX_CATEGORIES,
                severity="warning",
                message=f"图表分类数量过多: {category_count} 个（阈值: {threshold}）",
                suggested_action=QualityAction.TRIM_OTHERS,
                threshold=threshold,
                actual=category_count,
            )

        return None

    def _check_min_data_points(
        self,
        chart_data: Dict[str, Any],
        chart_config: Optional[AnalysisChartConfig],
    ) -> Optional[QualityIssue]:
        """检查数据点数量是否过少"""
        threshold = self.thresholds[QualityCheckType.MIN_DATA_POINTS]
        data_points = chart_data.get("data", [])
        point_count = len(data_points)

        if point_count < threshold:
            chart_type = chart_config.type if chart_config else "chart"
            return QualityIssue(
                check_type=QualityCheckType.MIN_DATA_POINTS,
                severity="warning",
                message=f"{chart_type}数据点过少: {point_count} 个（建议最少: {threshold}）",
                suggested_action=QualityAction.WARN,
                threshold=threshold,
                actual=point_count,
            )

        return None

    def _check_all_zero(
        self,
        chart_data: Optional[Dict[str, Any]],
        data_table: Optional[AnalysisDataTable],
    ) -> Optional[QualityIssue]:
        """检查是否所有数据都是零"""
        all_zero = True
        has_data = False

        # 检查图表数据
        if chart_data:
            data_points = chart_data.get("data", [])
            for point in data_points:
                for key, value in point.items():
                    if key in ("date", "category", "metric", "period"):
                        continue
                    has_data = True
                    if isinstance(value, (int, float)) and value != 0:
                        all_zero = False
                        break
                if not all_zero:
                    break

        # 如果图表数据是全零或无图表数据，检查表数据
        if (all_zero or not has_data) and data_table and data_table.rows:
            for row in data_table.rows:
                for key, value in row.items():
                    if "_id" in key or "_name" in key or key in ("date", "category", "metric", "period", "change_pct", "percentage"):
                        continue
                    has_data = True
                    if isinstance(value, (int, float)) and value != 0:
                        all_zero = False
                        break
                if not all_zero:
                    break

        if has_data and all_zero:
            return QualityIssue(
                check_type=QualityCheckType.ALL_ZERO,
                severity="warning",
                message="所有指标数据均为零",
                suggested_action=QualityAction.WARN,
            )

        return None

    def apply_fixes(
        self,
        analysis_result: AnalysisResult,
        quality_result: QualityResult,
    ) -> AnalysisResult:
        """
        应用修复措施

        Args:
            analysis_result: 原始分析结果
            quality_result: 质量检查结果

        Returns:
            AnalysisResult: 修复后的分析结果
        """
        if not quality_result.issues:
            return analysis_result

        # 创建副本以避免修改原始数据
        from copy import deepcopy
        result = deepcopy(analysis_result)

        for issue in quality_result.issues:
            if issue.suggested_action == QualityAction.TRIM_TOP:
                if issue.check_type == QualityCheckType.MAX_ROWS:
                    result = self._apply_trim_top_rows(result, issue.threshold)
            elif issue.suggested_action == QualityAction.TRIM_OTHERS:
                if issue.check_type == QualityCheckType.MAX_CATEGORIES:
                    result = self._apply_trim_others_categories(result, issue.threshold)

        return result

    def _apply_trim_top_rows(
        self,
        analysis_result: AnalysisResult,
        threshold: Optional[Any],
    ) -> AnalysisResult:
        """应用截断表格前 N 行"""
        limit = threshold or DEFAULT_THRESHOLDS[QualityCheckType.MAX_ROWS]
        if analysis_result.data_table and analysis_result.data_table.rows:
            analysis_result.data_table.rows = analysis_result.data_table.rows[:limit]
        return analysis_result

    def _apply_trim_others_categories(
        self,
        analysis_result: AnalysisResult,
        threshold: Optional[Any],
    ) -> AnalysisResult:
        """应用保留前 N 个分类，其余合并为'其他'"""
        limit = threshold or DEFAULT_THRESHOLDS[QualityCheckType.MAX_CATEGORIES]

        # 修复图表数据
        if analysis_result.chart_data:
            data_points = analysis_result.chart_data.get("data", [])
            if len(data_points) > limit:
                # 排序（假设数据点有 value 字段）
                sorted_points = sorted(
                    data_points,
                    key=lambda x: x.get("value", 0),
                    reverse=True,
                )
                top_points = sorted_points[:limit]
                other_points = sorted_points[limit:]

                # 计算"其他"的总和
                other_value = sum(p.get("value", 0) for p in other_points)

                if other_value > 0:
                    top_points.append({
                        "category": "其他",
                        "value": other_value,
                    })

                analysis_result.chart_data["data"] = top_points

        # 修复表格数据
        if analysis_result.data_table and analysis_result.data_table.rows:
            rows = analysis_result.data_table.rows
            if len(rows) > limit:
                # 找到 value 列
                value_col = None
                for col in analysis_result.data_table.columns:
                    if col.get("key") == "value":
                        value_col = "value"
                        break
                    if col.get("key") not in ("category", "percentage"):
                        # 假设第一个非分类列是数值列
                        value_col = value_col or col.get("key")

                # 排序
                if value_col:
                    sorted_rows = sorted(
                        rows,
                        key=lambda x: x.get(value_col, 0),
                        reverse=True,
                    )
                    top_rows = sorted_rows[:limit]
                    other_rows = sorted_rows[limit:]

                    # 合并"其他"
                    if other_rows:
                        other_row = {"category": "其他"}
                        if value_col:
                            other_row[value_col] = sum(r.get(value_col, 0) for r in other_rows)
                        # 重新计算百分比
                        total = sum(r.get(value_col, 0) for r in rows) if value_col else 0
                        if total > 0 and "percentage" in top_rows[0]:
                            for row in top_rows:
                                row["percentage"] = (row.get(value_col, 0) / total) * 100 if value_col else None
                            other_row["percentage"] = (other_row.get(value_col, 0) / total) * 100 if value_col else None
                        top_rows.append(other_row)

                        analysis_result.data_table.rows = top_rows

        return analysis_result
