"""Chain-of-Thought Analysis Planner

Core reasoning module that takes a user query and generates a structured analysis plan.
"""

import logging
import json
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import LLM infrastructure
try:
    from src.rag.agents import get_llm
    HAS_LLM = True
except ImportError:
    HAS_LLM = False

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.messages import SystemMessage, HumanMessage
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

from src.analysis.models import (
    AnalysisPlanResult,
    AnalysisPlan,
    FieldContext,
    CotReasoning,
    CotStep,
    AnalysisType,
    FilterType,
    EntityLevel,
    ChartType,
    AnalysisTimeRange,
    AnalysisComparison,
    QualityCheck,
)
from src.analysis.prompts import (
    COT_SYSTEM_PROMPT,
    COT_USER_PROMPT_TEMPLATE,
    build_cot_user_prompt,
    build_field_context_section,
)
from src.analysis.intent_analyzer import IntentAnalyzer, IntentAnalysisResult
from src.analysis.fewshot_retriever import FewshotRetriever, get_fewshot_retriever
from src.nl_dsl.dsl_templates.common import DERIVED_METRICS


class CotResultStatus(str, Enum):
    """Status of CoT planning result"""
    SUCCESS = "success"
    NEEDS_CLARIFICATION = "needs_clarification"
    PARSE_FAILED = "parse_failed"
    VALIDATION_FAILED = "validation_failed"


@dataclass
class ClarificationRequest:
    """Clarification request when information is missing"""
    question: str
    missing_fields: List[str]
    options: Optional[List[Dict[str, str]]] = None


@dataclass
class CotPlanResult:
    """Result from CoT planning"""
    status: CotResultStatus
    plan: Optional[AnalysisPlanResult] = None
    reasoning: Optional[CotReasoning] = None
    clarification: Optional[ClarificationRequest] = None
    raw_response: Optional[str] = None
    retry_count: int = 0


