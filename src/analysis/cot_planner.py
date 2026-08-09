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
    from backend.src.rag.agents import get_llm
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
        max_retries: int = 1,
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

    def plan(
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
        user_prompt = build_cot_user_prompt(
            user_query=user_input,
            field_context=field_context.model_dump() if field_context else {},
            advertisers=advertisers or [],
            few_shot_examples=[e.model_dump() for e in fewshot_examples],
        )

        # Get today's date for the system prompt
        today_str = date.today().isoformat()
        system_prompt = COT_SYSTEM_PROMPT.format(today_date=today_str)

        # Step 4: Call LLM with retry
        retry_count = 0
        last_error = None

        while retry_count <= self.max_retries:
            try:
                raw_response = self._call_llm(system_prompt, user_prompt, retry_count > 0)
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

    def _call_llm(
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

        # Build prompt template and invoke
        if HAS_LANGCHAIN:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", user_prompt),
            ])

            chain = prompt | self.llm
            response = chain.invoke({})
            return response.content.strip()
        else:
            # Fallback to direct invocation if needed
            raise NotImplementedError("LLM invocation requires LangChain")

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
                reasoning = self._parse_reasoning(parsed["reasoning"])

            # Parse analysis plan result
            # Make sure field_context is set
            if field_context and "field_context" not in parsed:
                parsed["field_context"] = field_context.model_dump()

            plan = AnalysisPlanResult(**parsed)

            # Validate
            validation_errors = self._validate_plan(plan)
            if validation_errors:
                logger.warning(f"Plan validation failed: {validation_errors}")
                return CotPlanResult(
                    status=CotResultStatus.VALIDATION_FAILED,
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

    def _extract_json(self, text: str) -> Optional[str]:
        """
        Extract JSON from text (handles markdown code blocks and extra text).
        """
        # Try to find JSON in code blocks
        code_block_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
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

    def _validate_plan(self, plan: AnalysisPlanResult) -> List[str]:
        """
        Validate the analysis plan.

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
