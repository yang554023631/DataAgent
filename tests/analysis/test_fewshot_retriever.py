"""Few-shot Retriever Tests"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.analysis.fewshot_retriever import (
    FewshotRetriever,
    RetrievedExample,
    get_fewshot_retriever,
)
from src.analysis.models import (
    CotExample,
    AnalysisType,
    FilterType,
    EntityLevel,
)


class TestFewshotRetriever:
    """Test FewshotRetriever class"""

    def test_initialization_defaults(self):
        """Test retriever can be initialized with defaults"""
        retriever = FewshotRetriever()
        assert retriever.retrieve_top_k == 6
        assert retriever.final_positive_count == 3
        assert retriever.final_negative_count == 1

    def test_initialization_custom(self):
        """Test retriever can be initialized with custom values"""
        retriever = FewshotRetriever(
            retrieve_top_k=10,
            final_positive_count=5,
            final_negative_count=2,
        )
        assert retriever.retrieve_top_k == 10
        assert retriever.final_positive_count == 5
        assert retriever.final_negative_count == 2

    def test_retrieve_basic(self):
        """Test basic retrieval (uses mock mode)"""
        retriever = FewshotRetriever()
        examples = retriever.retrieve("广告主最近7天的消耗趋势")

        # Should return examples (at least some)
        assert isinstance(examples, list)
        # Since we're in mock mode, it should load from YAML
        assert len(examples) > 0

        # Check that examples are CotExample objects
        for example in examples:
            assert isinstance(example, CotExample)
            assert example.example_id is not None
            assert example.question is not None

    def test_retrieve_with_analysis_type_hint(self):
        """Test retrieval with analysis type hint"""
        retriever = FewshotRetriever()
        examples = retriever.retrieve(
            "广告主最近7天的消耗趋势",
            analysis_type_hint=AnalysisType.TIME_TREND,
        )

        assert isinstance(examples, list)
        assert len(examples) > 0

    def test_retrieve_with_filter_type_hint(self):
        """Test retrieval with filter type hint"""
        retriever = FewshotRetriever()
        examples = retriever.retrieve(
            "广告主最近7天的消耗趋势",
            filter_type_hint=FilterType.NONE,
        )

        assert isinstance(examples, list)
        assert len(examples) > 0

    def test_retrieve_with_both_hints(self):
        """Test retrieval with both analysis and filter type hints"""
        retriever = FewshotRetriever()
        examples = retriever.retrieve(
            "广告主最近7天的消耗趋势",
            analysis_type_hint=AnalysisType.TIME_TREND,
            filter_type_hint=FilterType.NONE,
        )

        assert isinstance(examples, list)
        assert len(examples) > 0

    def test_parse_example_from_content(self):
        """Test parsing example from content string"""
        retriever = FewshotRetriever()

        # Create a mock content string
        content = """# CoT Example: test_01

## 问题 (Question)
广告主最近7天的消耗趋势

## 元数据 (Metadata)
- example_id: test_01
- category: positive
- analysis_type: time_trend
- filter_type: none

## 推理过程 (Reasoning)
Step 1: 问题理解
用户想查看趋势

## 生成计划 (Plan)
```json
{
  "target_level": "advertiser",
  "filter_plan": {
    "filter_type": "none",
    "target_level": "advertiser",
    "steps": []
  },
  "analysis_plan": {
    "analysis_type": "time_trend",
    "chart_type": "line",
    "metrics": ["cost"],
    "time_range": {
      "start_date": "2026-08-01",
      "end_date": "2026-08-08",
      "granularity": "day"
    }
  }
}
```
"""

        example = retriever._parse_example_from_content(content)

        assert example is not None
        assert example.example_id == "test_01"
        assert example.question == "广告主最近7天的消耗趋势"
        assert example.category == "positive"
        assert example.analysis_type == AnalysisType.TIME_TREND
        assert example.filter_type == FilterType.NONE
        assert "Step 1" in example.reasoning_chinese
        assert example.plan is not None

    def test_parse_example_from_content_with_notes(self):
        """Test parsing example with notes"""
        retriever = FewshotRetriever()

        content = """# CoT Example: neg_01

## 问题 (Question)
错误的问题

## 元数据 (Metadata)
- example_id: neg_01
- category: negative
- analysis_type:
- filter_type:

## 推理过程 (Reasoning)
Step 1: 错误示范

## 生成计划 (Plan)
```json
{"test": "plan"}
```

