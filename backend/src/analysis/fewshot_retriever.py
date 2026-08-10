"""Few-shot Example Retriever for CoT Analysis Planner

Retrieves relevant few-shot examples from pgvector with rule-based reranking.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# Import RAG infrastructure - these should be available in backend/src
try:
    from src.rag.retriever import VectorRetriever, RetrievalResult
    from src.rag.database import get_db_session
    from src.rag.embedding import get_embedding_provider
    HAS_RAG = True
except ImportError:
    # Fall back to mock if not available in this path
    logger.warning("RAG infrastructure not available, using mock retrieval")
    HAS_RAG = False

from src.analysis.models import CotExample, AnalysisType, FilterType


@dataclass
class RetrievedExample:
    """A retrieved few-shot example with metadata"""
    example: CotExample
    score: float
    retrieval_rank: int


class FewshotRetriever:
    """Few-shot Example Retriever with rule-based reranking"""

    def __init__(
        self,
        retrieve_top_k: int = 6,
        final_positive_count: int = 3,
        final_negative_count: int = 1,
    ):
        """
        Initialize the retriever.

        Args:
            retrieve_top_k: Number of examples to retrieve from vector store before reranking
            final_positive_count: Number of positive examples to keep after reranking
            final_negative_count: Number of negative examples to keep after reranking
        """
        self.retrieve_top_k = retrieve_top_k
        self.final_positive_count = final_positive_count
        self.final_negative_count = final_negative_count

        if HAS_RAG:
            self.vector_retriever = VectorRetriever(top_k=retrieve_top_k)

    def retrieve(
        self,
        query: str,
        analysis_type_hint: Optional[AnalysisType] = None,
        filter_type_hint: Optional[FilterType] = None,
    ) -> List[CotExample]:
        """
        Retrieve and rerank few-shot examples.

        Args:
            query: User's query
            analysis_type_hint: Optional hint about the analysis type from intent analysis
            filter_type_hint: Optional hint about the filter type from intent analysis

        Returns:
            List of reranked examples (positive first, then negative)
        """
        logger.info(f"Retrieving few-shot examples for query: {query[:50]}...")

        # Step 1: Vector retrieval from pgvector
        raw_results = self._vector_retrieve(query)

        # Step 2: Parse retrieved results into CotExample objects
        parsed_examples = self._parse_retrieval_results(raw_results)

        # Step 3: Rule-based reranking
        reranked = self._rule_rerank(
            parsed_examples,
            analysis_type_hint,
            filter_type_hint,
        )

        # Step 4: Split into positive and negative, take top N of each
        positives = [e for e in reranked if e.example.category == "positive"]
        negatives = [e for e in reranked if e.example.category == "negative"]

        final_positives = positives[:self.final_positive_count]
        final_negatives = negatives[:self.final_negative_count]

        logger.info(
            f"Retrieved {len(final_positives)} positive, {len(final_negatives)} negative examples "
            f"(from {len(parsed_examples)} candidates)"
        )

        # Return positive examples first, then negative
        return [e.example for e in final_positives + final_negatives]

    def _vector_retrieve(self, query: str) -> List[Any]:
        """
        Retrieve examples from vector store.
        """
        if not HAS_RAG:
            # Mock retrieval for development without RAG infrastructure
            return self._mock_retrieve(query)

        try:
            db_session = get_db_session()
            try:
                results = self.vector_retriever.retrieve(
                    query,
                    db_session,
                    doc_type="cot_example",
                )
                return results
            finally:
                db_session.close()
        except Exception as e:
            logger.exception(f"Vector retrieval failed: {e}")
            return self._mock_retrieve(query)

    def _parse_retrieval_results(self, results: List[Any]) -> List[RetrievedExample]:
        """
        Parse retrieval results into CotExample objects.
        """
        parsed = []

        for i, result in enumerate(results):
            try:
                # Extract score
                score = result.score if hasattr(result, 'score') else 0.0

                # Parse content to extract the example
                content = result.content if hasattr(result, 'content') else str(result)
                example = self._parse_example_from_content(content)

                if example:
                    parsed.append(RetrievedExample(
                        example=example,
                        score=score,
                        retrieval_rank=i,
                    ))
            except Exception as e:
                logger.debug(f"Failed to parse result {i}: {e}")

        return parsed

    def _parse_example_from_content(self, content: str) -> Optional[CotExample]:
        """
        Parse a CotExample from the stored content string.
        """
        import json

        # Extract example_id from content
        example_id_match = re.search(r"example_id:\s*(\S+)", content)
        example_id = example_id_match.group(1) if example_id_match else "unknown"

        # Extract question
        question_match = re.search(r"## 问题 \(Question\)\s*\n(.+?)\s*\n##", content, re.DOTALL)
        question = question_match.group(1).strip() if question_match else ""

        # Extract category
        category_match = re.search(r"category:\s*(\S+)", content)
        category = category_match.group(1) if category_match else "positive"

        # Extract analysis_type
        analysis_type_match = re.search(r"analysis_type:\s*(\S+)", content)
        analysis_type_str = analysis_type_match.group(1) if analysis_type_match else None
        analysis_type = None
        if analysis_type_str and analysis_type_str.strip() and analysis_type_str != "-":
            try:
                analysis_type = AnalysisType(analysis_type_str)
            except ValueError:
                pass

        # Extract filter_type
        filter_type_match = re.search(r"filter_type:\s*(\S+)", content)
        filter_type_str = filter_type_match.group(1) if filter_type_match else None
        filter_type = None
        if filter_type_str and filter_type_str.strip() and filter_type_str != "-":
            try:
                filter_type = FilterType(filter_type_str)
            except ValueError:
                pass

        # Extract reasoning_chinese
        reasoning_match = re.search(r"## 推理过程 \(Reasoning\)\s*\n(.+?)\s*\n##", content, re.DOTALL)
        reasoning_chinese = reasoning_match.group(1).strip() if reasoning_match else ""

        # Extract plan JSON
        plan_match = re.search(r"## 生成计划 \(Plan\)\s*\n```json\s*\n(.+?)\s*\n```", content, re.DOTALL)
        plan = {}
        if plan_match:
            try:
                plan = json.loads(plan_match.group(1))
            except json.JSONDecodeError:
                pass

        # Extract notes
        notes_match = re.search(r"## 备注 \(Notes\)\s*\n(.+)", content, re.DOTALL)
        notes = notes_match.group(1).strip() if notes_match else None

        return CotExample(
            example_id=example_id,
            question=question,
            category=category,
            analysis_type=analysis_type,
            filter_type=filter_type,
            reasoning_chinese=reasoning_chinese,
            plan=plan,
            notes=notes,
        )

    def _rule_rerank(
        self,
        examples: List[RetrievedExample],
        analysis_type_hint: Optional[AnalysisType],
        filter_type_hint: Optional[FilterType],
    ) -> List[RetrievedExample]:
        """
        Apply rule-based reranking to the retrieved examples.

        Reranking rules (higher score = better):
        1. +3.0 points: Same analysis_type as hint
        2. +2.0 points: Same filter_type as hint
        3. +1.0 point: Cross-level match (if query involves cross-level)
        4. Keep original vector score (0.0-1.0) as base

        Returns:
            Reranked list sorted by combined score descending
        """
        scored = []

        for ret_example in examples:
            example = ret_example.example
            score = ret_example.score  # Base score from vector retrieval (0.0-1.0)

            # Rule 1: Same analysis_type
            if analysis_type_hint and example.analysis_type == analysis_type_hint:
                score += 3.0

            # Rule 2: Same filter_type
            if filter_type_hint and example.filter_type == filter_type_hint:
                score += 2.0

            # Rule 3: Cross-level match
            if (filter_type_hint == FilterType.CROSS_LEVEL and
                example.filter_type == FilterType.CROSS_LEVEL):
                score += 1.0

            scored.append((score, ret_example))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return in order with updated scores (for logging)
        for score, ret_example in scored:
            ret_example.score = score

        return [ret_example for _, ret_example in scored]

    def _mock_retrieve(self, query: str) -> List[Any]:
        """
        Mock retrieval for development without RAG infrastructure.
        Loads examples directly from YAML and does simple keyword matching.
        """
        import yaml
        from pathlib import Path

        examples_path = Path(__file__).parent / "examples" / "cot_examples.yaml"

        if not examples_path.exists():
            logger.warning("Examples YAML not found, returning empty list")
            return []

        with open(examples_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        all_examples = data.get("examples", [])

        # Simple keyword-based filtering
        query_lower = query.lower()
        scored = []

        for example in all_examples:
            score = 0.1  # Base score
            question = example.get("question", "").lower()

            # Check for keyword matches
            if any(kw in query_lower for kw in ["趋势", "trend", "时间"]):
                if example.get("analysis_type") == "time_trend":
                    score += 0.5
            if any(kw in query_lower for kw in ["对比", "comparison"]):
                if example.get("analysis_type") == "period_comparison":
                    score += 0.5
            if any(kw in query_lower for kw in ["分布", "distribution"]):
                if example.get("analysis_type") == "audience_distribution":
                    score += 0.5
            if any(kw in query_lower for kw in ["列表", "排名", "top"]):
                if example.get("analysis_type") == "entity_table":
                    score += 0.5

            # Check for same keywords in question
            common = set(query_lower.split()) & set(question.split())
            score += 0.1 * len(common)

            # Create mock retrieval result
            mock_result = type('MockResult', (), {
                'content': self._example_to_mock_content(example),
                'score': score,
                'id': example.get("example_id"),
            })()
            scored.append((-score, mock_result))  # Negative for ascending sort

        # Sort just by the score key
        scored.sort(key=lambda x: x[0])
        return [r for _, r in scored[:self.retrieve_top_k]]

    def _example_to_mock_content(self, example: dict) -> str:
        """Convert an example dict to mock content string for parsing"""
        import json

        lines = [f"# CoT Example: {example.get('example_id')}", ""]
        lines.append(f"## 问题 (Question)")
        lines.append(example.get("question", ""))
        lines.append("")
        lines.append(f"## 元数据 (Metadata)")
        lines.append(f"- example_id: {example.get('example_id')}")
        lines.append(f"- category: {example.get('category')}")
        lines.append(f"- analysis_type: {example.get('analysis_type', '')}")
        lines.append(f"- filter_type: {example.get('filter_type', '')}")
        lines.append("")
        lines.append(f"## 推理过程 (Reasoning)")
        lines.append(example.get("reasoning_chinese", ""))
        lines.append("")
        lines.append(f"## 生成计划 (Plan)")
        lines.append("```json")
        lines.append(json.dumps(example.get("plan", {}), ensure_ascii=False, indent=2))
        lines.append("```")

        if "notes" in example:
            lines.append("")
            lines.append(f"## 备注 (Notes)")
            lines.append(example.get("notes", ""))

        return "\n".join(lines)


# Singleton instance
_fewshot_retriever_instance = None


def get_fewshot_retriever() -> FewshotRetriever:
    """Get the FewshotRetriever singleton"""
    global _fewshot_retriever_instance
    if _fewshot_retriever_instance is None:
        _fewshot_retriever_instance = FewshotRetriever()
    return _fewshot_retriever_instance
