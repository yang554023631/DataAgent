"""NL→DSL 生成器

包含查询规划器和 DSL 生成器两部分。
查询规划：将用户问题拆解为多步查询计划。
DSL 生成：为每个步骤生成具体的 ES DSL。
"""
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from pydantic import ValidationError

from src.config.context import truncate_log
from .models import QueryPlan, QueryStep, RetryInfo
from .dsl_validator import ValidationResult
from .prompts import (
    QUERY_PLANNING_SYSTEM_PROMPT,
    QUERY_PLANNING_USER_PROMPT,
    DSL_GENERATION_SYSTEM_PROMPT,
    DSL_GENERATION_USER_PROMPT,
    REFLECTION_SYSTEM_PROMPT,
    REFLECTION_USER_PROMPT,
)

logger = logging.getLogger(__name__)


class DslGenerator:
    """NL→DSL 生成器

    职责：
    1. 规划查询步骤
    2. 为每步生成 ES DSL
    3. 校验 DSL 安全性
    4. 失败时生成反思修正版 DSL
    """

    def __init__(
        self,
        llm_client=None,
        schema_retriever=None,
        validator=None,
        max_steps: int = 5,
    ):
        self._llm = llm_client
        self._schema_retriever = schema_retriever
        self._validator = validator
        self.max_steps = max_steps

    async def plan_query(
        self,
        user_input: str,
        constraints: Dict[str, Any],
    ) -> QueryPlan:
        """生成查询计划

        Args:
            user_input: 用户原始问题
            constraints: 已提取的约束 {advertiser_ids, time_range, metrics, analysis_type}

        Returns:
            QueryPlan
        """
        logger.info(f"NL→DSL查询规划开始: 用户问题='{truncate_log(user_input, 100)}'")

        if not self._llm:
            raise ValueError("llm_client is required")

        # 1. 检索相关 schema
        schema_context = self._get_schema_context(user_input + " " + " ".join(constraints.get("metrics") or []))

        # 2. 调用 LLM 生成计划
        user_prompt = QUERY_PLANNING_USER_PROMPT.format(
            user_input=user_input,
            advertiser_ids=constraints.get("advertiser_ids", []),
            time_range=constraints.get("time_range", {}),
            metrics=constraints.get("metrics", []),
            analysis_type=constraints.get("analysis_type", ""),
            schema_context=schema_context[:2000],
        )

        response = await self._llm.call(
            system_prompt=QUERY_PLANNING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_mode=True,
        )

        try:
            plan_data = json.loads(response)
            plan = QueryPlan(**plan_data)
        except (json.JSONDecodeError, ValidationError):
            logger.exception("查询规划解析失败")
            # 降级：返回单步计划
            plan_data = {
                "steps": [{
                    "step_id": "step_1",
                    "description": user_input[:50],
                    "index": "ad_stat_data",
                    "output_fields": [],
                    "purpose": "单步查询",
                }],
                "final_output": "step_1.output",
            }
            plan = QueryPlan(**plan_data)

        logger.info(
            f"NL→DSL查询规划完成: 步骤数={len(plan.steps)}, "
            f"步骤=[{', '.join(s.description[:20] for s in plan.steps)}]"
        )
        return plan

    async def generate_step(
        self,
        step: QueryStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        prev_results: Optional[Dict[str, Any]] = None,
        retry_info: Optional[RetryInfo] = None,
    ) -> Tuple[Dict[str, Any], Any]:
        """生成单步的 ES DSL

        Args:
            step: 查询步骤
            advertiser_ids: 广告主ID列表
            time_range: 时间范围 {start, end}
            prev_results: 上一步结果
            retry_info: 重试信息（首次为 None）

        Returns:
            (dsl_dict, validation_result)
        """
        step_id = step.step_id
        logger.info(f"NL→DSL生成(步骤{step_id}): 索引={step.index}")

        if not self._llm:
            raise ValueError("llm_client is required")

        # 1. 检索该索引的 schema
        schema_context = self._get_schema_context_for_index(step.index, step.description)

        # 2. 构建输入参数字符串
        input_params = self._build_input_params(step, advertiser_ids, time_range, prev_results)

        if retry_info and retry_info.attempt > 1:
            # 重试模式：用反思 prompt
            dsl = await self._generate_with_reflection(
                step, schema_context, input_params, retry_info
            )
        else:
            # 首次生成
            user_prompt = DSL_GENERATION_USER_PROMPT.format(
                step_description=step.description,
                input_params=input_params,
                schema_context=schema_context[:2000],
                index_name=step.index,
                advertiser_ids=advertiser_ids,
                time_range=time_range,
            )
            response = await self._llm.call(
                system_prompt=DSL_GENERATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                json_mode=True,
            )
            try:
                dsl = json.loads(response)
            except json.JSONDecodeError:
                logger.exception(f"DSL生成解析失败(步骤{step_id})")
                dsl = {}

        logger.info(f"NL→DSL生成(步骤{step_id}): DSL={truncate_log(json.dumps(dsl, ensure_ascii=False), 500)}")

        # 3. 安全校验
        if self._validator:
            validation_result = self._validator.validate(dsl, step.index)
        else:
            validation_result = ValidationResult()
            validation_result.ok = True

        return dsl, validation_result

    async def _generate_with_reflection(
        self,
        step: QueryStep,
        schema_context: str,
        input_params: str,
        retry_info: RetryInfo,
    ) -> Dict[str, Any]:
        """通过反思生成修正后的 DSL"""
        user_prompt = REFLECTION_USER_PROMPT.format(
            previous_dsl=json.dumps(retry_info.previous_dsl or {}, ensure_ascii=False, indent=2),
            failure_type=retry_info.failure_type,
            error_message=retry_info.error_message,
            schema_context=schema_context[:2000],
        )
        response = await self._llm.call(
            system_prompt=REFLECTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_mode=True,
        )
        try:
            data = json.loads(response)
            fixed_dsl = data.get("fixed_dsl", {})
            reflection = data.get("reflection", "")
            logger.info(f"NL→DSL反思(步骤{step.step_id}): {truncate_log(reflection, 200)}")
            return fixed_dsl
        except (json.JSONDecodeError, KeyError):
            logger.exception(f"反思DSL解析失败(步骤{step.step_id})")
            return retry_info.previous_dsl or {}

    def _get_schema_context(self, query: str) -> str:
        """获取 schema 上下文文本"""
        if not self._schema_retriever:
            return ""
        try:
            results = self._schema_retriever.search(query)
            return "\n\n".join(r.content for r in results)
        except Exception:
            logger.exception("Schema检索失败")
            return ""

    def _get_schema_context_for_index(self, index_name: str, description: str) -> str:
        """获取指定索引的 schema 上下文"""
        if not self._schema_retriever:
            return ""
        try:
            results = self._schema_retriever.search_by_index(description, index_name)
            return "\n\n".join(r.content for r in results)
        except Exception:
            logger.exception(f"Schema检索失败(索引{index_name})")
            return ""

    @staticmethod
    def _build_input_params(
        step: QueryStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        prev_results: Optional[Dict[str, Any]],
    ) -> str:
        """构建输入参数字符串"""
        lines = [f"- 广告主ID: {advertiser_ids}"]
        if time_range:
            lines.append(f"- 时间范围: {time_range.get('start', '')} ~ {time_range.get('end', '')}")
        if step.output_fields:
            lines.append(f"- 需要输出字段: {step.output_fields}")
        if prev_results:
            lines.append(f"- 上一步结果: {json.dumps(prev_results, ensure_ascii=False)[:500]}")
        return "\n".join(lines)


_dsl_generator_instance = None


def get_dsl_generator() -> DslGenerator:
    """获取 DslGenerator 单例"""
    global _dsl_generator_instance
    if _dsl_generator_instance is None:
        from src.intent.llm_client import get_intent_llm_client
        from .dsl_validator import DslValidator
        from src.schema_rag.retriever import get_schema_retriever

        llm_client = get_intent_llm_client()
        schema_retriever = get_schema_retriever()
        # 默认白名单索引
        allowed_indices = {"ad_stat_data", "ad_stat_audience", "advertiser", "adgroup"}
        validator = DslValidator(allowed_indices=allowed_indices)

        _dsl_generator_instance = DslGenerator(
            llm_client=llm_client,
            schema_retriever=schema_retriever,
            validator=validator,
        )
    return _dsl_generator_instance
