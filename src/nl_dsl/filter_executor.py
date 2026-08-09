"""筛选计划执行器"""
from typing import List, Dict, Any, Optional
import logging
from .models import FilterPlan, FilterStep, FilterResult, FilterCondition
from .dsl_templates import (
    build_having_filter,
    build_derived_having_filter,
    build_where_dimension_filter,
    build_cross_level_up_filter,
    build_cross_level_down_filter_step1,
    build_full_filter,
    extract_entity_ids,
    validate_es_dsl,
    LEVEL_TO_FIELD,
    is_derived_metric,
)

logger = logging.getLogger(__name__)

# ID 数量软上限
MAX_IDS = 500


class FilterExecutor:
    """筛选计划执行器"""

    def __init__(self, es_client):
        """
        初始化筛选执行器

        Args:
            es_client: Elasticsearch 客户端实例
        """
        self.es_client = es_client

    def execute(
        self,
        filter_plan: FilterPlan,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
    ) -> FilterResult:
        """
        执行筛选计划

        Args:
            filter_plan: 筛选计划
            advertiser_ids: 广告主 ID 列表
            time_range: 时间范围，包含 start_date 和 end_date

        Returns:
            FilterResult: 筛选结果
        """
        trace = []
        current_entity_ids: Optional[List[Any]] = filter_plan.entity_ids
        current_level = filter_plan.target_level

        # 如果是 none 类型筛选（全量），直接返回
        if filter_plan.filter_type == "none" or not filter_plan.steps:
            return FilterResult(
                entity_ids=current_entity_ids or [],
                entity_level=current_level,
                total_count=len(current_entity_ids) if current_entity_ids else 0,
                trace=[{"step": "none", "action": "full_scan", "status": "success"}],
            )

        # 逐步执行筛选
        for step in filter_plan.steps:
            step_trace = {
                "step_id": step.step_id,
                "step_type": step.step_type,
                "level": step.level,
                "status": "pending",
            }

            try:
                # 执行步骤（带重试）
                entity_ids = self._execute_step_with_retry(
                    step=step,
                    advertiser_ids=advertiser_ids,
                    time_range=time_range,
                    previous_entity_ids=current_entity_ids,
                )

                # 去重（向上汇总时）
                if step.step_type == "cross_level_up":
                    entity_ids = list(set(entity_ids))

                # 软上限截断
                truncated = False
                if len(entity_ids) > MAX_IDS:
                    # 这里需要注意：我们应该按某种优先级排序，比如消耗
                    # 但目前阶段先简单截断前 500 个
                    entity_ids = entity_ids[:MAX_IDS]
                    truncated = True
                    logger.warning(f"Step {step.step_id}: Entity IDs truncated to {MAX_IDS}")

                step_trace.update({
                    "status": "success",
                    "entity_count": len(entity_ids),
                    "truncated": truncated,
                })

                # 更新当前实体 ID 列表和层级
                current_entity_ids = entity_ids
                current_level = step.level

            except Exception as e:
                logger.error(f"Step {step.step_id} failed: {str(e)}", exc_info=True)
                step_trace.update({
                    "status": "failed",
                    "error": str(e),
                })
                raise

            trace.append(step_trace)

        return FilterResult(
            entity_ids=current_entity_ids or [],
            entity_level=current_level,
            total_count=len(current_entity_ids) if current_entity_ids else 0,
            trace=trace,
            truncated=any(t.get("truncated", False) for t in trace),
        )

    def _execute_step_with_retry(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        previous_entity_ids: Optional[List[Any]] = None,
    ) -> List[Any]:
        """
        执行单个筛选步骤（带重试）

        Args:
            step: 筛选步骤
            advertiser_ids: 广告主 ID 列表
            time_range: 时间范围
            previous_entity_ids: 上一步输出的实体 ID 列表

        Returns:
            筛选出的实体 ID 列表
        """
        max_attempts = 2  # 1 次重试，共 2 次尝试
        last_exception = None

        for attempt in range(1, max_attempts + 1):
            try:
                return self._execute_step(
                    step=step,
                    advertiser_ids=advertiser_ids,
                    time_range=time_range,
                    previous_entity_ids=previous_entity_ids,
                )
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    logger.warning(f"Step {step.step_id} attempt {attempt} failed, retrying: {str(e)}")
                else:
                    logger.error(f"Step {step.step_id} all attempts failed: {str(e)}")

        raise last_exception

    def _execute_step(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        previous_entity_ids: Optional[List[Any]] = None,
    ) -> List[Any]:
        """
        执行单个筛选步骤

        Args:
            step: 筛选步骤
            advertiser_ids: 广告主 ID 列表
            time_range: 时间范围
            previous_entity_ids: 上一步输出的实体 ID 列表

        Returns:
            筛选出的实体 ID 列表
        """
        # 构建 DSL
        dsl = self._build_dsl_for_step(
            step=step,
            advertiser_ids=advertiser_ids,
            time_range=time_range,
            previous_entity_ids=previous_entity_ids,
        )

        # 如果是全量筛选，直接返回
        if dsl is None:
            return []

        # 执行查询
        index = dsl.pop("index", step.index)
        response = self.es_client.search(index=index, body=dsl)

        # 确定聚合路径
        if step.step_type == "cross_level_up":
            # 跨层级向上：聚合是按目标层级（output_field）来的
            target_level = step.output_field.replace("_id", "")
            agg_path = f"by_{target_level}"
        else:
            agg_path = f"by_{step.level}"

        # 提取实体 ID
        entity_ids = extract_entity_ids(response, agg_path)

        return entity_ids

    def _build_dsl_for_step(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        previous_entity_ids: Optional[List[Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        为筛选步骤构建 DSL

        Args:
            step: 筛选步骤
            advertiser_ids: 广告主 ID 列表
            time_range: 时间范围
            previous_entity_ids: 上一步输出的实体 ID 列表

        Returns:
            Elasticsearch DSL 查询
        """
        step_type = step.step_type

        if step_type == "where_filter":
            return self._build_where_filter_dsl(
                step=step,
                advertiser_ids=advertiser_ids,
                previous_entity_ids=previous_entity_ids,
            )
        elif step_type == "having_filter":
            return self._build_having_filter_dsl(
                step=step,
                advertiser_ids=advertiser_ids,
                time_range=time_range,
                previous_entity_ids=previous_entity_ids,
            )
        elif step_type == "cross_level_up":
            return self._build_cross_level_up_dsl(
                step=step,
                advertiser_ids=advertiser_ids,
                previous_entity_ids=previous_entity_ids,
            )
        elif step_type == "cross_level_down":
            return self._build_cross_level_down_dsl(
                step=step,
                advertiser_ids=advertiser_ids,
                previous_entity_ids=previous_entity_ids,
            )
        elif step_type == "full_filter":
            return build_full_filter(advertiser_ids, step.level)
        else:
            raise ValueError(f"Unknown step type: {step_type}")

    def _build_where_filter_dsl(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        previous_entity_ids: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """构建 where 筛选 DSL"""
        dsl = build_where_dimension_filter(
            advertiser_ids=advertiser_ids,
            level=step.level,
            conditions=[],  # 先构建基础 DSL
            index=step.index,
        )

        # 如果有上一步的实体 ID，添加到过滤条件
        if previous_entity_ids:
            # 需要确定用哪个字段来过滤
            # 这里假设上一步的输出字段可以映射到当前层级的字段
            # 简化处理：直接添加到 query.bool.filter
            for cond in dsl["query"]["bool"]["filter"]:
                if isinstance(cond, dict) and "terms" in cond and "advertiser_id" in cond["terms"]:
                    # 在 advertiser_id 条件后添加
                    break
            else:
                # 添加到开头
                dsl["query"]["bool"]["filter"].insert(0, {"terms": {"advertiser_id": advertiser_ids}})

        # 处理步骤中的条件
        # build_where_dimension_filter expects conditions in a specific format
        # 我们需要把 FilterCondition 转换为字典格式
        condition_dicts = []
        for cond in step.conditions:
            condition_dicts.append({
                "field": cond.field,
                "operator": cond.operator,
                "value": cond.value,
            })

        # 重新构建带条件的 DSL
        if condition_dicts:
            dsl = build_where_dimension_filter(
                advertiser_ids=advertiser_ids,
                level=step.level,
                conditions=condition_dicts,
                index=step.index,
            )

        return dsl

    def _build_having_filter_dsl(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        previous_entity_ids: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """构建 having 筛选 DSL"""
        # having 筛选通常只有一个条件（指标条件）
        if not step.conditions:
            raise ValueError(f"Having filter step {step.step_id} has no conditions")

        cond = step.conditions[0]
        metric = cond.metric or cond.field  # 使用 metric 字段或 field

        # 判断是否为派生指标
        if is_derived_metric(metric):
            builder = build_derived_having_filter
        else:
            builder = build_having_filter

        dsl = builder(
            advertiser_ids=advertiser_ids,
            start_date=time_range["start_date"],
            end_date=time_range["end_date"],
            metric=metric,
            operator=cond.operator,
            threshold=float(cond.value) if isinstance(cond.value, (int, float, str)) else cond.value,
            group_by_level=step.level,
        )

        # 如果有上一步的实体 ID，需要注入到过滤条件中
        if previous_entity_ids:
            # 这里需要修改 DSL，添加 terms 过滤
            # 注意：这需要更复杂的逻辑来确定用哪个字段
            # 简化处理：假设使用当前层级的 ID 字段
            level_field = LEVEL_TO_FIELD.get(step.level, f"{step.level}_id")
            dsl["query"]["bool"]["filter"].append({"terms": {level_field: previous_entity_ids}})

        return dsl

    def _build_cross_level_up_dsl(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        previous_entity_ids: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """构建跨层级向上筛选 DSL（从低层级到高层级）"""
        # 提取条件
        if not step.conditions:
            raise ValueError(f"Cross level up step {step.step_id} has no conditions")

        # 第一个条件用于筛选低层级实体
        cond = step.conditions[0]

        dsl = build_cross_level_up_filter(
            advertiser_ids=advertiser_ids,
            low_level=step.level,
            low_level_field=cond.field,
            low_level_value=cond.value,
            low_level_operator=cond.operator,
            target_level=step.output_field.replace("_id", ""),  # 从输出字段推断目标层级
            index=step.index,
        )

        # 如果有上一步的实体 ID，添加到过滤条件
        if previous_entity_ids:
            # 假设上一步的输出字段是当前低层级的 ID
            low_level_field = LEVEL_TO_FIELD.get(step.level, f"{step.level}_id")
            dsl["query"]["bool"]["filter"].append({"terms": {low_level_field: previous_entity_ids}})

        return dsl

    def _build_cross_level_down_dsl(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        previous_entity_ids: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """构建跨层级向下筛选 DSL（从高层级到低层级）"""
        # 这通常是两步：
        # 1. 先查高层级实体 ID（用 where 条件）
        # 2. 再查低层级实体（用 terms 过滤高层级 ID）

        # build_cross_level_down_filter_step1 用于第一步
        condition_dicts = []
        for cond in step.conditions:
            condition_dicts.append({
                "field": cond.field,
                "operator": cond.operator,
                "value": cond.value,
            })

        # 确定高层级（从 output_field 推断或从 step.level）
        high_level = step.level

        dsl = build_cross_level_down_filter_step1(
            advertiser_ids=advertiser_ids,
            high_level=high_level,
            conditions=condition_dicts,
            index=step.index,
        )

        # 如果有上一步的实体 ID，添加到过滤条件
        if previous_entity_ids:
            high_level_field = LEVEL_TO_FIELD.get(high_level, f"{high_level}_id")
            dsl["query"]["bool"]["filter"].append({"terms": {high_level_field: previous_entity_ids}})

        return dsl
