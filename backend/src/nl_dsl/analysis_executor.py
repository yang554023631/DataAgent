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
        date_related = ['data_date', 'date', 'day', 'month', 'time']
        if series_level and series_level.lower() not in date_related:
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
        chart_data_points = []
        for date_key, value in trend_data.items():
            if series_level and isinstance(value, dict):
                # 多系列: {date: {series_id: value, ...}}
                point = {"date": date_key}
                for series_id, series_value in value.items():
                    point[str(series_id)] = series_value
                chart_data_points.append(point)
            else:
                # 单系列: {date: value}
                chart_data_points.append({"date": date_key, metric: value})

        # 构建数据表格
        data_table = self._build_data_table_for_trend(
            trend_data, metric, series_level
        )

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

        if not analysis_plan.audience_type:
            raise ValueError("Audience distribution analysis requires audience_type")

        if not analysis_plan.metrics:
            raise ValueError("Audience distribution analysis requires at least one metric")
        metric = analysis_plan.metrics[0]

        dsl = build_audience_distribution(
            advertiser_ids=advertiser_ids,
            start_date=start_date,
            end_date=end_date,
            metric=metric,
            audience_type=analysis_plan.audience_type,
        )

        # 如果有实体 ID，添加过滤条件
        if entity_ids and entity_level:
            level_field = get_level_field(entity_level)
            dsl["query"]["bool"]["filter"].append({"terms": {level_field: entity_ids}})

        # 执行查询（带重试）
        response = self._execute_with_retry(dsl, "audience_distribution")

        # 提取数据
        audience_data = extract_audience_data(response)

        # 构建图表配置
        # 如果 analysis_plan 已经指定了 chart_type，默认配置使用它，不要硬编码覆盖
        default_chart_type = analysis_plan.chart_type.value if hasattr(analysis_plan.chart_type, "value") else analysis_plan.chart_type
        chart_config = analysis_plan.chart_config or AnalysisChartConfig(
            type=default_chart_type,
            title=f"{analysis_plan.audience_type} 分布",
        )

        # 构建图表数据
        chart_data_points = [
            {"category": key, "value": value}
            for key, value in audience_data.items()
        ]

        # 构建数据表格
        data_table = self._build_data_table_for_audience(
            audience_data, analysis_plan.audience_type, metric
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
        """为趋势分析构建数据表格"""
        columns = [{"key": "date", "label": "日期"}]
        rows = []

        if series_level:
            # 多系列
            # 获取所有系列 ID
            all_series = set()
            for date_key, series_values in trend_data.items():
                if isinstance(series_values, dict):
                    all_series.update(series_values.keys())

            # 添加系列列
            for series_id in sorted(all_series):
                series_name = self.entity_name_resolver.get(series_id, str(series_id))
                columns.append({"key": str(series_id), "label": series_name})

            # 构建行
            for date_key, series_values in sorted(trend_data.items()):
                row = {"date": date_key}
                if isinstance(series_values, dict):
                    for series_id, value in series_values.items():
                        row[str(series_id)] = value
                rows.append(row)
        else:
            # 单系列
            columns.append({"key": metric, "label": metric})
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