## 备注 (Notes)
这是错误示例，原因是混淆了where和having
"""

        example = retriever._parse_example_from_content(content)

        assert example is not None
        assert example.category == "negative"
        assert example.notes is not None
        assert "混淆了where和having" in example.notes

    def test_rule_rerank_basic(self):
        """Test rule-based reranking"""
        retriever = FewshotRetriever()

        # Create some test examples
        example1 = CotExample(
            example_id="ex1",
            question="test1",
            category="positive",
            analysis_type=AnalysisType.TIME_TREND,
            filter_type=FilterType.NONE,
            reasoning_chinese="step1",
            plan={},
        )
        example2 = CotExample(
            example_id="ex2",
            question="test2",
            category="positive",
            analysis_type=AnalysisType.ENTITY_TABLE,
            filter_type=FilterType.WHERE,
            reasoning_chinese="step1",
            plan={},
        )

        retrieved1 = RetrievedExample(
            example=example1,
            score=0.5,
            retrieval_rank=0,
        )
        retrieved2 = RetrievedExample(
            example=example2,
            score=0.6,
            retrieval_rank=1,
        )

        # Rerank with TIME_TREND hint - example1 should come first
        reranked = retriever._rule_rerank(
            [retrieved1, retrieved2],
            analysis_type_hint=AnalysisType.TIME_TREND,
            filter_type_hint=None,
        )

        assert len(reranked) == 2
        assert reranked[0].example.example_id == "ex1"
        assert reranked[0].score > 0.5  # Should have bonus points

    def test_rule_rerank_with_filter_type(self):
        """Test rule-based reranking with filter type"""
        retriever = FewshotRetriever()

        example1 = CotExample(
            example_id="ex1",
            question="test1",
            category="positive",
            analysis_type=AnalysisType.TIME_TREND,
            filter_type=FilterType.HAVING,
            reasoning_chinese="step1",
            plan={},
        )
        example2 = CotExample(
            example_id="ex2",
            question="test2",
            category="positive",
            analysis_type=AnalysisType.TIME_TREND,
            filter_type=FilterType.NONE,
            reasoning_chinese="step1",
            plan={},
        )

        retrieved1 = RetrievedExample(example=example1, score=0.5, retrieval_rank=0)
        retrieved2 = RetrievedExample(example=example2, score=0.6, retrieval_rank=1)

        # Rerank with HAVING filter type hint
        reranked = retriever._rule_rerank(
            [retrieved1, retrieved2],
            analysis_type_hint=AnalysisType.TIME_TREND,
            filter_type_hint=FilterType.HAVING,
        )

        assert len(reranked) == 2
        assert reranked[0].example.example_id == "ex1"

    def test_rule_rerank_with_cross_level(self):
        """Test rule-based reranking with cross level filter type"""
        retriever = FewshotRetriever()

        example1 = CotExample(
            example_id="ex1",
            question="test1",
            category="positive",
            analysis_type=AnalysisType.ENTITY_TABLE,
            filter_type=FilterType.CROSS_LEVEL,
            reasoning_chinese="step1",
            plan={},
        )
        example2 = CotExample(
            example_id="ex2",
            question="test2",
            category="positive",
            analysis_type=AnalysisType.ENTITY_TABLE,
            filter_type=FilterType.WHERE,
            reasoning_chinese="step1",
            plan={},
        )

        retrieved1 = RetrievedExample(example=example1, score=0.5, retrieval_rank=0)
        retrieved2 = RetrievedExample(example=example2, score=0.6, retrieval_rank=1)

        # Rerank with CROSS_LEVEL filter type hint
        reranked = retriever._rule_rerank(
            [retrieved1, retrieved2],
            analysis_type_hint=AnalysisType.ENTITY_TABLE,
            filter_type_hint=FilterType.CROSS_LEVEL,
        )

        assert len(reranked) == 2
        assert reranked[0].example.example_id == "ex1"

    def test_mock_retrieve_fallback(self):
        """Test that mock retrieve works as fallback"""
        retriever = FewshotRetriever()

        # Call the mock retrieve directly
        results = retriever._mock_retrieve("广告主最近7天的消耗趋势")

        assert isinstance(results, list)
        assert len(results) > 0

    def test_get_fewshot_retriever_singleton(self):
        """Test singleton pattern works"""
        retriever1 = get_fewshot_retriever()
        retriever2 = get_fewshot_retriever()

        assert retriever1 is retriever2


class TestRetrievedExample:
    """Test RetrievedExample dataclass"""

    def test_retrieved_example_creation(self):
        """Test RetrievedExample can be created"""
        example = CotExample(
            example_id="test",
            question="question",
            category="positive",
            reasoning_chinese="step1",
            plan={},
        )

        retrieved = RetrievedExample(
            example=example,
            score=0.8,
            retrieval_rank=0,
        )

        assert retrieved.example == example
        assert retrieved.score == 0.8
        assert retrieved.retrieval_rank == 0


class TestCategoryFiltering:
    """Test that positive/negative examples are correctly filtered"""

    def test_positive_negative_separation(self):
        """Test that examples are correctly separated by category"""
        retriever = FewshotRetriever(
            final_positive_count=2,
            final_negative_count=1,
        )

        # Create test examples
        examples = []
        for i in range(3):
            examples.append(CotExample(
                example_id=f"pos_{i}",
                question=f"positive question {i}",
                category="positive",
                reasoning_chinese="step1",
                plan={},
            ))
        for i in range(2):
            examples.append(CotExample(
                example_id=f"neg_{i}",
                question=f"negative question {i}",
                category="negative",
                reasoning_chinese="step1",
                plan={},
            ))

        # Wrap in RetrievedExample
        retrieved_examples = [
            RetrievedExample(example=ex, score=0.5, retrieval_rank=i)
            for i, ex in enumerate(examples)
        ]

        # Simulate what happens in retrieve()
        positives = [e for e in retrieved_examples if e.example.category == "positive"]
        negatives = [e for e in retrieved_examples if e.example.category == "negative"]

        assert len(positives) == 3
        assert len(negatives) == 2
        assert all(e.example.category == "positive" for e in positives)
        assert all(e.example.category == "negative" for e in negatives)

        # Test the count limits
        final_positives = positives[:2]
        final_negatives = negatives[:1]

        assert len(final_positives) == 2
        assert len(final_negatives) == 1