class CotPlanner:
    """Chain-of-Thought Analysis Planner"""

    def __init__(
        self,
        intent_analyzer: Optional[IntentAnalyzer] = None,
        fewshot_retriever: Optional[FewshotRetriever] = None,
        llm: Optional[Any] = None,
        max_retries: int = 2,
    ):
        """
        Initialize the CoT Planner.

        Args:
            intent_analyzer: Intent analyzer for field extraction
            fewshot_retriever: Retriever for few-shot examples
            llm: LLM client (falls back to singleton if not provided)
            max_retries: Maximum number of retries for parse/validation failures
        """
        self.intent_analyzer = intent_analyzer or IntentAnalyzer()
        self.fewshot_retriever = fewshot_retriever or get_fewshot_retriever()
        self.max_retries = max_retries

        # Initialize LLM
        if llm:
            self.llm = llm
        elif HAS_LLM:
            self.llm = get_llm()
        else:
            self.llm = None
            logger.warning("LLM not available, CotPlanner will use mock mode")

    async def plan(
        self,
        user_input: str,
        field_context: Optional[FieldContext] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        advertisers: Optional[List[Dict[str, Any]]] = None,
    ) -> CotPlanResult:
        """
        Generate an analysis plan from user input.

        Args:
            user_input: User's query
            field_context: Pre-validated field context (optional)
            conversation_history: Conversation history for context
            advertisers: Available advertisers (for context)

        Returns:
            CotPlanResult with plan or clarification request
        """
        logger.info(f"Starting CoT planning for query: {user_input[:50]}...")

        # Step 1: Intent analysis to extract initial fields
        intent_result = None
        if field_context is None:
            intent_result = self.intent_analyzer.analyze(
                user_input,
                conversation_history=conversation_history,
            )
            field_context = intent_result.field_context

        # Step 2: Retrieve few-shot examples
        fewshot_examples = self.fewshot_retriever.retrieve(
            user_input,
            analysis_type_hint=intent_result.analysis_type_hint if intent_result else None,
            filter_type_hint=intent_result.filter_type_hint if intent_result else None,
        )

        # Step 3: Build prompt
        base_user_prompt = build_cot_user_prompt(
            user_query=user_input,
            field_context=field_context.model_dump() if field_context else {},
            advertisers=advertisers or [],
            few_shot_examples=[e.model_dump() for e in fewshot_examples],
        )

        # Get today's date for the system prompt
        today_str = date.today().isoformat()
        # 用 replace 而不是 format，避免 prompt 中的 JSON 花括号被解析为格式占位符
        system_prompt = COT_SYSTEM_PROMPT.replace("{today_date}", today_str)

        # Step 4: Call LLM with retry
        retry_count = 0
        last_error = None

        while retry_count <= self.max_retries:
            try:
                # Build prompt with error feedback if this is a retry
                if retry_count > 0 and last_error is not None:
                    # Add error feedback to prompt
                    error_feedback = self._build_error_feedback(last_error)
                    current_user_prompt = base_user_prompt + "\n\n" + error_feedback
                else:
                    current_user_prompt = base_user_prompt

                raw_response = await self._call_llm(system_prompt, current_user_prompt, retry_count > 0)
                logger.debug(f"LLM response received (attempt {retry_count + 1})")

                # Step 5: Parse and validate
                result = self._parse_and_validate(raw_response, field_context)

                if result.status == CotResultStatus.SUCCESS:
                    logger.info("CoT planning successful")
                    result.retry_count = retry_count
                    return result
                elif result.status == CotResultStatus.NEEDS_CLARIFICATION:
                    logger.info("CoT planning needs clarification")
                    result.retry_count = retry_count
                    return result
                elif result.status in [CotResultStatus.PARSE_FAILED, CotResultStatus.VALIDATION_FAILED]:
                    if retry_count < self.max_retries:
                        logger.warning(f"CoT planning {result.status}, retrying...")
                        retry_count += 1
                        last_error = result
                        continue
                    else:
                        logger.error(f"CoT planning failed after {retry_count} retries")
                        result.retry_count = retry_count
                        return result

            except Exception as e:
                logger.exception(f"Error in CoT planning (attempt {retry_count + 1}): {e}")
                if retry_count < self.max_retries:
                    retry_count += 1
                    last_error = e
                else:
                    return CotPlanResult(
                        status=CotResultStatus.PARSE_FAILED,
                        raw_response=str(e),
                        retry_count=retry_count,
                    )

        # Shouldn't reach here, but just in case
        return CotPlanResult(
            status=CotResultStatus.PARSE_FAILED,
            raw_response=str(last_error),
            retry_count=retry_count,
        )

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        is_retry: bool = False,
    ) -> str:
        """
        Call the LLM with the prompts.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            is_retry: Whether this is a retry attempt

        Returns:
            Raw LLM response string
        """
        # If no LLM available, use mock
        if self.llm is None:
            return self._mock_llm_response(system_prompt, user_prompt)

        # Use IntentLLMClient with json_schema mode to enforce strict JSON output
        from src.intent.llm_client import get_intent_llm_client
        from src.analysis.models import AnalysisPlanResult

        client = get_intent_llm_client()
        response = await client.call(  # type: ignore
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=True,
            schema=AnalysisPlanResult,
        )
        return response

    def _parse_and_validate(
        self,
        raw_response: str,
        field_context: Optional[FieldContext],
    ) -> CotPlanResult:
        """
        Parse LLM response and validate the result.

        Args:
            raw_response: Raw LLM response string
            field_context: Field context from intent analysis

        Returns:
            CotPlanResult with parsed data or error
        """
        # Extract JSON from response (handle cases where LLM adds extra text)
        json_str = self._extract_json(raw_response)

        if not json_str:
            logger.warning("Failed to extract JSON from response")
            return CotPlanResult(
                status=CotResultStatus.PARSE_FAILED,
                raw_response=raw_response,
            )

        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode failed: {e}")
            return CotPlanResult(
                status=CotResultStatus.PARSE_FAILED,
                raw_response=raw_response,
            )

        # Check if it's a clarification request
        if "clarification_request" in parsed:
            cr = parsed["clarification_request"]
            return CotPlanResult(
                status=CotResultStatus.NEEDS_CLARIFICATION,
                clarification=ClarificationRequest(
                    question=cr.get("question", ""),
                    missing_fields=cr.get("missing_fields", []),
                    options=cr.get("options"),
                ),
                raw_response=raw_response,
            )

        # Try to parse as AnalysisPlanResult
        try:
            # Parse reasoning if present
            reasoning = None
            if "reasoning" in parsed and isinstance(parsed["reasoning"], str):
                # LLM returned reasoning as plain text, parse it into structured format
                reasoning = self._parse_reasoning(parsed["reasoning"])
                # Replace the string with parsed structured data for pydantic
                parsed["reasoning"] = reasoning.model_dump() if reasoning else None

            # Convert quality_checks if LLM returned strings instead of objects
            if "quality_checks" in parsed:
                qcs = parsed["quality_checks"]
                if isinstance(qcs, list) and len(qcs) > 0 and isinstance(qcs[0], str):
                    # LLM gave list of strings, convert to minimal QualityCheck objects
                    converted = []
                    for i, qc_str in enumerate(qcs):
                        converted.append({
                            "check_type": "max_rows",  # placeholder
                            "threshold": 1000,
                            "action": "warn",
                        })
                    parsed["quality_checks"] = converted

            # Convert quality_checks in analysis_plan if needed
            if ("analysis_plan" in parsed and
                isinstance(parsed["analysis_plan"], dict) and
                "quality_checks" in parsed["analysis_plan"]):
                qcs = parsed["analysis_plan"]["quality_checks"]
                if isinstance(qcs, list) and len(qcs) > 0 and isinstance(qcs[0], str):
                    converted = []
                    for i, qc_str in enumerate(qcs):
                        converted.append({
                            "check_type": "max_rows",
                            "threshold": 1000,
                            "action": "warn",
                        })
                    parsed["analysis_plan"]["quality_checks"] = converted

            # Parse analysis plan result
            # Make sure field_context is set
            if field_context and "field_context" not in parsed:
                parsed["field_context"] = field_context.model_dump()

            plan = AnalysisPlanResult(**parsed)

            # Validate
            validation_errors = self._validate_plan(plan, field_context)
            if validation_errors:
                logger.warning(f"Plan validation failed: {validation_errors}")
                return CotPlanResult(
                    status=CotResultStatus.VALIDATION_FAILED,
                    plan=plan,
                    raw_response=raw_response,
                )

            return CotPlanResult(
                status=CotResultStatus.SUCCESS,
                plan=plan,
                reasoning=reasoning,
                raw_response=raw_response,
            )

        except Exception as e:
            logger.warning(f"Failed to parse AnalysisPlanResult: {e}")
            return CotPlanResult(
                status=CotResultStatus.PARSE_FAILED,
                raw_response=raw_response,
            )

    def _build_error_feedback(self, last_error) -> str:
        """
        Build error feedback prompt for retries.

        Args:
            last_error: The previous error result (CotPlanResult or Exception)

        Returns:
            str: Error feedback text to append to prompt
        """
        if isinstance(last_error, CotPlanResult):
            if last_error.status == CotResultStatus.PARSE_FAILED:
                return (
                    "\n\n⚠️ **ERROR - 请修正后重试**\n"
                    "你的上一次输出解析失败了。\n"
                    "可能原因：JSON格式不正确，缺少必要的双引号，或者有多余的逗号。\n"
                    "请重新检查JSON格式，输出严格正确的JSON格式。"
                )
            elif last_error.status == CotResultStatus.VALIDATION_FAILED:
                # 如果 last_error 有 plan，我们可以检查具体的验证错误
                feedback_lines = [
                    "\n\n⚠️ **ERROR - 请修正后重试**",
                    "你的上一次计划验证失败了，请修正以下错误后重新输出："
                ]
                # Extract validation errors if available
                if last_error.plan:
                    # We can't get the errors directly from last_error, but we can re-validate
                    from src.analysis.models import AnalysisPlanResult
                    # The errors were already collected in _validate_plan
                    # Just add the general specific reminders
                    if (last_error.plan.field_context and
                        last_error.plan.field_context.metrics and
                        last_error.plan.analysis_plan and
                        last_error.plan.analysis_plan.metrics):
                        expected = last_error.plan.field_context.metrics
                        actual = last_error.plan.analysis_plan.metrics
                        if sorted(expected) != sorted(actual):
                            feedback_lines.append(f"- ⚠️ METRICS MISMATCH: field_context specifies metrics = {expected}, but you output metrics = {actual}. THEY MUST BE EXACTLY THE SAME (same count, same names). THIS IS A HARD REQUIREMENT. Fix it NOW.")

                feedback_lines.extend([
                    "- 如果 field_context 中已经指定了 metrics，analysis_plan.metrics 必须与 field_context.metrics 完全一致（数量和名称都必须相同）",
                    "- 所有必填字段都必须填写，不能为 null",
                    "- 受众分布分析必须正确设置 audience_dimension 字段名（如 性别 → audience_gender）",
                    "- group_by 必须使用实体层级名称（如 campaign），不能使用带 _id 后缀的字段名",
                    "\n请修正这些错误，重新输出完整正确的JSON计划。"
                ])
            # 针对筛选计划结构错误的针对性提示
            if last_error.plan and last_error.plan.filter_plan and last_error.plan.filter_plan.steps:
                # 提取验证错误信息
                # 重新验证一次拿到错误列表
                validation_errors = self._validate_plan(last_error.plan, input_field_context=None)
                if any("cannot be the first step" in err for err in validation_errors):
                    feedback_lines.append("- ⚠️ STRUCTURE ERROR: `having_filter` (指标筛选 like '点击量 > 50') **cannot** be the first step. It must be placed **after** all `where_filter`/`cross_level_down` steps, because it needs the entity IDs output from previous dimension filtering. MOVE it to the LAST step.")

                if any("cannot contain both" in err for err in validation_errors):
                    feedback_lines.append("- ⚠️ STRUCTURE ERROR: One step cannot contain both where conditions (`field`: dimension attribute like name/status) AND having conditions (`metric`: aggregated metric like clicks/cost). **SEPARATE them into different steps**: where conditions → with cross_level_down/where_filter; having conditions → separate final step.")

                if any("has no conditions" in err for err in validation_errors):
                    feedback_lines.append("- ⚠️ STRUCTURE ERROR: `having_filter` step cannot be empty. **ONLY add a having_filter step when you need to filter by an aggregated metric condition** (like 'clicks > 50' or 'cvr > 0.03'). If you just need to SORT by a metric (like 'highest cvr first'), you DON'T need a having_filter step. DELETE the empty having_filter step entirely. The sorting is already done in the analysis_plan's order_by field.")

                has_structural_error = (
                    any("cannot be the first step" in err for err in validation_errors) or
                    any("cannot contain both" in err for err in validation_errors) or
                    any("has no conditions" in err for err in validation_errors)
                )
                if has_structural_error:
                    feedback_lines.append("\nPlease fix these structural errors and output the complete correct JSON plan again.")
                return "\n".join(feedback_lines)
            else:
                return (
                    "\n\n⚠️ **ERROR - 请修正后重试**\n"
                    "你的上一次输出验证失败了，请重新检查并修正错误后再次输出。"
                )
        elif isinstance(last_error, Exception):
            return (
                f"\n\n⚠️ **ERROR - 请修正后重试**\n"
                f"上一次执行遇到错误：{str(last_error)}\n"
                "请修正后重新输出。"
            )
        else:
            return (
                "\n\n⚠️ **ERROR - 请修正后重试**\n"
                "上一次输出有错误，请修正后重新输出。"
            )

    def _extract_json(self, text: str) -> Optional[str]:
        """
        Extract JSON from text (handles markdown code blocks and extra text).
        """
        # Try to find JSON in code blocks - more flexible regex that handles:
        # - ```json\n{...}\n``` (standard format)
        # - ```json{...}``` (one line, no newlines)
        # - ```json { ... } ``` (one line with spaces)
        # - ```\n{...}``` (no newline before closing)
        code_block_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if code_block_match:
            return code_block_match.group(1).strip()

        # Try to find JSON from first { to last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace:last_brace + 1]

        return None

    def _parse_reasoning(self, reasoning_text: str) -> CotReasoning:
        """
        Parse reasoning text into CotReasoning structure.
        """
        steps = []

        # Try to extract numbered steps
        step_pattern = re.compile(r"(\d+)[.\)]\s*([^\n]+)")
        matches = step_pattern.findall(reasoning_text)

        for i, (num, content) in enumerate(matches, 1):
            steps.append(CotStep(
                step_id=f"step_{i}",
                step_name=f"步骤 {i}",
                content=content.strip(),
                confidence=0.8,
            ))

        # If no numbered steps found, just create one step with all text
        if not steps:
            steps.append(CotStep(
                step_id="step_1",
                step_name="推理过程",
                content=reasoning_text,
                confidence=0.5,
            ))

        return CotReasoning(
            steps=steps,
            summary=reasoning_text[:200] if len(reasoning_text) > 200 else reasoning_text,
            raw_text=reasoning_text,
        )

    def _validate_plan(self, plan: AnalysisPlanResult, input_field_context: Optional[FieldContext] = None) -> List[str]:
        """
        Validate the analysis plan and auto-add base metrics for derived metrics.

        Args:
            plan: The parsed analysis plan result
            input_field_context: Field context from intent analysis (input to planner),
                this is the authoritative source, not what LLM output in plan.field_context.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required fields
        if not plan.target_level:
            errors.append("target_level is required")

        if not plan.filter_plan:
            errors.append("filter_plan is required")

        if not plan.analysis_plan:
            errors.append("analysis_plan is required")

        if plan.analysis_plan:
            if not plan.analysis_plan.analysis_type:
                errors.append("analysis_type is required")
            if not plan.analysis_plan.chart_type:
                errors.append("chart_type is required")
            if not plan.analysis_plan.metrics:
                errors.append("metrics are required")
            if not plan.analysis_plan.time_range:
                errors.append("time_range is required")

            # For audience_distribution analysis type, audience_dimension is required
            if plan.analysis_plan.analysis_type == "audience_distribution" and not plan.analysis_plan.audience_dimension:
                # Check if audience_dimension is available in input_field_context
                if not (input_field_context and input_field_context.audience_dimension):
                    errors.append("audience_distribution analysis requires audience_dimension (e.g., audience_gender, audience_age, etc.)")

            # Check metrics consistency with field_context
            # Use the input_field_context from intent analysis (authoritative) NOT plan.field_context
            if input_field_context and input_field_context.metrics:
                # field_context 已经指定了 metrics，analysis_plan.metrics 必须完全一致
                expected_metrics = input_field_context.metrics
                actual_metrics = plan.analysis_plan.metrics
                if sorted(expected_metrics) != sorted(actual_metrics):
                    errors.append(
                        f"metrics mismatch: field_context specifies {expected_metrics}, "
                        f"but analysis_plan has {actual_metrics}. "
                        f"They must be exactly the same (same count and same names) per prompt instructions."
                    )

            # Auto-add base metrics for derived metrics in analysis_plan
            # Only do this if field_context doesn't already specify metrics
            # If field_context specifies metrics, we shouldn't add anything - mismatch is an error
            if plan.analysis_plan.metrics and not (input_field_context and input_field_context.metrics):
                metrics_set = set(plan.analysis_plan.metrics)
                for metric in list(metrics_set):  # Iterate over copy
                    if metric in DERIVED_METRICS:
                        base_metrics = DERIVED_METRICS[metric]["depends_on"]
                        for base_metric in base_metrics:
                            if base_metric not in metrics_set:
                                plan.analysis_plan.metrics.append(base_metric)
                                metrics_set.add(base_metric)
                                logger.info(f"Auto-added base metric {base_metric} for derived metric {metric}")

        # Auto-add base metrics for derived metrics in filter_plan (having conditions)
        if plan.filter_plan and plan.filter_plan.steps:
            for step in plan.filter_plan.steps:
                if step.step_type == "having_filter" and step.conditions:
                    for condition in step.conditions:
                        # Condition might be a dict or a FilterCondition model
                        if hasattr(condition, "metric"):
                            metric = condition.metric
                        else:
                            metric = condition.get("metric") if hasattr(condition, "get") else None

                        if metric and metric in DERIVED_METRICS:
                            # Add base metrics to analysis_plan if not already there
                            if plan.analysis_plan and plan.analysis_plan.metrics:
                                metrics_set = set(plan.analysis_plan.metrics)
                                base_metrics = DERIVED_METRICS[metric]["depends_on"]
                                for base_metric in base_metrics:
                                    if base_metric not in metrics_set:
                                        plan.analysis_plan.metrics.append(base_metric)
                                        metrics_set.add(base_metric)
                                        logger.info(f"Auto-added base metric {base_metric} for having condition on {metric}")

        # 验证筛选计划结构规则
        if plan.filter_plan and plan.filter_plan.steps:
            has_having = False
            step_index = 0
            for step in plan.filter_plan.steps:
                step_index += 1
                # Get step_type - handle both dict and FilterCondition object
                if isinstance(step, dict):
                    step_type = step.get("step_type")
                    conditions = step.get("conditions", [])
                else:
                    step_type = step.step_type
                    conditions = step.conditions

                # 规则1: having_filter 不能是第一个步骤
                # having 需要 entity_ids，必须在 where/cross_level_down 之后
                if step_type == "having_filter" and step_index == 1:
                    errors.append("having_filter cannot be the first step. having filter needs entity IDs from previous steps, must come after where/cross_level_down")

                # 规则2: having_filter 必须至少有一个条件
                # having_filter 步骤如果没有 conditions，说明 LLM 添加了多余的空步骤，应该删除
                if step_type == "having_filter" and (not conditions or len(conditions) == 0):
                    errors.append("having_filter step has no conditions. If you don't need to filter by aggregated metrics, do NOT add an empty having_filter step - omit it entirely. Only add having_filter when you have specific metric conditions like 'clicks > 50' or 'cvr > 0.03'.")

                # 规则3: 同一个步骤不能同时包含 where 条件（field）和 having 条件（metric）
                # where 和 having 必须分开到不同步骤
                if conditions and isinstance(conditions, list):
                    has_field_cond = False
                    has_metric_cond = False
                    for cond in conditions:
                        if isinstance(cond, dict):
                            if "field" in cond:
                                has_field_cond = True
                            if "metric" in cond:
                                has_metric_cond = True
                    if has_field_cond and has_metric_cond:
                        errors.append("One step cannot contain both 'field' (where) conditions and 'metric' (having) conditions. where conditions filter dimension attributes and must go with cross_level_down/where_filter; having conditions filter aggregated metrics and must be in a separate final step. They must be separated.")

        # Validate time_range.granularity
        if plan.analysis_plan and plan.analysis_plan.time_range:
            granularity = plan.analysis_plan.time_range.granularity
            if granularity not in {"day", "week", "month"}:
                errors.append(f"Invalid granularity '{granularity}'. time_range.granularity must be one of: 'day', 'week', 'month'. Do not use '1d', '1w', '1M', 'daily', 'weekly'.")

        # Validate audience_distribution steps
        if plan.analysis_plan and plan.analysis_plan.steps:
            for step in plan.analysis_plan.steps:
                if step.analysis_type == "audience_distribution" and not step.audience_type:
                    errors.append("For audience_distribution analysis step, audience_type (audience dimension like 'audience_gender') must be specified. One analysis step can only contain one audience dimension. If you have multiple dimensions, split into multiple steps.")

        return errors

    def _mock_llm_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        Mock LLM response for development/testing.
        """
        # Create a simple mock response based on keywords
        mock_response = {
            "target_level": "campaign",
            "filter_plan": {
                "filter_type": "none",
                "target_level": "campaign",
                "steps": [],
            },
            "analysis_plan": {
                "analysis_type": "time_trend",
                "chart_type": "line",
                "metrics": ["impressions", "clicks", "cost"],
                "time_range": {
                    "start_date": "2026-08-01",
                    "end_date": "2026-08-08",
                    "granularity": "day",
                },
                "compare_time_range": None,
                "time_granularity": "day",
                "audience_dimension": None,
                "group_by": None,
                "order_by": None,
                "order_dir": "desc",
                "limit": 100,
                "quality_checks": [],
            },
            "reasoning": None,
            "field_context": None,
            "quality_checks": [],
        }

        return json.dumps(mock_response, ensure_ascii=False, indent=2)


# Singleton instance
_cot_planner_instance = None


def get_cot_planner() -> CotPlanner:
    """Get the CotPlanner singleton"""
    global _cot_planner_instance
    if _cot_planner_instance is None:
        _cot_planner_instance = CotPlanner()
    return _cot_planner_instance
