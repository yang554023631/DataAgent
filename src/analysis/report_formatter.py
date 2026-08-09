"""ReportFormatter - 报告包装器

将分析结果包装成统一的报告格式，返回给前端。
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.analysis.models import (
    AnalysisPlan,
    AnalysisType,
    ChartType,
    CotReasoning,
    AnalysisPlanResult,
)
from src.nl_dsl.models import (
    FilterResult,
    QualityResult,
    QualityIssue,
    QualityCheckType,
    QualityAction,
    AnalysisResult as NlDslAnalysisResult,
    EmptyCheckResult,
)

logger = logging.getLogger(__name__)


class ReportFormatter:
    """报告包装器"""

    @classmethod
    def format(
        cls,
        analysis_plan_result: AnalysisPlanResult,
        analysis_result: NlDslAnalysisResult,
        quality_result: QualityResult,
        filter_result: FilterResult,
        user_input: str,
        cot_reasoning: Optional[CotReasoning] = None,
    ) -> Dict[str, Any]:
        """格式化分析结果为最终报告

        Args:
            analysis_plan_result: 分析计划结果（包含分析计划和筛选计划）
            analysis_result: 分析执行结果
            quality_result: 质量检查结果
            filter_result: 筛选结果
            user_input: 用户原始输入
            cot_reasoning: CoT 推理过程（可选）

        Returns:
            最终报告字典
        """
        analysis_plan = analysis_plan_result.analysis_plan
        chart_data = analysis_result.chart_data or {}

        # 1. 判断报告类型
        report_type = cls._determine_report_type(quality_result, chart_data)

        if report_type == "error":
            return cls.format_error(
                error_type="data_empty",
                message="未找到有效的分析结果",
                reason="数据为空或质量检查失败",
                suggestions=["调整筛选条件", "扩大时间范围", "检查指标是否正确"],
                recommended_queries=["查看最近7天的整体数据", "查看全部广告主数据"]
            )

        # 2. 生成标题
        title = cls._generate_title_from_plan(analysis_plan)
        if report_type == "hitl":
            title = f"⚠️ 需要人工介入 - {title}"

        # 3. 提取图表配置和数据
        chart_config = chart_data.get("chart_config", {})
        data = chart_data.get("data", [])

        # 4. 格式化数据表格
        data_table = cls._format_analysis_data_table(analysis_result.data_table, analysis_plan.metrics)

        # 5. 生成亮点
        highlights = cls._generate_highlights(
            data=data,
            metrics=analysis_plan.metrics,
            quality_result=quality_result
        )

        # 6. 准备质量信息
        quality_info = cls._format_quality_info(quality_result)

        # 7. 准备元数据
        metadata = cls._generate_metadata(filter_result, analysis_plan)

        # 8. CoT 推理摘要
        cot_reasoning_summary = cls._summarize_cot_reasoning(cot_reasoning or analysis_plan_result.reasoning)

        # 9. 生成推荐查询
        next_queries = cls._generate_next_queries(analysis_plan, data)

        return {
            "report_type": report_type,
            "title": title,
            "chart_config": chart_config,
            "data": data,
            "data_table": data_table,
            "quality_info": quality_info,
            "highlights": highlights,
            "metadata": metadata,
            "cot_reasoning_summary": cot_reasoning_summary,
            "next_queries": next_queries
        }

    @classmethod
    def format_empty_result(
        cls,
        empty_check_result: EmptyCheckResult,
        analysis_plan_result: AnalysisPlanResult,
        filter_result: FilterResult,
        user_input: str,
    ) -> Dict[str, Any]:
        """格式化空结果报告

        Args:
            empty_check_result: 空检查结果
            analysis_plan_result: 分析计划结果
            filter_result: 筛选结果
            user_input: 用户原始输入

        Returns:
            最终报告字典
        """
        # 构建建议列表
        suggestions = empty_check_result.hints or [
            "调整筛选条件",
            "扩大时间范围",
            "检查指标是否正确"
        ]

        # 生成标题
        title = cls._generate_title_from_plan(analysis_plan_result.analysis_plan)

        return {
            "report_type": "empty",
            "title": f"📭 {title}",
            "highlights": [
                {
                    "type": "negative",
                    "text": f"⚠️ {empty_check_result.hints[0] if empty_check_result.hints else '未找到符合条件的数据'}"
                }
            ],
            "data_table": {"columns": [], "rows": []},
            "chart_config": None,
            "metadata": cls._generate_metadata(filter_result, analysis_plan_result.analysis_plan),
            "next_queries": ["查看最近7天的整体数据", "查看全部广告主数据"],
            "suggestions": suggestions
        }

    @classmethod
    def format_error(
        cls,
        error_type: str,
        message: str,
        reason: str,
        suggestions: List[str],
        recommended_queries: List[str]
    ) -> Dict[str, Any]:
        """格式化错误报告

        Args:
            error_type: 错误类型 query_failed / intent_unclear / data_empty / system_error
            message: 用户友好的错误消息
            reason: 具体原因
            suggestions: 解决建议列表
            recommended_queries: 推荐查询列表

        Returns:
            错误报告字典
        """
        return {
            "report_type": "error",
            "error_type": error_type,
            "message": message,
            "reason": reason,
            "suggestions": suggestions,
            "recommended_queries": recommended_queries
        }

    @classmethod
    def _determine_report_type(
        cls,
        quality_result: QualityResult,
        chart_data: Dict[str, Any]
    ) -> str:
        """判断报告类型"""
        # 检查是否需要人工介入
        for issue in quality_result.issues:
            if issue.severity == "hitl_required" or issue.suggested_action == QualityAction.HITL:
                return "hitl"

        # 检查是否有数据
        data = chart_data.get("data", [])
        if not data and quality_result.passed is False:
            return "error"

        return "success"

    @classmethod
    def _generate_title_from_plan(cls, analysis_plan: AnalysisPlan) -> str:
        """从分析计划生成标题"""
        analysis_type_names = {
            AnalysisType.ENTITY_TABLE: "实体表格分析",
            AnalysisType.TIME_TREND: "时间趋势分析",
            AnalysisType.PERIOD_COMPARISON: "时期对比分析",
            AnalysisType.AUDIENCE_DISTRIBUTION: "受众分布分析",
            AnalysisType.SUMMARY: "数据汇总分析",
        }

        type_name = analysis_type_names.get(analysis_plan.analysis_type, "数据分析")

        time_range = analysis_plan.time_range
        start_date = time_range.start_date
        end_date = time_range.end_date

        if start_date and end_date:
            return f"{type_name} ({start_date} ~ {end_date})"
        return type_name

    @classmethod
    def _format_data_table(cls, data: List[Dict[str, Any]], metrics: List[str]) -> Dict[str, Any]:
        """格式化数据表格（从字典列表）"""
        if not data:
            return {"columns": [], "rows": []}

        # 获取所有列名
        columns = list(data[0].keys())

        # 格式化行数据
        rows = []
        for row in data:
            formatted_row = []
            for col in columns:
                value = row.get(col)
                # 格式化百分比字段
                if col in metrics and (col.lower().find("ctr") != -1 or col.lower().find("cvr") != -1):
                    if isinstance(value, (int, float)):
                        formatted_row.append(f"{value * 100:.1f}%")
                    else:
                        formatted_row.append(value)
                # 格式化金额字段
                elif col in metrics and (col.lower().find("cost") != -1 or col.lower().find("spend") != -1):
                    if isinstance(value, (int, float)):
                        formatted_row.append(f"¥{value:,.2f}")
                    else:
                        formatted_row.append(value)
                # 格式化数字字段
                elif col in metrics and isinstance(value, (int, float)):
                    formatted_row.append(f"{value:,}")
                else:
                    formatted_row.append(value)
            rows.append(formatted_row)

        return {
            "columns": columns,
            "rows": rows
        }

    @classmethod
    def _format_analysis_data_table(cls, data_table, metrics: List[str]) -> Dict[str, Any]:
        """格式化数据表格（从 AnalysisDataTable 对象）"""
        if not data_table:
            return {"columns": [], "rows": []}

        # 如果是字典格式
        if isinstance(data_table, dict):
            columns = data_table.get("columns", [])
            rows = data_table.get("rows", [])
        # 如果是对象格式
        else:
            columns = []
            for col in getattr(data_table, "columns", []):
                if isinstance(col, dict):
                    columns.append(col.get("label", col.get("key", str(col))))
                else:
                    columns.append(str(col))
            rows = getattr(data_table, "rows", [])

        # 格式化行数据
        formatted_rows = []
        for row in rows:
            # 如果行是字典，提取值并格式化
            if isinstance(row, dict):
                formatted_row = []
                for col in (row.keys() if columns == [] else [c.get("key", c) if isinstance(c, dict) else c for c in columns]):
                    # 如果列是字典，获取key
                    col_key = col.get("key", col) if isinstance(col, dict) else col
                    value = row.get(col_key)
                    # 格式化百分比字段
                    if col_key in metrics and (str(col_key).lower().find("ctr") != -1 or str(col_key).lower().find("cvr") != -1):
                        if isinstance(value, (int, float)):
                            formatted_row.append(f"{value * 100:.1f}%")
                        else:
                            formatted_row.append(value)
                    # 格式化金额字段
                    elif col_key in metrics and (str(col_key).lower().find("cost") != -1 or str(col_key).lower().find("spend") != -1):
                        if isinstance(value, (int, float)):
                            formatted_row.append(f"¥{value:,.2f}")
                        else:
                            formatted_row.append(value)
                    # 格式化数字字段
                    elif col_key in metrics and isinstance(value, (int, float)):
                        formatted_row.append(f"{value:,}")
                    else:
                        formatted_row.append(value)
                formatted_rows.append(formatted_row)
            # 如果行是列表，直接格式化
            elif isinstance(row, list):
                formatted_row = []
                for i, value in enumerate(row):
                    col = columns[i] if i < len(columns) else ""
                    col_key = col.get("key", col) if isinstance(col, dict) else col
                    # 格式化百分比字段
                    if col_key in metrics and (str(col_key).lower().find("ctr") != -1 or str(col_key).lower().find("cvr") != -1):
                        if isinstance(value, (int, float)):
                            formatted_row.append(f"{value * 100:.1f}%")
                        else:
                            formatted_row.append(value)
                    # 格式化金额字段
                    elif col_key in metrics and (str(col_key).lower().find("cost") != -1 or str(col_key).lower().find("spend") != -1):
                        if isinstance(value, (int, float)):
                            formatted_row.append(f"¥{value:,.2f}")
                        else:
                            formatted_row.append(value)
                    # 格式化数字字段
                    elif col_key in metrics and isinstance(value, (int, float)):
                        formatted_row.append(f"{value:,}")
                    else:
                        formatted_row.append(value)
                formatted_rows.append(formatted_row)
            else:
                formatted_rows.append(row)

        # 处理列格式
        formatted_columns = []
        for col in columns:
            if isinstance(col, dict):
                formatted_columns.append(col.get("label", col.get("key", str(col))))
            else:
                formatted_columns.append(str(col))

        return {
            "columns": formatted_columns,
            "rows": formatted_rows
        }

    @classmethod
    def _generate_highlights(
        cls,
        data: List[Dict[str, Any]],
        metrics: List[str],
        quality_result: QualityResult
    ) -> List[Dict[str, str]]:
        """生成亮点（基于规则）"""
        highlights = []

        # 1. 从数据生成亮点
        data_highlights = cls._generate_highlights_from_data(data, metrics)
        highlights.extend(data_highlights)

        # 2. 从质量问题生成警告
        for issue in quality_result.issues:
            if issue.severity == "warning":
                highlights.append({
                    "type": "warning",
                    "text": f"⚠️ {issue.message}"
                })
            elif issue.severity == "hitl_required":
                highlights.append({
                    "type": "info",
                    "text": f"ℹ️ {issue.message}"
                })

        # 3. 添加质量警告
        for warning in quality_result.warnings:
            highlights.append({
                "type": "warning",
                "text": f"⚠️ {warning}"
            })

        # 4. 如果没有任何亮点，添加默认提示
        if not highlights:
            if data:
                highlights.append({
                    "type": "info",
                    "text": "✅ 数据加载完成，共 {} 条记录".format(len(data))
                })
            else:
                highlights.append({
                    "type": "info",
                    "text": "📭 当前条件下无数据，建议调整筛选条件"
                })

        return highlights

    @classmethod
    def _generate_highlights_from_data(
        cls,
        data: List[Dict[str, Any]],
        metrics: List[str]
    ) -> List[Dict[str, str]]:
        """基于数据生成亮点"""
        highlights = []

        if not data or not metrics:
            return highlights

        # 1. 总体统计
        total_records = len(data)
        if total_records > 0:
            highlights.append({
                "type": "info",
                "text": f"📊 共 {total_records} 条数据记录"
            })

        # 2. 指标汇总（处理前2个指标）
        for metric in metrics[:2]:  # 只处理前2个指标，避免亮点太多
            values = []
            for row in data:
                val = row.get(metric)
                if isinstance(val, (int, float)):
                    values.append(val)

            if values:
                total = sum(values)
                avg = total / len(values)
                max_val = max(values)
                min_val = min(values)

                # 格式化数值
                if metric.lower().find("ctr") != -1 or metric.lower().find("cvr") != -1:
                    total_str = f"{total * 100:.1f}%"
                    avg_str = f"{avg * 100:.1f}%"
                    max_str = f"{max_val * 100:.1f}%"
                    min_str = f"{min_val * 100:.1f}%"
                elif metric.lower().find("cost") != -1:
                    total_str = f"¥{total:,.2f}"
                    avg_str = f"¥{avg:,.2f}"
                    max_str = f"¥{max_val:,.2f}"
                    min_str = f"¥{min_val:,.2f}"
                else:
                    total_str = f"{total:,.0f}"
                    avg_str = f"{avg:,.0f}"
                    max_str = f"{max_val:,.0f}"
                    min_str = f"{min_val:,.0f}"

                metric_display_name = cls._get_metric_display_name(metric)

                if len(values) > 1:
                    highlights.append({
                        "type": "info",
                        "text": f"📈 {metric_display_name}：总计 {total_str}，平均 {avg_str}，最高 {max_str}，最低 {min_str}"
                    })
                else:
                    highlights.append({
                        "type": "info",
                        "text": f"📈 {metric_display_name}：{total_str}"
                    })

        # 3. 趋势判断（如果有日期字段且数据>=3条，使用第一个指标）
        primary_metric = metrics[0] if metrics else None
        if len(data) >= 3 and primary_metric:
            date_fields = ["date", "data_date", "day", "data_day"]
            has_date_field = any(f in data[0] for f in date_fields)

            if has_date_field:
                # 简单的趋势判断：比较前半部分和后半部分的平均值
                mid = len(data) // 2
                first_half = data[:mid]
                second_half = data[mid:]

                first_values = [row.get(primary_metric, 0) for row in first_half if isinstance(row.get(primary_metric), (int, float))]
                second_values = [row.get(primary_metric, 0) for row in second_half if isinstance(row.get(primary_metric), (int, float))]

                if first_values and second_values:
                    first_avg = sum(first_values) / len(first_values)
                    second_avg = sum(second_values) / len(second_values)

                    if second_avg > first_avg * 1.1:  # 上升超过10%
                        highlights.append({
                            "type": "positive",
                            "text": f"🟢 {cls._get_metric_display_name(primary_metric)} 呈现上升趋势"
                        })
                    elif second_avg < first_avg * 0.9:  # 下降超过10%
                        highlights.append({
                            "type": "negative",
                            "text": f"🔴 {cls._get_metric_display_name(primary_metric)} 呈现下降趋势"
                        })

        return highlights[:5]  # 最多返回5个亮点

    @classmethod
    def _get_metric_display_name(cls, metric: str) -> str:
        """获取指标显示名称"""
        display_names = {
            "cost": "消耗",
            "impressions": "曝光量",
            "clicks": "点击量",
            "ctr": "点击率",
            "cvr": "转化率",
            "spend": "花费",
            "conv": "转化数",
        }
        return display_names.get(metric, metric)

    @classmethod
    def _format_quality_info(cls, quality_result: QualityResult) -> Dict[str, Any]:
        """格式化质量信息"""
        return {
            "passed": quality_result.passed,
            "issues": [
                {
                    "check_type": issue.check_type.value if hasattr(issue.check_type, "value") else issue.check_type,
                    "severity": issue.severity,
                    "message": issue.message,
                    "suggested_action": issue.suggested_action.value if hasattr(issue.suggested_action, "value") else issue.suggested_action,
                    "threshold": issue.threshold,
                    "actual": issue.actual
                }
                for issue in quality_result.issues
            ],
            "warnings": quality_result.warnings,
            "actions": [action.value if hasattr(action, "value") else action for action in quality_result.actions]
        }

    @classmethod
    def _generate_metadata(cls, filter_result: FilterResult, analysis_plan: AnalysisPlan) -> Dict[str, Any]:
        """生成元数据"""
        return {
            "generated_at": datetime.now().isoformat(),
            "entity_level": filter_result.entity_level,
            "total_entities": filter_result.total_count,
            "metrics": analysis_plan.metrics,
            "analysis_type": analysis_plan.analysis_type.value if hasattr(analysis_plan.analysis_type, "value") else analysis_plan.analysis_type,
            "chart_type": analysis_plan.chart_type.value if hasattr(analysis_plan.chart_type, "value") else analysis_plan.chart_type,
            "time_range": {
                "start_date": analysis_plan.time_range.start_date,
                "end_date": analysis_plan.time_range.end_date,
                "granularity": analysis_plan.time_range.granularity
            }
        }

    @classmethod
    def _summarize_cot_reasoning(cls, cot_reasoning: Optional[CotReasoning]) -> Optional[str]:
        """摘要 CoT 推理过程"""
        if not cot_reasoning:
            return None

        if cot_reasoning.summary:
            return cot_reasoning.summary

        # 如果没有摘要，从步骤中生成
        if cot_reasoning.steps:
            return " → ".join([step.step_name for step in cot_reasoning.steps])

        return None

    @classmethod
    def _generate_next_queries(cls, analysis_plan: AnalysisPlan, data: List[Dict[str, Any]]) -> List[str]:
        """生成推荐查询"""
        next_queries = []

        if analysis_plan.analysis_type == AnalysisType.TIME_TREND:
            next_queries.append("按广告计划维度拆分趋势")
            next_queries.append("对比上周同期数据")
            next_queries.append("查看受众分布情况")
        elif analysis_plan.analysis_type == AnalysisType.ENTITY_TABLE:
            next_queries.append("查看时间趋势变化")
            next_queries.append("对比不同时期表现")
            next_queries.append("下钻到广告组维度")
        elif analysis_plan.analysis_type == AnalysisType.PERIOD_COMPARISON:
            next_queries.append("查看详细趋势图")
            next_queries.append("按维度拆分对比")
            next_queries.append("查看受众对比")
        elif analysis_plan.analysis_type == AnalysisType.AUDIENCE_DISTRIBUTION:
            next_queries.append("查看不同受众的转化情况")
            next_queries.append("对比历史受众分布")
            next_queries.append("按受众查看趋势")
        else:
            next_queries.append("查看时间趋势")
            next_queries.append("对比分析")
            next_queries.append("查看受众分布")

        return next_queries
