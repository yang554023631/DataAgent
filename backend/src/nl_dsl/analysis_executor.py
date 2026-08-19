"""分析计划执行器"""
from typing import List, Dict, Any, Optional
import logging
from .models import (
    AnalysisPlan,
    AnalysisResult,
    AnalysisDataTable,
    AnalysisChartConfig,
)
from .dsl_templates import (
    build_single_series_trend,
    build_multi_series_trend,
    build_entity_table,
    build_period_comparison_summary,
    build_audience_distribution,
    build_summary,
    extract_trend_data,
    extract_entity_table_data,
    extract_comparison_data,
    extract_audience_data,
    extract_summary_data,
    get_level_field,
    LEVEL_TO_FIELD,
)
from src.tools.custom_report_client import AUDIENCE_VALUE_MAPS

logger = logging.getLogger(__name__)


class AnalysisExecutor:
    """分析计划执行器"""

    def __init__(self, es_client, entity_name_resolver=None):
        """
        初始化分析执行器

        Args:
            es_client: Elasticsearch 客户端实例
            entity_name_resolver: 实体名称解析器（可选，用于将实体 ID 转换为名称）
        """
        self.es_client = es_client
        self.entity_name_resolver = entity_name_resolver or {}

    def execute(
        self,
        analysis_plan: AnalysisPlan,
        entity_ids: Optional[List[Any]] = None,
        entity_level: Optional[str] = None,
        advertiser_ids: Optional[List[str]] = None,
        time_range: Optional[Dict[str, str]] = None,
    ) -> AnalysisResult:
        """
        执行分析计划

        Args:
            analysis_plan: 分析计划
            entity_ids: 筛选后的实体 ID 列表（可选，来自 FilterExecutor）
            entity_level: 实体层级（可选）
            advertiser_ids: 广告主 ID 列表
            time_range: 时间范围（可选，如果提供会覆盖 analysis_plan.time_range）

        Returns:
            AnalysisResult: 分析结果
        """
        trace = []
        advertiser_ids = advertiser_ids or []

        # 确定时间范围
        if time_range:
            start_date = time_range.get("start_date", analysis_plan.time_range.start_date)
            end_date = time_range.get("end_date", analysis_plan.time_range.end_date)
        else:
            start_date = analysis_plan.time_range.start_date
            end_date = analysis_plan.time_range.end_date

        granularity = analysis_plan.time_range.granularity

        try:
            # 如果是多步计划（有前置过滤步骤，比如 where 过滤得到实体 ID 再分析）
            # 需要交给 MultiStepPipeline 链式执行
            # 顶层 execute 只执行最终分析步骤，这里不需要处理多步
            if analysis_plan.steps and len(analysis_plan.steps) > 0:
                # 多步计划应该由 MultiStepPipeline 处理
                # 但如果走到这里，说明这是最终分析步骤，steps 是空的？
                # 实际上，对于多步计划，每个步骤单独执行，最终步骤也应该有自己的配置
                # 如果 audience_dimension 为空但 steps 存在，说明需要多步处理
                # 这里不应该走到单步执行器，应该报错说明需要多步执行
                # 但是在当前架构中，最终分析步骤仍需要正确配置
                # 对于 audience_distribution，最终步骤应该包含 audience_dimension
                pass

            # 根据分析类型执行相应的分析
            if analysis_plan.analysis_type == "time_trend":
                result = self._execute_time_trend(
                    analysis_plan=analysis_plan,
                    entity_ids=entity_ids,
                    entity_level=entity_level,
                    advertiser_ids=advertiser_ids,
                    start_date=start_date,
                    end_date=end_date,
                    granularity=granularity,
                    trace=trace,
                )
            elif analysis_plan.analysis_type == "entity_table":
                result = self._execute_entity_table(
                    analysis_plan=analysis_plan,
                    entity_ids=entity_ids,
                    entity_level=entity_level,
                    advertiser_ids=advertiser_ids,
                    start_date=start_date,
                    end_date=end_date,
                    trace=trace,
                )
            elif analysis_plan.analysis_type == "period_comparison":
                result = self._execute_period_comparison(
                    analysis_plan=analysis_plan,
                    entity_ids=entity_ids,
                    entity_level=entity_level,
                    advertiser_ids=advertiser_ids,
                    start_date=start_date,
                    end_date=end_date,
                    trace=trace,
                )
            elif analysis_plan.analysis_type == "audience_distribution":
                result = self._execute_audience_distribution(
                    analysis_plan=analysis_plan,
                    entity_ids=entity_ids,
                    entity_level=entity_level,
                    advertiser_ids=advertiser_ids,
                    start_date=start_date,
                    end_date=end_date,
                    trace=trace,
                )
            elif analysis_plan.analysis_type == "summary":
                result = self._execute_summary(
                    analysis_plan=analysis_plan,
                    entity_ids=entity_ids,
                    entity_level=entity_level,
                    advertiser_ids=advertiser_ids,
                    start_date=start_date,
                    end_date=end_date,
                    trace=trace,
                )
            else:
                raise ValueError(f"Unknown analysis type: {analysis_plan.analysis_type}")

            return result

        except Exception as e:
            logger.error(f"Analysis execution failed: {str(e)}", exc_info=True)
            return AnalysisResult(
                success=False,
                error=str(e),
                trace=trace + [{"step": "execution", "status": "failed", "error": str(e)}],
            )

    def _execute_time_trend(
        self,
        analysis_plan: AnalysisPlan,
        entity_ids: Optional[List[Any]],
        entity_level: Optional[str],
        advertiser_ids: List[str],
        start_date: str,
        end_date: str,
        granularity: str,
        trace: List[Dict[str, Any]],
    ) -> AnalysisResult:
        """执行时间趋势分析"""
        trace.append({"step": "time_trend", "status": "started"})

        # 只支持单个指标
        if not analysis_plan.metrics:
            raise ValueError("Time trend analysis requires at least one metric")
        metric = analysis_plan.metrics[0]

        # 判断是单系列还是多系列
        # For multi-series trend, use group_by field (already defined in model)
        # Skip date-related grouping - single series trend is already grouped by date
        series_level = analysis_plan.group_by
        date_related = ['data_date', 'date', 'day', 'month', 'time', 'advertiser_id', 'advertiser']

        # 如果 group_by 是列表（多个分组字段），过滤掉日期相关的，只保留非日期的作为 series_level
        if isinstance(series_level, list):
            # 找第一个非日期相关且非顶级实体ID的字段作为 series_level
            found = None
            for gb in series_level:
                if gb.lower() not in date_related:
                    found = gb
                    break
            series_level = found

        # 智能推断：如果 having 过滤后得到多个实体ID，且 group_by 为空
        # 说明用户希望看到每个实体单独的趋势，自动推断 series_level = entity_level
        if entity_ids and len(entity_ids) > 1 and not series_level and entity_level:
            # entity_level 是 "campaign"，对应的字段就是 get_level_field(entity_level) = "campaign_id"
            series_level = get_level_field(entity_level)

        if series_level and str(series_level).lower() not in date_related:
            # 多系列趋势
            dsl = build_multi_series_trend(
                advertiser_ids=advertiser_ids,
                start_date=start_date,
                end_date=end_date,
                metric=metric,
                series_level=series_level,
                # 注意：series_ids 只是当 series_level == entity_level 时用于筛选系列
                # 我们需要在下面单独添加实体过滤器，不管 series_level 是什么
                series_ids=None,
                granularity=granularity,
            )
        else:
            # 单系列趋势
            dsl = build_single_series_trend(
                advertiser_ids=advertiser_ids,
                start_date=start_date,
                end_date=end_date,
                metric=metric,
                granularity=granularity,
            )

        # 如果有实体 ID，需要添加过滤条件（无论是单系列还是多系列）
        # 注意：派生指标以小数形式存储（0.05 = 5%），只在显示层格式化
        if entity_ids and entity_level:
            level_field = get_level_field(entity_level)
            dsl["query"]["bool"]["filter"].append({"terms": {level_field: entity_ids}})

        # 执行查询（带重试）
        response = self._execute_with_retry(dsl, "time_trend")

        # 提取数据
        trend_data = extract_trend_data(response, series_level=series_level)

        # 构建图表数据
        # 如果 analysis_plan 已经指定了 chart_type，默认配置使用它，不要硬编码覆盖
        default_chart_type = analysis_plan.chart_type.value if hasattr(analysis_plan.chart_type, "value") else analysis_plan.chart_type
        chart_config = analysis_plan.chart_config or AnalysisChartConfig(
            type=default_chart_type,
            title=f"{metric} 趋势",
            x_axis={"field": "date", "label": "日期"},
            y_axis={"field": metric, "label": metric},
        )

        # 转换数据格式
        # 构建数据表格（表格始终使用长格式，已经补零）
        data_table = self._build_data_table_for_trend(
            trend_data, metric, series_level
        )

        if series_level and str(series_level).lower() not in ['data_date', 'date', 'day', 'month', 'time']:
            # 多系列趋势: 转换为前端期望的长格式，每个 date × series 占一行
            # 这样前端现有代码可以直接处理多系列
            # 收集所有日期和所有系列
            all_series = set()
            all_dates = set()
            for date_key, series_values in trend_data.items():
                all_dates.add(date_key)
                if isinstance(series_values, dict):
                    all_series.update(series_values.keys())

            # 判断指标类型，确定补零值
            # 计数类指标（曝光/点击/转化/触达）补整数0，其他（消耗/比例/频次）补浮点数0.0
            integer_metrics = {'impressions', 'clicks', 'conversions', 'reach'}
            fill_value = 0 if metric in integer_metrics else 0.0

            # 获取 series_field 名称（比如 "campaign_id"）
            series_field = get_level_field(series_level) if series_level else None

            # 对每个日期 × 每个系列生成一行（长格式）
            chart_data_points = []
            sorted_dates = sorted(all_dates)
            for date_key in sorted_dates:
                series_values = trend_data.get(date_key, {})
                if not isinstance(series_values, dict):
                    series_values = {}
                for series_id in sorted(all_series):
                    value = series_values.get(series_id, fill_value)
                    point = {
                        "date": date_key,
                        series_field: str(series_id),
                        metric: value,
                    }
                    chart_data_points.append(point)

            # 自动填充 chart_config.series 给前端
            # 每个系列需要一个 {name: series_name} 条目
            if chart_config.series is None or len(chart_config.series) == 0:
                series_list = []
                for series_id in sorted(all_series):
                    series_name = self.entity_name_resolver.get(series_id, str(series_id))
                    series_list.append({"name": series_name})
                chart_config.series = series_list

            # 设置 series_field
            chart_config.series_field = series_field
        else:
            # 单系列: {date: value}
            chart_data_points = []
            for date_key, value in sorted(trend_data.items()):
                chart_data_points.append({"date": date_key, metric: value})

        trace.append({"step": "time_trend", "status": "success"})

        return AnalysisResult(
            chart_data={
                "chart_config": chart_config.model_dump(),
                "data": chart_data_points,
            },
            data_table=data_table,
            trace=trace,
        )

    def _execute_entity_table(
        self,
        analysis_plan: AnalysisPlan,
        entity_ids: Optional[List[Any]],
        entity_level: Optional[str],
        advertiser_ids: List[str],
        start_date: str,
        end_date: str,
        trace: List[Dict[str, Any]],
    ) -> AnalysisResult:
        """执行实体表格分析"""
        trace.append({"step": "entity_table", "status": "started"})

        group_by_level = analysis_plan.group_by or entity_level
        # If group_by is a list (multiple groupings), take the first non-date one for entity table grouping
        if isinstance(group_by_level, list):
            date_related = ['data_date', 'date', 'day', 'month', 'time']
            found = None
            for gb in group_by_level:
                if gb.lower() not in date_related:
                    found = gb
                    break
            if found:
                group_by_level = found
            else:
                group_by_level = group_by_level[0] if group_by_level else entity_level
        if not group_by_level:
            raise ValueError("Entity table analysis requires group_by (group by level)")

        dsl = build_entity_table(
            advertiser_ids=advertiser_ids,
            start_date=start_date,
            end_date=end_date,
            metrics=analysis_plan.metrics,
            group_by_level=group_by_level,
            order_by=analysis_plan.order_by,
            order_dir=analysis_plan.order_dir,
            limit=analysis_plan.limit,
        )

        # 如果有实体 ID，添加过滤条件
        if entity_ids and entity_level:
            level_field = get_level_field(entity_level)
            dsl["query"]["bool"]["filter"].append({"terms": {level_field: entity_ids}})

        # 执行查询（带重试）
        response = self._execute_with_retry(dsl, "entity_table")

        # 提取数据
        table_data = extract_entity_table_data(response, group_by_level)

        # 构建图表配置（默认为表格类型，如果 LLM 指定了 chart_type 就用 LLM 的）
        default_chart_type = analysis_plan.chart_type.value if hasattr(analysis_plan.chart_type, "value") else analysis_plan.chart_type
        chart_config = analysis_plan.chart_config or AnalysisChartConfig(
            type=default_chart_type,
            title=f"{group_by_level} 指标汇总",
        )

        # 构建数据表格
        data_table = self._build_data_table_for_entity(
            table_data, analysis_plan.metrics, group_by_level
        )

        # 构建图表数据（如果需要图表展示）
        chart_data = None
        if chart_config.type != "table":
            chart_data = self._build_chart_data_for_entity(
                table_data, analysis_plan.metrics, group_by_level, chart_config
            )

        trace.append({"step": "entity_table", "status": "success"})

        return AnalysisResult(
            chart_data=chart_data,
            chart_config=chart_config,
            data_table=data_table,
            trace=trace,
        )

    def _execute_period_comparison(
        self,
        analysis_plan: AnalysisPlan,
        entity_ids: Optional[List[Any]],
        entity_level: Optional[str],
        advertiser_ids: List[str],
        start_date: str,
        end_date: str,
        trace: List[Dict[str, Any]],
    ) -> AnalysisResult:
        """执行时期对比分析"""
        trace.append({"step": "period_comparison", "status": "started"})

        if not analysis_plan.compare_time_range:
            raise ValueError("Period comparison analysis requires comparison config")

        dsl = build_period_comparison_summary(
            advertiser_ids=advertiser_ids,
            current_start=start_date,
            current_end=end_date,
            compare_start=analysis_plan.compare_time_range.compare_start_date,
            compare_end=analysis_plan.compare_time_range.compare_end_date,
            metrics=analysis_plan.metrics,
        )

        # 如果有实体 ID，添加过滤条件
        if entity_ids and entity_level:
            level_field = get_level_field(entity_level)
            dsl["query"]["bool"]["filter"].append({"terms": {level_field: entity_ids}})

        # 执行查询（带重试）
        response = self._execute_with_retry(dsl, "period_comparison")

        # 提取数据
        comparison_data = extract_comparison_data(response, analysis_plan.metrics)

        # 构建图表配置
        # 如果 analysis_plan 已经指定了 chart_type，默认配置使用它，不要硬编码覆盖
        # 只有当 chart_config 为 None 时才创建默认配置
        default_chart_type = analysis_plan.chart_type.value if hasattr(analysis_plan.chart_type, "value") else analysis_plan.chart_type
        chart_config = analysis_plan.chart_config or AnalysisChartConfig(
            type=default_chart_type,
            title="时期对比",
            x_axis={"field": "metric", "label": "指标"},
            y_axis={"field": "value", "label": "数值"},
            series_field="period",
        )

        # 构建图表数据
        chart_data_points = []
        # Generate friendly period names from date ranges
        def get_friendly_period_name(period_key: str) -> str:
            """Generate friendly display name for a period from its date range"""
            # Get the start and end dates for this period
            if period_key == "current_period":
                start_date = analysis_plan.time_range.start_date
                end_date = analysis_plan.time_range.end_date
            elif period_key == "compare_period":
                if not analysis_plan.compare_time_range:
                    return "对比期"
                start_date = analysis_plan.compare_time_range.compare_start_date
                end_date = analysis_plan.compare_time_range.compare_end_date
            else:
                return period_key

            # Parse YYYY-MM-DD
            if len(start_date) != 10 or len(end_date) != 10:
                return period_key.replace("_", " ")

            start_year = int(start_date[0:4])
            start_month = int(start_date[5:7])
            start_day = int(start_date[8:10])
            end_year = int(end_date[0:4])
            end_month = int(end_date[5:7])
            end_day = int(end_date[8:10])

            # Case 1: Full month (start day 1, end day is last day of month) → just "M月" or "YYYY年M月"
            if start_day == 1 and end_day >= 28:
                if start_year == end_year:
                    return f"{start_month}月"
                else:
                    return f"{start_year}年{start_month}月"

            # Case 2: Same year, different months → "M月d日 ~ N月d日"
            if start_year == end_year:
                if start_month == end_month:
                    # Same month, multiple days → "M月d日 ~d日"
                    return f"{start_month}月{start_day}日~{end_day}日"
                else:
                    return f"{start_month}月{start_day}日~{end_month}月{end_day}日"

            # Case 3: Different years → "YYYY年M月d日 ~ YYYY年M月d日"
            return f"{start_year}年{start_month}月{start_day}日~{end_year}年{end_month}月{end_day}日"

        for metric in analysis_plan.metrics:
            for period in ["current_period", "compare_period"]:
                chart_data_points.append({
                    "metric": metric,
                    "period": get_friendly_period_name(period),
                    "value": comparison_data[period].get(metric),
                })

        # 构建数据表格
        data_table = self._build_data_table_for_comparison(
            comparison_data, analysis_plan.metrics
        )

        trace.append({"step": "period_comparison", "status": "success"})

        return AnalysisResult(
            chart_data={
                "chart_config": chart_config.model_dump(),
                "data": chart_data_points,
            },
            data_table=data_table,
            trace=trace,
        )

    def _execute_audience_distribution(
        self,
        analysis_plan: AnalysisPlan,
        entity_ids: Optional[List[Any]],
        entity_level: Optional[str],
        advertiser_ids: List[str],
        start_date: str,
        end_date: str,
        trace: List[Dict[str, Any]],
    ) -> AnalysisResult:
        """执行受众分布分析"""
        trace.append({"step": "audience_distribution", "status": "started"})

        # Check if we have anything to execute
        has_single_step = bool(analysis_plan.audience_dimension)
        has_multi_steps = analysis_plan.steps and len(analysis_plan.steps) > 0
        if not has_single_step and not has_multi_steps:
            raise ValueError("Audience distribution analysis requires audience_dimension (single-step) or steps (multi-step)")

        # For multi-step plans: if we get here, it means this is the final analysis step
        # and the audience_dimension should already be set on the analysis_plan
        # If it's still empty, it's an error
        audience_dimension = analysis_plan.audience_dimension
        metrics = analysis_plan.metrics

        if not audience_dimension:
            raise ValueError("Audience distribution analysis requires audience_dimension")

        if not metrics:
            raise ValueError("Audience distribution analysis requires at least one metric")

        dsl = build_audience_distribution(
            advertiser_ids=advertiser_ids,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            audience_type=audience_dimension,
        )

        # 如果有实体 ID，添加过滤条件
        if entity_ids and entity_level:
            level_field = get_level_field(entity_level)
            dsl["query"]["bool"]["filter"].append({"terms": {level_field: entity_ids}})

        # 执行查询（带重试）
        response = self._execute_with_retry(dsl, "audience_distribution")

        # 提取数据
        audience_data = extract_audience_data(response)

        # 如果有受众值映射，将数字编码转换为中文名称
        if audience_dimension in AUDIENCE_VALUE_MAPS:
            mapping = AUDIENCE_VALUE_MAPS[audience_dimension]
            # audience_data is now {audience_value: {metric_name: value}}
            # we need to map the audience_value key only
            mapped_data = {}
            for key, metric_values in audience_data.items():
                mapped_key = mapping.get(str(key), mapping.get(key, key))
                mapped_data[mapped_key] = metric_values
            audience_data = mapped_data

        # 构建图表配置
        # 如果 analysis_plan 已经指定了 chart_type，默认配置使用它，不要硬编码覆盖
        default_chart_type = analysis_plan.chart_type.value if hasattr(analysis_plan.chart_type, "value") else analysis_plan.chart_type
        chart_config = analysis_plan.chart_config or AnalysisChartConfig(
            type=default_chart_type,
            title=f"{audience_dimension} 分布",
        )

        # 对于饼图，如果 chart_config.series 为空，自动填充series信息，每个标签对应一个系列
        # Only works for single metric case
        if default_chart_type == "pie" and (not chart_config.series) and len(metrics) == 1:
            # 从 audience_data 提取所有标签作为 series
            single_metric = metrics[0]
            series = []
            for label in audience_data.keys():
                series.append({"name": str(label)})
            chart_config.series = series

        # 对于柱状图，如果 x_axis 或 y_axis 为空，自动补全默认配置
        if default_chart_type == "bar":
            if not chart_config.x_axis:
                # x 轴是分类标签，字段名就是 label
                audience_dim_label = audience_dimension or "分类"
                # 尝试映射中文标签
                label_mapping = {
                    "audience_gender": "性别",
                    "audience_age": "年龄",
                    "audience_os": "操作系统",
                    "audience_country": "国家",
                    "audience_city": "城市",
                    "audience_interest": "兴趣",
                }
                display_label = label_mapping.get(audience_dim_label, audience_dim_label)
                chart_config.x_axis = {"field": "category", "label": display_label}
            if not chart_config.y_axis:
                chart_config.y_axis = {"field": "value", "label": "数值"}

        # 构建图表数据
        # For multiple metrics, we only chart the first metric for now
        chart_data_points = []
        if len(metrics) > 0:
            chart_metric = metrics[0]
            for key, metric_values in audience_data.items():
                value = metric_values.get(chart_metric, 0)
                # Pie chart requires 'label' field
                chart_data_points.append({"label": str(key), "value": value})

        # 构建数据表格
        data_table = self._build_data_table_for_audience_multi(
            audience_data, audience_dimension, metrics
        )

        trace.append({"step": "audience_distribution", "status": "success"})

        return AnalysisResult(
            chart_data={
                "chart_config": chart_config.model_dump(),
                "data": chart_data_points,
            },
            data_table=data_table,
            trace=trace,
        )

    def _execute_summary(
        self,
        analysis_plan: AnalysisPlan,
        entity_ids: Optional[List[Any]],
        entity_level: Optional[str],
        advertiser_ids: List[str],
        start_date: str,
        end_date: str,
        trace: List[Dict[str, Any]],
    ) -> AnalysisResult:
        """执行汇总指标分析"""
        trace.append({"step": "summary", "status": "started"})

        dsl = build_summary(
            advertiser_ids=advertiser_ids,
            start_date=start_date,
            end_date=end_date,
            metrics=analysis_plan.metrics,
        )

        # 如果有实体 ID，添加过滤条件
        if entity_ids and entity_level:
            level_field = get_level_field(entity_level)
            dsl["query"]["bool"]["filter"].append({"terms": {level_field: entity_ids}})

        # 执行查询（带重试）
        response = self._execute_with_retry(dsl, "summary")

        # 提取数据
        summary_data = extract_summary_data(response, analysis_plan.metrics)

        # 构建图表配置
        # 如果 analysis_plan 已经指定了 chart_type，默认配置使用它，不要硬编码覆盖
        default_chart_type = analysis_plan.chart_type.value if hasattr(analysis_plan.chart_type, "value") else analysis_plan.chart_type
        chart_config = analysis_plan.chart_config or AnalysisChartConfig(
            type=default_chart_type,
            title="汇总指标",
        )

        # 构建图表数据
        chart_data_points = [
            {"metric": metric, "value": value}
            for metric, value in summary_data.items()
        ]

        # 构建数据表格
        data_table = self._build_data_table_for_summary(summary_data)

        trace.append({"step": "summary", "status": "success"})

        return AnalysisResult(
            chart_data={
                "chart_config": chart_config.model_dump(),
                "data": chart_data_points,
            },
            data_table=data_table,
            trace=trace,
        )

    def _execute_with_retry(self, dsl: Dict[str, Any], step_name: str) -> Dict[str, Any]:
        """执行查询（带重试）"""
        max_attempts = 2  # 1 次重试，共 2 次尝试
        last_exception = None
        index = dsl.pop("index", "ad_stat_data")

        for attempt in range(1, max_attempts + 1):
            try:
                return self.es_client.search(index=index, body=dsl)
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    logger.warning(f"Analysis step {step_name} attempt {attempt} failed, retrying: {str(e)}")
                else:
                    logger.error(f"Analysis step {step_name} all attempts failed: {str(e)}")

        raise last_exception

    def _build_data_table_for_trend(
        self,
        trend_data: Dict[str, Any],
        metric: str,
        series_level: Optional[str],
    ) -> AnalysisDataTable:
        """为趋势分析构建数据表格

        多系列使用长格式（每行 date + series + value），避免列爆炸。
        缺失数据按指标类型补零。
        """
        # 只有当 series_level 不为空且不是 date 相关维度时，才是真正的多系列
        # date_related 分组本身就是趋势分析的分组维度，不代表多系列
        # 顶级实体ID（advertiser/advertiser_id）也不代表多系列（因为我们已经筛选了该advertiser）
        date_related = ['data_date', 'date', 'day', 'month', 'time', 'advertiser_id', 'advertiser']
        if series_level and series_level.lower() not in date_related:
            # 多系列 → 长格式：每行 date × series → 避免列爆炸
            # 获取所有系列 ID 和 所有日期
            all_series = set()
            all_dates = set()
            for date_key, series_values in trend_data.items():
                all_dates.add(date_key)
                if isinstance(series_values, dict):
                    all_series.update(series_values.keys())

            # 判断指标类型，确定补零值
            integer_metrics = {'impressions', 'clicks', 'cost', 'conversions', 'reach'}
            fill_value = 0 if metric in integer_metrics else 0.0

            # 排序
            sorted_dates = sorted(all_dates)
            sorted_series = sorted(all_series)

            # 构建长格式表格：每行 date × series
            columns = [
                {"key": "date", "label": "日期"},
                {"key": "series_id", "label": f"{series_level} ID"},
                {"key": "series_name", "label": f"{series_level} 名称"},
                {"key": metric, "label": metric},
            ]
            rows = []

            # 对每个日期 × 每个系列 都生成一行，缺失补零
            for date_key in sorted_dates:
                series_values = trend_data.get(date_key, {})
                if not isinstance(series_values, dict):
                    series_values = {}

                for series_id in sorted_series:
                    series_name = self.entity_name_resolver.get(series_id, str(series_id))
                    value = series_values.get(series_id, fill_value)
                    row = {
                        "date": date_key,
                        "series_id": str(series_id),
                        "series_name": series_name,
                        metric: value,
                    }
                    rows.append(row)
        else:
            # 单系列 → 简单一列
            columns = [
                {"key": "date", "label": "日期"},
                {"key": metric, "label": metric},
            ]
            rows = []
            for date_key, value in sorted(trend_data.items()):
                rows.append({"date": date_key, metric: value})

        return AnalysisDataTable(columns=columns, rows=rows)

    def _build_data_table_for_entity(
        self,
        table_data: Dict[Any, Dict[str, float]],
        metrics: List[str],
        group_by_level: str,
    ) -> AnalysisDataTable:
        """为实体表格分析构建数据表格"""
        id_field = f"{group_by_level}_id"
        name_field = f"{group_by_level}_name"

        columns = [
            {"key": id_field, "label": f"{group_by_level} ID"},
            {"key": name_field, "label": f"{group_by_level} 名称"},
        ]
        for metric in metrics:
            columns.append({"key": metric, "label": metric})

        rows = []
        for entity_id, metrics_dict in table_data.items():
            entity_name = self.entity_name_resolver.get(entity_id, str(entity_id))
            row = {
                id_field: entity_id,
                name_field: entity_name,
            }
            for metric in metrics:
                row[metric] = metrics_dict.get(metric)
            rows.append(row)

        return AnalysisDataTable(columns=columns, rows=rows)

    def _build_chart_data_for_entity(
        self,
        table_data: Dict[Any, Dict[str, float]],
        metrics: List[str],
        group_by_level: str,
        chart_config: AnalysisChartConfig,
    ) -> Dict[str, Any]:
        """为实体表格分析构建图表数据"""
        data_points = []

        for entity_id, metrics_dict in table_data.items():
            entity_name = self.entity_name_resolver.get(entity_id, str(entity_id))
            point = {f"{group_by_level}_name": entity_name}
            for metric in metrics:
                point[metric] = metrics_dict.get(metric)
            data_points.append(point)

        return {
            "chart_config": chart_config.model_dump(),
            "data": data_points,
        }

    def _build_data_table_for_comparison(
        self,
        comparison_data: Dict[str, Dict[str, float]],
        metrics: List[str],
    ) -> AnalysisDataTable:
        """为时期对比分析构建数据表格"""
        columns = [
            {"key": "metric", "label": "指标"},
            {"key": "current", "label": "当前期"},
            {"key": "compare", "label": "对比期"},
            {"key": "change", "label": "变化"},
            {"key": "change_pct", "label": "变化率"},
        ]

        rows = []
        for metric in metrics:
            current = comparison_data["current_period"].get(metric)
            compare = comparison_data["compare_period"].get(metric)

            change = None
            change_pct = None
            if current is not None and compare is not None:
                change = current - compare
                if compare != 0:
                    change_pct = (change / compare) * 100

            rows.append({
                "metric": metric,
                "current": current,
                "compare": compare,
                "change": change,
                "change_pct": change_pct,
            })

        return AnalysisDataTable(columns=columns, rows=rows)

    def _build_data_table_for_audience(
        self,
        audience_data: Dict[str, float],
        audience_type: str,
        metric: str,
    ) -> AnalysisDataTable:
        """为受众分布分析构建数据表格"""
        columns = [
            {"key": "category", "label": f"{audience_type} 类别"},
            {"key": "value", "label": metric},
            {"key": "percentage", "label": "占比"},
        ]

        total = sum(audience_data.values()) if audience_data else 0

        rows = []
        for category, value in audience_data.items():
            percentage = (value / total * 100) if total > 0 else None
            rows.append({
                "category": category,
                "value": value,
                "percentage": percentage,
            })

        return AnalysisDataTable(columns=columns, rows=rows)

    def _build_data_table_for_audience_multi(
        self,
        audience_data: Dict[str, Dict[str, float]],
        audience_type: str,
        metrics: List[str],
    ) -> AnalysisDataTable:
        """为受众分布分析构建数据表格 - 支持多指标"""
        columns = [
            {"key": "category", "label": f"{audience_type} 类别"},
        ]
        for metric in metrics:
            columns.append({"key": metric, "label": metric})

        # 单指标情况下添加百分比列（和测试期望一致）
        if len(metrics) == 1:
            columns.append({"key": "percentage", "label": "占比"})

        # Calculate total percentage based on first metric
        first_metric = metrics[0] if metrics else None
        total = 0.0
        if first_metric:
            for metric_values in audience_data.values():
                val = metric_values.get(first_metric, 0)
                if isinstance(val, (int, float)):
                    total += val

        rows = []
        for category, metric_values in audience_data.items():
            row = {"category": category}
            row.update(metric_values)
            # 单指标情况下添加百分比
            if len(metrics) == 1 and total > 0:
                percentage = (metric_values.get(first_metric, 0) / total * 100) if total > 0 else None
                row["percentage"] = percentage
            rows.append(row)

        return AnalysisDataTable(columns=columns, rows=rows)

    def _build_data_table_for_summary(
        self,
        summary_data: Dict[str, float],
    ) -> AnalysisDataTable:
        """为汇总指标分析构建数据表格"""
        columns = [
            {"key": "metric", "label": "指标"},
            {"key": "value", "label": "数值"},
        ]

        rows = [
            {"metric": metric, "value": value}
            for metric, value in summary_data.items()
        ]

        return AnalysisDataTable(columns=columns, rows=rows)
