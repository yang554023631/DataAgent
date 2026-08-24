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
    get_level_index,
    is_derived_metric,
)

logger = logging.getLogger(__name__)

# ID 数量软上限
MAX_IDS = 500

# 字段 -> 维度索引映射：哪些字段只存在于维度表
FIELD_TO_DIM_INDEX = {
    "campaign_name": "campaign",
    "ad_group_name": "adgroup",
    "adgroup_name": "adgroup",  # alias for both naming conventions
    "creative_name": "creative",
    "status": "campaign",          # 计划状态只在维度表
    "campaign_status": "campaign",
    "ad_group_status": "adgroup",
    "adgroup_status": "adgroup",  # alias for both naming conventions
    "creative_status": "creative",
}

# ID字段名映射：每个维度表对应的ID字段名
DIM_ID_FIELD = {
    "campaign": "campaign_id",
    "adgroup": "ad_group_id",
    "creative": "creative_id",
}


class FilterExecutor:
    """筛选计划执行器"""

    def __init__(self, es_client):
        """
        初始化筛选执行器

        Args:
            es_client: Elasticsearch 客户端实例
        """
        self.es_client = es_client

    async def execute(
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
            # Special case: when target_level is advertiser and current_entity_ids is None,
            # use the top-level advertiser_ids as the entity ids since we've already filtered them upstream
            if current_level == "advertiser" and current_entity_ids is None:
                # Convert to int if possible just like in build_common_filters
                converted_ids = []
                for adv_id in advertiser_ids:
                    try:
                        converted_ids.append(int(adv_id))
                    except ValueError:
                        converted_ids.append(adv_id)
                return FilterResult(
                    entity_ids=converted_ids,
                    entity_level=current_level,
                    total_count=len(converted_ids),
                    trace=[{"step": "none", "action": "full_scan (use top-level advertiser_ids)", "status": "success"}],
                )
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
                entity_ids = await self._execute_step_with_retry(
                    step=step,
                    advertiser_ids=advertiser_ids,
                    time_range=time_range,
                    previous_entity_ids=current_entity_ids,
                    previous_entity_level=current_level,
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
                # 确定输出层级（对于 cross_level_up/down，使用 output_field）
                if step.step_type in ("cross_level_up", "cross_level_down"):
                    current_level = step.output_field.replace("_id", "")
                else:
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

    async def _execute_step_with_retry(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        previous_entity_ids: Optional[List[Any]] = None,
        previous_entity_level: Optional[str] = None,
    ) -> List[Any]:
        """
        执行单个筛选步骤（带重试）

        Args:
            step: 筛选步骤
            advertiser_ids: 广告主 ID 列表
            time_range: 时间范围
            previous_entity_ids: 上一步输出的实体 ID 列表
            previous_entity_level: 上一步输出的实体层级

        Returns:
            筛选出的实体 ID 列表
        """
        max_attempts = 2  # 1 次重试，共 2 次尝试
        last_exception = None

        for attempt in range(1, max_attempts + 1):
            try:
                return await self._execute_step(
                    step=step,
                    advertiser_ids=advertiser_ids,
                    time_range=time_range,
                    previous_entity_ids=previous_entity_ids,
                    previous_entity_level=previous_entity_level,
                )
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    logger.warning(f"Step {step.step_id} attempt {attempt} failed, retrying: {str(e)}")
                else:
                    logger.error(f"Step {step.step_id} all attempts failed: {str(e)}")

        raise last_exception

    async def _execute_step(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        previous_entity_ids: Optional[List[Any]] = None,
        previous_entity_level: Optional[str] = None,
    ) -> List[Any]:
        """
        执行单个筛选步骤

        Args:
            step: 筛选步骤
            advertiser_ids: 广告主 ID 列表
            time_range: 时间范围
            previous_entity_ids: 上一步输出的实体 ID 列表
            previous_entity_level: 上一步输出的实体层级

        Returns:
            筛选出的实体 ID 列表
        """
        # 对于 cross_level_down，需要两个步骤
        if step.step_type == "cross_level_down":
            return await self._execute_cross_level_down(
                step=step,
                advertiser_ids=advertiser_ids,
                time_range=time_range,
                previous_entity_ids=previous_entity_ids,
                previous_entity_level=previous_entity_level,
            )

        # 构建 DSL，如果所有条件都是维度表独有，我们已经得到匹配 IDs，直接返回
        dsl, matched_ids = await self._build_dsl_for_step(
            step=step,
            advertiser_ids=advertiser_ids,
            time_range=time_range,
            previous_entity_ids=previous_entity_ids,
            previous_entity_level=previous_entity_level,
        )

        # 如果我们已经通过维度表找到了匹配的 IDs，直接返回它们
        if matched_ids is not None:
            return matched_ids

        # 如果是全量筛选，直接返回
        if dsl is None:
            return []

        # 执行查询
        index = dsl.pop("index", step.index)
        response = await self.es_client.search(index=index, body=dsl)

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

    async def _build_dsl_for_step(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        previous_entity_ids: Optional[List[Any]] = None,
        previous_entity_level: Optional[str] = None,
    ) -> tuple[Optional[Dict[str, Any]], Optional[List[Any]]]:
        """
        为筛选步骤构建 DSL

        Args:
            step: 筛选步骤
            advertiser_ids: 广告主 ID 列表
            time_range: 时间范围
            previous_entity_ids: 上一步输出的实体 ID 列表
            previous_entity_level: 上一步输出的实体层级

        Returns:
            Tuple of (Elasticsearch DSL query, matched entity IDs from dimension lookup if any)
        """
        step_type = step.step_type

        if step_type == "where_filter":
            return await self._build_where_filter_dsl(
                step=step,
                advertiser_ids=advertiser_ids,
                previous_entity_ids=previous_entity_ids,
                previous_entity_level=previous_entity_level,
            )
        elif step_type == "having_filter":
            dsl = self._build_having_filter_dsl(
                step=step,
                advertiser_ids=advertiser_ids,
                time_range=time_range,
                previous_entity_ids=previous_entity_ids,
                previous_entity_level=previous_entity_level,
            )
            return (dsl, None)
        elif step_type == "cross_level_up":
            dsl = self._build_cross_level_up_dsl(
                step=step,
                advertiser_ids=advertiser_ids,
                previous_entity_ids=previous_entity_ids,
                previous_entity_level=previous_entity_level,
            )
            return (dsl, None)
        elif step_type == "full_filter":
            dsl = build_full_filter(advertiser_ids, step.level, step.index)
            return (dsl, None)
        else:
            raise ValueError(f"Unknown step type: {step_type}")

    async def _build_where_filter_dsl(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        previous_entity_ids: Optional[List[Any]] = None,
        previous_entity_level: Optional[str] = None,
    ) -> tuple[Dict[str, Any], Optional[List[Any]]]:
        """构建 where 筛选 DSL"""
        # 把 FilterCondition 转换为字典格式
        condition_dicts = []
        dimension_conditions_need_lookup = []

        # 分离条件：哪些条件需要先在维度表搜索获取 ID
        for cond in step.conditions:
            field = cond.field
            if field in FIELD_TO_DIM_INDEX:
                dimension_conditions_need_lookup.append(cond)
            else:
                condition_dicts.append({
                    "field": cond.field,
                    "operator": cond.operator,
                    "value": cond.value,
                })

        # 如果有维度表字段需要先查找 ID
        matched_ids_from_dimension = None
        if dimension_conditions_need_lookup:
            # 所有这些条件都在同一个维度表，因为同一个筛选步骤是针对同一层级
            # 所以取第一个条件的维度表即可
            first_field = dimension_conditions_need_lookup[0].field
            dim_index = FIELD_TO_DIM_INDEX[first_field]
            dim_id_field = DIM_ID_FIELD[dim_index]

            # 构建维度表查询条件
            must_clauses = []
            for cond in dimension_conditions_need_lookup:
                field = cond.field
                op = cond.operator
                value = cond.value

                # Try to convert to number if possible for numeric fields
                try:
                    if isinstance(value, str):
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                except (ValueError, TypeError):
                    pass

                if op == "like":
                    must_clauses.append({"wildcard": {field: f"*{value}*"}})
                elif op == "eq":
                    must_clauses.append({"term": {field: value}})
                elif op == "gt":
                    must_clauses.append({"range": {field: {"gt": value}}})
                elif op == "gte":
                    must_clauses.append({"range": {field: {"gte": value}}})
                elif op == "lt":
                    must_clauses.append({"range": {field: {"lt": value}}})
                elif op == "lte":
                    must_clauses.append({"range": {field: {"lte": value}}})
                elif op == "in" and isinstance(value, list):
                    must_clauses.append({"terms": {field: value}})

            # 如果有广告主过滤，维度表也要加上
            if advertiser_ids:
                must_clauses.append({"terms": {"advertiser_id": [int(aid) for aid in advertiser_ids]}})

            # 如果有上一步的实体 ID，维度表也要加上
            if previous_entity_ids and previous_entity_level:
                previous_level_field = LEVEL_TO_FIELD.get(
                    previous_entity_level,
                    f"{previous_entity_level}_id",
                )
                converted_previous_ids = []
                for eid in previous_entity_ids:
                    try:
                        converted_previous_ids.append(int(eid))
                    except ValueError:
                        converted_previous_ids.append(eid)
                must_clauses.append({"terms": {previous_level_field: converted_previous_ids}})

            # 在维度表搜索
            dsl_dim = {
                "query": {"bool": {"must": must_clauses}},
                "size": 1000,
            }
            response = await self.es_client.search(index=dim_index, body=dsl_dim)

            # 提取匹配到的 ID
            matched_ids = []
            for hit in response["hits"]["hits"]:
                eid = hit["_source"].get(dim_id_field)
                if eid is not None:
                    try:
                        matched_ids.append(int(eid))
                    except (ValueError, TypeError):
                        matched_ids.append(eid)

            matched_ids_from_dimension = matched_ids

        # 构建带条件的 DSL
        dsl = build_where_dimension_filter(
            advertiser_ids=advertiser_ids,
            level=step.level,
            conditions=condition_dicts,
            index=step.index,
        )

        # 如果有上一步的实体 ID，添加到过滤条件
        if previous_entity_ids and previous_entity_level:
            # 确定用哪个字段来过滤（上一步的层级对应的字段）
            previous_level_field = LEVEL_TO_FIELD.get(
                previous_entity_level,
                f"{previous_entity_level}_id",
            )
            # 转换实体 ID 为整数如果可能（因为 dimension tables 存储整数 ID）
            converted_previous_ids = []
            for eid in previous_entity_ids:
                try:
                    converted_previous_ids.append(int(eid))
                except ValueError:
                    converted_previous_ids.append(eid)
            # 如果我们已经从维度表找到了匹配ID，就不需要再加上一步过滤了，因为维度表已经过滤过
            if not matched_ids_from_dimension:
                dsl["query"]["bool"]["filter"].append(
                    {"terms": {previous_level_field: converted_previous_ids}}
                )

        # 如果我们从维度表找到了匹配 ID，这些就是最终结果
        # 直接返回 (dsl, matched_ids) 给 _execute_step
        if matched_ids_from_dimension is not None:
            target_level_field = LEVEL_TO_FIELD.get(step.level, f"{step.level}_id")
            dsl["query"]["bool"]["filter"].append(
                {"terms": {target_level_field: matched_ids_from_dimension}}
            )
            # Return DSL and the matched IDs directly - no need to query again
            return (dsl, matched_ids_from_dimension)

        # No matched from dimension - return (dsl, None)
        return (dsl, None)

    def _build_having_filter_dsl(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        previous_entity_ids: Optional[List[Any]] = None,
        previous_entity_level: Optional[str] = None,
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

        # 如果有上一步的实体 ID，添加到过滤条件
        if previous_entity_ids and previous_entity_level:
            previous_level_field = LEVEL_TO_FIELD.get(
                previous_entity_level,
                f"{previous_entity_level}_id",
            )
            # 转换实体 ID 为整数如果可能（因为 dimension tables 存储整数 ID）
            converted_previous_ids = []
            for eid in previous_entity_ids:
                try:
                    converted_previous_ids.append(int(eid))
                except ValueError:
                    converted_previous_ids.append(eid)
            dsl["query"]["bool"]["filter"].append(
                {"terms": {previous_level_field: converted_previous_ids}}
            )

        return dsl

    def _build_cross_level_up_dsl(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        previous_entity_ids: Optional[List[Any]] = None,
        previous_entity_level: Optional[str] = None,
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
        if previous_entity_ids and previous_entity_level:
            previous_level_field = LEVEL_TO_FIELD.get(
                previous_entity_level,
                f"{previous_entity_level}_id",
            )
            # 转换实体 ID 为整数如果可能（因为 dimension tables 存储整数 ID）
            converted_previous_ids = []
            for eid in previous_entity_ids:
                try:
                    converted_previous_ids.append(int(eid))
                except ValueError:
                    converted_previous_ids.append(eid)
            dsl["query"]["bool"]["filter"].append(
                {"terms": {previous_level_field: converted_previous_ids}}
            )

        return dsl

    async def _execute_cross_level_down(
        self,
        step: FilterStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        previous_entity_ids: Optional[List[Any]] = None,
        previous_entity_level: Optional[str] = None,
    ) -> List[Any]:
        """执行跨层级向下筛选（两步查询）

        Step 1: 过滤高层级实体得到高层级 ID
        Step 2: 用高层级 ID 过滤低层级实体得到低层级 ID
        如果条件包含维度表独有字段（名称、状态等），先在维度表过滤得到 IDs
        """
        # 目标层级从 output_field 推断
        target_level = step.output_field.replace("_id", "")
        high_level = step.level

        # 分离条件：哪些条件需要先在维度表搜索获取 ID
        condition_dicts = []
        dimension_conditions_need_lookup = []
        for cond in step.conditions:
            field = cond.field
            if field in FIELD_TO_DIM_INDEX:
                dimension_conditions_need_lookup.append(cond)
            else:
                condition_dicts.append({
                    "field": cond.field,
                    "operator": cond.operator,
                    "value": cond.value,
                })

        # 如果有维度表字段需要先查找 ID → 条件是针对目标层级（低层级）的，直接在维度表查询
        matched_ids_from_dimension = None
        if dimension_conditions_need_lookup:
            # 所有这些条件都在同一个维度表（目标维度）
            first_field = dimension_conditions_need_lookup[0].field
            dim_index = FIELD_TO_DIM_INDEX[first_field]
            dim_id_field = DIM_ID_FIELD[dim_index]

            # 构建维度表查询条件
            must_clauses = []
            for cond in dimension_conditions_need_lookup:
                field = cond.field
                op = cond.operator
                value = cond.value

                # Try to convert to number if possible for numeric fields
                try:
                    if isinstance(value, str):
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                except (ValueError, TypeError):
                    pass

                if op == "like" or op == "contains":
                    must_clauses.append({"wildcard": {field: f"*{value}*"}})
                elif op == "eq" or op == "=":
                    must_clauses.append({"term": {field: value}})
                elif op == "gt":
                    must_clauses.append({"range": {field: {"gt": value}}})
                elif op == "gte":
                    must_clauses.append({"range": {field: {"gte": value}}})
                elif op == "lt":
                    must_clauses.append({"range": {field: {"lt": value}}})
                elif op == "lte":
                    must_clauses.append({"range": {field: {"lte": value}}})
                elif op == "in" and isinstance(value, list):
                    must_clauses.append({"terms": {field: value}})

            # 如果有广告主过滤，维度表也要加上
            if advertiser_ids:
                must_clauses.append({"terms": {"advertiser_id": [int(aid) for aid in advertiser_ids]}})

            # 如果有上一步的实体 ID（高层级），维度表也要加上（例如：从 advertiser 到 campaign，要保留 advertiser 过滤）
            if previous_entity_ids and previous_entity_level:
                # previous_entity_level 是高层级（例如 advertiser），我们需要在维度表上按高层级 ID 过滤
                previous_level_field = LEVEL_TO_FIELD.get(
                    previous_entity_level,
                    f"{previous_entity_level}_id",
                )
                converted_previous_ids = []
                for eid in previous_entity_ids:
                    try:
                        converted_previous_ids.append(int(eid))
                    except ValueError:
                        converted_previous_ids.append(eid)
                must_clauses.append({"terms": {previous_level_field: converted_previous_ids}})

            # 在维度表搜索
            dsl_dim = {
                "query": {"bool": {"must": must_clauses}},
                "size": 1000,
            }
            response = await self.es_client.search(index=dim_index, body=dsl_dim)

            # 提取匹配到的 ID
            matched_ids = []
            for hit in response["hits"]["hits"]:
                eid = hit["_source"].get(dim_id_field)
                if eid is not None:
                    try:
                        matched_ids.append(int(eid))
                    except (ValueError, TypeError):
                        matched_ids.append(eid)

            matched_ids_from_dimension = matched_ids

            # 如果我们已经从维度表找到了匹配 IDs，并且没有剩下的非维度条件，直接返回这些 IDs
            # 因为目标层级就是低层级，维度表已经给出所有匹配的低层级 ID
            if not condition_dicts:
                return matched_ids_from_dimension

        # 如果还有非维度条件，继续执行传统的两步聚合
        # ====== 第一步: 过滤高层级实体 ======
        dsl_step1 = build_cross_level_down_filter_step1(
            advertiser_ids=advertiser_ids,
            high_level=high_level,
            conditions=condition_dicts,
            index=step.index,
        )

        # 如果有上一步的实体 ID，添加到过滤条件
        if previous_entity_ids and previous_entity_level:
            previous_level_field = LEVEL_TO_FIELD.get(
                previous_entity_level,
                f"{previous_entity_level}_id",
            )
            # 转换实体 ID 为整数如果可能（因为 dimension tables 存储整数 ID）
            converted_previous_ids = []
            for eid in previous_entity_ids:
                try:
                    converted_previous_ids.append(int(eid))
                except ValueError:
                    converted_previous_ids.append(eid)
            dsl_step1["query"]["bool"]["filter"].append(
                {"terms": {previous_level_field: converted_previous_ids}}
            )

        # 执行第一步查询
        index_step1 = dsl_step1.pop("index", step.index)
        response_step1 = await self.es_client.search(index=index_step1, body=dsl_step1)

        # 提取高层级 ID
        high_level_ids = extract_entity_ids(response_step1, f"by_{high_level}")

        if not high_level_ids:
            return []

        # ====== 第二步: 查询低层级实体 ======
        # 构建第二步 DSL: 查询目标层级，用高层级 ID 过滤 + 维度表 IDs 过滤（如果有）
        high_level_field = LEVEL_TO_FIELD.get(high_level, f"{high_level}_id")

        # Convert advertiser_ids to integer if possible (dimension tables store integer IDs)
        converted_advertiser_ids = []
        for aid in advertiser_ids:
            try:
                converted_advertiser_ids.append(int(aid))
            except ValueError:
                converted_advertiser_ids.append(aid)

        # Convert high_level_ids to integer if possible
        converted_high_level_ids = []
        for hid in high_level_ids:
            try:
                converted_high_level_ids.append(int(hid))
            except ValueError:
                converted_high_level_ids.append(hid)

        filters = [
            {"terms": {"advertiser_id": converted_advertiser_ids}},
            {"terms": {high_level_field: converted_high_level_ids}},
        ]

        # 如果我们从维度表找到了匹配 IDs，也加上过滤
        if matched_ids_from_dimension is not None:
            target_level_field = LEVEL_TO_FIELD.get(target_level, f"{target_level}_id")
            filters.append({"terms": {target_level_field: matched_ids_from_dimension}})

        dsl_step2 = {
            "index": get_level_index(target_level),  # 目标层级索引，使用转换后的实际索引名
            "query": {
                "bool": {
                    "filter": filters
                }
            },
            "size": 0,
            "aggs": {
                f"by_{target_level}": {
                    "terms": {"field": LEVEL_TO_FIELD.get(target_level, f"{target_level}_id"), "size": 1000}
                }
            },
        }

        # 执行第二步查询
        index_step2 = dsl_step2.pop("index", target_level)
        response_step2 = await self.es_client.search(index=index_step2, body=dsl_step2)

        # 提取目标层级 ID
        return extract_entity_ids(response_step2, f"by_{target_level}")
