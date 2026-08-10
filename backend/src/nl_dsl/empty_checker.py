"""空结果自查器

在执行完整分析前快速检查是否会得到空结果，避免浪费查询资源。

包含两组并行检查：
1. 静态检查组：规则检查，立即返回
   - 时间范围有效性
   - 指标与维度兼容性
   - 实体ID列表非空

2. ES轻量查询组：快速ES计数/求和查询，<500ms
   - 总文档数>0
   - 核心指标(cost/impressions)求和>0
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime
from .models import (
    EmptyCheckResult,
    EmptyCheckErrorType,
    AnalysisPlan,
    FilterResult,
)
from .dsl_templates.common import (
    get_data_type,
    is_derived_metric,
    DERIVED_METRICS,
    build_time_filter,
    build_common_filters,
)

logger = logging.getLogger(__name__)


class EmptyResultChecker:
    """空结果自查器"""

    def __init__(self, es_client):
        """
        初始化空结果自查器

        Args:
            es_client: Elasticsearch 客户端实例
        """
        self.es_client = es_client

    def check(
        self,
        analysis_plan: AnalysisPlan,
        advertiser_ids: List[str],
        filter_result: Optional[FilterResult] = None,
        entity_ids: Optional[List[Any]] = None,
        entity_level: Optional[str] = None,
    ) -> EmptyCheckResult:
        """
        同步执行空结果检查（同步包装器，兼容非异步调用者）

        Args:
            analysis_plan: 分析计划
            advertiser_ids: 广告主ID列表
            filter_result: 筛选结果（可选）
            entity_ids: 实体ID列表（可选，优先使用 filter_result）
            entity_level: 实体层级（可选）

        Returns:
            EmptyCheckResult: 检查结果
        """
        return asyncio.run(
            self.async_check(
                analysis_plan=analysis_plan,
                advertiser_ids=advertiser_ids,
                filter_result=filter_result,
                entity_ids=entity_ids,
                entity_level=entity_level,
            )
        )

    async def async_check(
        self,
        analysis_plan: AnalysisPlan,
        advertiser_ids: List[str],
        filter_result: Optional[FilterResult] = None,
        entity_ids: Optional[List[Any]] = None,
        entity_level: Optional[str] = None,
    ) -> EmptyCheckResult:
        """
        异步执行空结果检查（并行执行静态检查和ES检查）

        Args:
            analysis_plan: 分析计划
            advertiser_ids: 广告主ID列表
            filter_result: 筛选结果（可选）
            entity_ids: 实体ID列表（可选，优先使用 filter_result）
            entity_level: 实体层级（可选）

        Returns:
            EmptyCheckResult: 检查结果
        """
        # 收集实体ID
        ids = entity_ids
        level = entity_level
        if filter_result:
            ids = filter_result.entity_ids
            level = filter_result.entity_level

        # 并行运行静态检查组和ES轻量查询组
        static_task = asyncio.to_thread(
            self._run_static_checks,
            analysis_plan=analysis_plan,
            entity_ids=ids,
        )
        es_task = asyncio.to_thread(
            self._run_es_checks,
            analysis_plan=analysis_plan,
            advertiser_ids=advertiser_ids,
            entity_ids=ids,
            entity_level=level,
        )

        # 等待两者完成
        static_result, es_result = await asyncio.gather(static_task, es_task)

        # 优先返回静态检查错误（因为更快且无需ES查询）
        if static_result.found_error:
            return static_result

        # 然后返回ES检查错误
        if es_result.found_error:
            return es_result

        # 两者都通过
        return EmptyCheckResult(found_error=False)

    def _run_static_checks(
        self,
        analysis_plan: AnalysisPlan,
        entity_ids: Optional[List[Any]] = None,
    ) -> EmptyCheckResult:
        """运行静态检查组"""
        # 检查 1: 时间范围有效性
        time_range_result = self._check_time_range(analysis_plan)
        if time_range_result.found_error:
            return time_range_result

        # 检查 2: 指标有效性
        metrics_result = self._check_metrics(analysis_plan)
        if metrics_result.found_error:
            return metrics_result

        # 检查 3: 实体ID列表非空（如果有筛选）
        entity_result = self._check_entity_ids(entity_ids)
        if entity_result.found_error:
            return entity_result

        return EmptyCheckResult(found_error=False)

    def _check_time_range(
        self,
        analysis_plan: AnalysisPlan,
    ) -> EmptyCheckResult:
        """检查时间范围有效性"""
        time_range = analysis_plan.time_range
        try:
            start_date = datetime.strptime(time_range.start_date, "%Y-%m-%d")
            end_date = datetime.strptime(time_range.end_date, "%Y-%m-%d")

            if start_date > end_date:
                return EmptyCheckResult(
                    found_error=True,
                    error_type=EmptyCheckErrorType.INVALID_TIME_RANGE,
                    hints=[
                        f"开始日期 ({time_range.start_date}) 晚于结束日期 ({time_range.end_date})",
                        "请检查并调整时间范围",
                    ],
                    correction={
                        "start_date": time_range.end_date,
                        "end_date": time_range.start_date,
                    },
                )

            # 检查时间范围是否合理（例如，不超过3年）
            days_diff = (end_date - start_date).days
            if days_diff > 365 * 3:
                return EmptyCheckResult(
                    found_error=True,
                    error_type=EmptyCheckErrorType.INVALID_TIME_RANGE,
                    hints=[
                        f"时间范围过大 ({days_diff} 天)，建议不超过 3 年",
                    ],
                )

            return EmptyCheckResult(found_error=False)

        except ValueError as e:
            return EmptyCheckResult(
                found_error=True,
                error_type=EmptyCheckErrorType.INVALID_TIME_RANGE,
                hints=[
                    f"日期格式无效: {str(e)}",
                    "请使用 YYYY-MM-DD 格式",
                ],
            )

    def _check_metrics(
        self,
        analysis_plan: AnalysisPlan,
    ) -> EmptyCheckResult:
        """检查指标有效性"""
        invalid_metrics: List[str] = []
        missing_dependencies: Dict[str, List[str]] = {}

        for metric in analysis_plan.metrics:
            if is_derived_metric(metric):
                # 派生指标：检查依赖
                derived = DERIVED_METRICS[metric]
                dependencies = derived["depends_on"]
                missing = []
                for dep in dependencies:
                    if get_data_type(dep) is None:
                        missing.append(dep)
                if missing:
                    missing_dependencies[metric] = missing
            else:
                # 基础指标：检查是否已知
                if get_data_type(metric) is None:
                    invalid_metrics.append(metric)

        hints: List[str] = []
        if invalid_metrics:
            hints.append(f"未知的指标: {', '.join(invalid_metrics)}")
        if missing_dependencies:
            for metric, deps in missing_dependencies.items():
                hints.append(f"指标 {metric} 缺少依赖: {', '.join(deps)}")

        if hints:
            return EmptyCheckResult(
                found_error=True,
                error_type=EmptyCheckErrorType.INVALID_METRICS,
                hints=hints,
            )

        return EmptyCheckResult(found_error=False)

    def _check_entity_ids(
        self,
        entity_ids: Optional[List[Any]] = None,
    ) -> EmptyCheckResult:
        """检查实体ID列表"""
        # 注意：只有当提供了 entity_ids 时才检查，如果是 None 表示全量查询
        if entity_ids is not None and len(entity_ids) == 0:
            return EmptyCheckResult(
                found_error=True,
                error_type=EmptyCheckErrorType.NO_ENTITY_IDS,
                hints=[
                    "筛选结果为空，没有符合条件的实体",
                    "请尝试放宽筛选条件",
                ],
            )

        return EmptyCheckResult(found_error=False)

    def _run_es_checks(
        self,
        analysis_plan: AnalysisPlan,
        advertiser_ids: List[str],
        entity_ids: Optional[List[Any]] = None,
        entity_level: Optional[str] = None,
    ) -> EmptyCheckResult:
        """运行ES轻量查询检查组"""
        time_range = analysis_plan.time_range

        # 构建检查所需的数据类型
        metrics = analysis_plan.metrics
        data_types: Set[int] = set()
        for metric in metrics:
            if is_derived_metric(metric):
                derived = DERIVED_METRICS[metric]
                for dep in derived["depends_on"]:
                    dt = get_data_type(dep)
                    if dt is not None:
                        data_types.add(dt)
            else:
                dt = get_data_type(metric)
                if dt is not None:
                    data_types.add(dt)

        # 构建基础过滤条件
        filters = build_common_filters(
            advertiser_ids=advertiser_ids,
            start_date=time_range.start_date,
            end_date=time_range.end_date,
            data_types=list(data_types) if data_types else None,
        )

        # 添加实体ID过滤（如果有）
        if entity_ids and entity_level:
            from .dsl_templates.common import LEVEL_TO_FIELD
            level_field = LEVEL_TO_FIELD.get(entity_level, f"{entity_level}_id")
            filters.append({"terms": {level_field: entity_ids}})

        # 执行 1: 检查文档总数
        doc_count = self._get_doc_count(filters)
        if doc_count == 0:
            return EmptyCheckResult(
                found_error=True,
                error_type=EmptyCheckErrorType.NO_DOCUMENTS,
                hints=[
                    "在指定的时间范围内没有找到任何数据",
                    "请尝试调整时间范围或广告主",
                ],
            )

        # 执行 2: 检查核心指标求和
        # 总是检查 cost 和 impressions（如果有对应 data_type）
        core_metrics = ["cost", "impressions"]
        core_data_types: Set[int] = set()
        for metric in core_metrics:
            dt = get_data_type(metric)
            if dt is not None:
                core_data_types.add(dt)

        if core_data_types:
            # 重新构建包含核心指标的过滤器
            core_filters = build_common_filters(
                advertiser_ids=advertiser_ids,
                start_date=time_range.start_date,
                end_date=time_range.end_date,
                data_types=list(core_data_types),
            )
            # 添加实体ID过滤（如果有）
            if entity_ids and entity_level:
                from .dsl_templates.common import LEVEL_TO_FIELD
                level_field = LEVEL_TO_FIELD.get(entity_level, f"{entity_level}_id")
                core_filters.append({"terms": {level_field: entity_ids}})

            core_sum = self._get_metrics_sum(core_filters, list(core_data_types))
            if core_sum == 0:
                return EmptyCheckResult(
                    found_error=True,
                    error_type=EmptyCheckErrorType.NO_DATA_VALUES,
                    hints=[
                        "在指定条件下，核心指标(cost/impressions)的总和为零",
                        "请尝试调整筛选条件或时间范围",
                    ],
                )

        return EmptyCheckResult(found_error=False)

    def _get_doc_count(self, filters: List[Dict[str, Any]]) -> int:
        """获取文档总数"""
        dsl = {
            "query": {
                "bool": {
                    "filter": filters,
                },
            },
            "size": 0,
        }

        try:
            response = self.es_client.search(index="ad_stat_data", body=dsl)
            return response.get("hits", {}).get("total", {}).get("value", 0)
        except Exception as e:
            logger.warning(f"Failed to get doc count: {str(e)}")
            # 出错时假设存在文档，继续后续流程
            return 1

    def _get_metrics_sum(
        self,
        filters: List[Dict[str, Any]],
        data_types: List[int],
    ) -> float:
        """获取指标总和"""
        # 构建每个 data_type 的 sum 聚合
        aggs = {}
        for dt in data_types:
            aggs[f"sum_dt_{dt}"] = {
                "filter": {"term": {"data_type": dt}},
                "aggs": {
                    "total": {"sum": {"field": "data_value"}},
                },
            }

        dsl = {
            "query": {
                "bool": {
                    "filter": filters,
                },
            },
            "size": 0,
            "aggs": aggs,
        }

        try:
            response = self.es_client.search(index="ad_stat_data", body=dsl)
            total_sum = 0.0
            aggregations = response.get("aggregations", {})
            for dt in data_types:
                agg_result = aggregations.get(f"sum_dt_{dt}", {})
                dt_sum = agg_result.get("total", {}).get("value", 0)
                if dt_sum:
                    total_sum += dt_sum
            return total_sum
        except Exception as e:
            logger.warning(f"Failed to get metrics sum: {str(e)}")
            # 出错时假设存在数据，继续后续流程
            return 1.0
