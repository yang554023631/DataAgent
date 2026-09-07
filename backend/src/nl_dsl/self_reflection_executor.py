"""自反思执行器

负责执行查询计划，每步：生成 DSL → 校验 → 执行 → 结果检查
失败则反思并重试，最多 max_attempts 次。
"""
import time
import logging
from typing import Dict, Any, List

from src.config.context import truncate_log
from .models import QueryPlan, QueryStep, RetryInfo, NlDslResult
from .result_formatter import ResultFormatter

logger = logging.getLogger(__name__)


class SelfReflectionExecutor:
    """自反思查询执行器"""

    def __init__(
        self,
        es_client=None,
        dsl_generator=None,
        max_attempts: int = 3,
        query_timeout: int = 30,
        max_size: int = 1000,
    ):
        self._es = es_client
        self._generator = dsl_generator
        self.max_attempts = max_attempts
        self.query_timeout = query_timeout
        self.max_size = max_size

    async def execute_plan(
        self,
        plan: QueryPlan,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        display_type_hint: str = "",
    ) -> NlDslResult:
        """执行查询计划

        Args:
            plan: 查询计划
            advertiser_ids: 广告主ID列表
            time_range: 时间范围 {start, end}
            display_type_hint: 呈现类型提示

        Returns:
            NlDslResult
        """
        start_time = time.time()
        step_results: Dict[str, Any] = {}

        for step in plan.steps:
            result = await self._execute_step(
                step=step,
                advertiser_ids=advertiser_ids,
                time_range=time_range,
                prev_results=step_results,
                display_type_hint=display_type_hint,
            )

            if not result.metadata.get("success", True):
                # 某步失败，直接返回失败结果
                logger.error(
                    f"NL→DSL查询失败: 步骤={step.step_id}, "
                    f"错误={result.metadata.get('final_error', 'unknown')}"
                )
                return result

            step_results[step.step_id] = result

        # 取最后一步的结果作为最终结果
        final_step_id = plan.final_output.replace(".output", "")
        final_result = step_results.get(final_step_id)

        # 容错：如果 final_output 匹配不上，就用最后一步的结果
        if not final_result and step_results:
            last_step_id = list(step_results.keys())[-1]
            logger.warning(
                f"final_output({plan.final_output})不匹配步骤ID, "
                f"降级使用最后一步({last_step_id})作为结果"
            )
            final_result = step_results[last_step_id]

        if final_result:
            # 更新总耗时
            final_result.metadata["query_steps"] = len(plan.steps)
            final_result.metadata["total_time_ms"] = int((time.time() - start_time) * 1000)
            logger.info(
                f"NL→DSL查询完成: 总步骤={len(plan.steps)}, "
                f"总耗时={final_result.metadata['total_time_ms']}ms, "
                f"最终行数={final_result.metadata.get('total_rows', 0)}"
            )
            return final_result

        # 没有结果（空计划 或 final_output 不匹配）
        error_msg = f"空查询计划或final_output不匹配: final_output={getattr(plan, 'final_output', 'N/A')}, step_ids={list(step_results.keys())}"
        logger.error(f"NL→DSL查询失败: {error_msg}")
        return NlDslResult(
            display_type="qa",
            columns=[],
            rows=[],
            metadata={"success": False, "final_error": error_msg},
        )

    async def _execute_step(
        self,
        step: QueryStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        prev_results: Dict[str, Any],
        display_type_hint: str = "",
    ) -> NlDslResult:
        """执行单步查询，含反思重试"""
        step_id = step.step_id
        last_error = ""
        last_dsl = None
        total_retries = 0

        for attempt in range(1, self.max_attempts + 1):
            retry_info = None
            if attempt > 1 and last_error:
                retry_info = RetryInfo(
                    attempt=attempt,
                    failure_type=self._classify_failure(last_error),
                    error_message=last_error,
                    previous_dsl=last_dsl,
                )
                logger.info(
                    f"NL→DSL第{attempt-1}次重试(步骤{step_id}): "
                    f"失败类型={retry_info.failure_type}"
                )

            # 1. 生成 DSL
            dsl, validation_result = await self._generator.generate_step(
                step=step,
                advertiser_ids=advertiser_ids,
                time_range=time_range,
                prev_results=prev_results,
                retry_info=retry_info,
            )
            last_dsl = dsl

            # 2. 校验
            if not validation_result.ok:
                last_error = "校验失败: " + "; ".join(validation_result.errors)
                logger.info(f"NL→DSL安全校验失败(步骤{step_id}): {last_error}")
                total_retries = attempt - 1
                continue

            # 3. 执行
            try:
                es_response = self._execute_search(dsl, step.index)
            except Exception as e:
                last_error = f"执行失败: {str(e)}"
                logger.exception(f"NL→DSL执行失败(步骤{step_id}): {truncate_log(str(e), 200)}")
                total_retries = attempt - 1
                continue

            # 4. 结果检查
            check_result = self._check_result(es_response, step)
            if not check_result["ok"]:
                last_error = f"结果异常: {check_result['reason']}"
                logger.info(f"NL→DSL结果检查(步骤{step_id}): {last_error}")
                # 空结果特殊处理：第一次自查后重试，第二次就返回
                if check_result.get("is_empty") and attempt >= 2:
                    # 空结果且已经重试过了，返回空结果（不算失败）
                    formatted = ResultFormatter.format(es_response, display_type_hint)
                    result = NlDslResult(**formatted)
                    result.metadata["retries"] = attempt - 1
                    result.metadata["is_empty_result"] = True
                    result.metadata["empty_reason"] = check_result["reason"]
                    result.metadata["success"] = True
                    result.metadata["step_id"] = step_id
                    return result
                total_retries = attempt - 1
                continue

            # 5. 成功，格式化结果
            formatted = ResultFormatter.format(es_response, display_type_hint)
            result = NlDslResult(**formatted)
            result.metadata["retries"] = attempt - 1
            result.metadata["success"] = True
            result.metadata["step_id"] = step_id
            # 保存 query_context（用于翻页和列名映射）
            # 只要有数据行就保存，不限制 display_type
            if result.rows:
                result.query_context = {
                    "index": step.index,
                    "base_dsl": dsl,
                    "total": result.metadata.get("total_rows", 0),
                }
            return result

        # 所有尝试都失败
        logger.error(f"NL→DSL最终失败(步骤{step_id}): 重试{total_retries}次, 最终错误={last_error}")
        return NlDslResult(
            display_type="qa",
            columns=["错误信息"],
            rows=[[last_error]],
            metadata={
                "success": False,
                "retries": total_retries,
                "final_error": last_error,
                "failure_type": self._classify_failure(last_error),
            },
        )

    def _execute_search(self, dsl: dict, index_name: str) -> dict:
        """执行 ES 查询"""
        if self._es is None:
            raise RuntimeError("ES 客户端未初始化")

        # size 截断（与 DslValidator.max_size 保持一致）
        size = dsl.get("size", 10)
        if isinstance(size, int) and size > self.max_size:
            dsl = dict(dsl)
            dsl["size"] = self.max_size

        response = self._es.search(
            index=index_name,
            body=dsl,
            request_timeout=self.query_timeout,
        )
        return response

    @staticmethod
    def _check_result(es_response: dict, step: QueryStep) -> dict:
        """检查查询结果是否合理

        Returns:
            {"ok": bool, "reason": str, "is_empty": bool}
        """
        # 检查空结果
        hits = es_response.get("hits", {})
        total = hits.get("total", 0)
        if isinstance(total, dict):
            total = total.get("value", 0)

        aggs = es_response.get("aggregations", {})
        has_aggs = bool(aggs)

        if total == 0 and not has_aggs:
            return {"ok": False, "reason": "查询结果为空（0条命中且无聚合结果）", "is_empty": True}

        # 检查聚合结果是否也为空
        if has_aggs and total == 0:
            # 检查第一个聚合的 buckets
            agg_keys = list(aggs.keys())
            if not agg_keys:
                return {"ok": False, "reason": "聚合结果为空（0个bucket）", "is_empty": True}
            first_agg_key = agg_keys[0]
            first_agg = aggs[first_agg_key]
            if isinstance(first_agg, dict) and "buckets" in first_agg:
                if len(first_agg["buckets"]) == 0:
                    return {"ok": False, "reason": "聚合结果为空（0个bucket）", "is_empty": True}

        # TODO: 数值异常检查（数量级不合理等）
        # 暂时只做空结果检查

        return {"ok": True, "reason": ""}

    @staticmethod
    def _classify_failure(error_msg: str) -> str:
        """将错误信息分类为失败类型"""
        error_msg = error_msg.lower()
        if "校验失败" in error_msg or "validation" in error_msg:
            return "validation"
        if "执行失败" in error_msg or "exception" in error_msg or "error" in error_msg:
            return "execution"
        if "空" in error_msg or "empty" in error_msg:
            return "empty"
        if "异常" in error_msg or "abnormal" in error_msg:
            return "abnormal"
        return "unknown"


_executor_instance = None


def get_self_reflection_executor() -> SelfReflectionExecutor:
    """获取 SelfReflectionExecutor 单例"""
    global _executor_instance
    if _executor_instance is None:
        from src.tools.custom_report_client import custom_report_client
        from .dsl_generator import get_dsl_generator

        generator = get_dsl_generator()

        _executor_instance = SelfReflectionExecutor(
            es_client=custom_report_client.es_client,
            dsl_generator=generator,
        )
    return _executor_instance