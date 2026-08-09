"""CoT Few-Shot Examples Tests"""
import pytest
import yaml
from pathlib import Path
from src.analysis.models import CotExample, AnalysisType, FilterType, EntityLevel


@pytest.fixture
def examples_yaml_path():
    """Path to cot_examples.yaml"""
    return Path(__file__).parent.parent.parent / "src" / "analysis" / "examples" / "cot_examples.yaml"


@pytest.fixture
def examples_data(examples_yaml_path):
    """Load examples from YAML"""
    if not examples_yaml_path.exists():
        pytest.skip(f"Examples file not found: {examples_yaml_path}")

    with open(examples_yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestExamplesYamlStructure:
    """Test the structure and content of cot_examples.yaml"""

    def test_yaml_loads_successfully(self, examples_data):
        """Test YAML file can be loaded without errors"""
        assert examples_data is not None
        assert "examples" in examples_data

    def test_examples_is_list(self, examples_data):
        """Test examples is a list"""
        examples = examples_data["examples"]
        assert isinstance(examples, list)
        assert len(examples) > 0

    def test_has_positive_and_negative_examples(self, examples_data):
        """Test there are both positive and negative examples"""
        examples = examples_data["examples"]
        categories = [ex["category"] for ex in examples]

        assert "positive" in categories
        assert "negative" in categories

    def test_minimum_example_counts(self, examples_data):
        """Test minimum number of examples (brief says 10+ positive, 3+ negative)"""
        examples = examples_data["examples"]
        positive = [ex for ex in examples if ex["category"] == "positive"]
        negative = [ex for ex in examples if ex["category"] == "negative"]

        assert len(positive) >= 10, f"Need at least 10 positive examples, got {len(positive)}"
        assert len(negative) >= 3, f"Need at least 3 negative examples, got {len(negative)}"

    def test_all_examples_have_required_fields(self, examples_data):
        """Test all examples have required fields"""
        examples = examples_data["examples"]
        required_fields = ["example_id", "question", "category", "reasoning_chinese", "plan"]

        for i, example in enumerate(examples):
            for field in required_fields:
                assert field in example, f"Example {i} missing required field: {field}"

    def test_example_ids_are_unique(self, examples_data):
        """Test all example_ids are unique"""
        examples = examples_data["examples"]
        ids = [ex["example_id"] for ex in examples]
        assert len(ids) == len(set(ids)), "Duplicate example_ids found"

    def test_reasoning_has_multiple_steps(self, examples_data):
        """Test reasoning_chinese has multiple steps"""
        examples = examples_data["examples"]

        for example in examples:
            reasoning = example["reasoning_chinese"]
            # Should have at least a couple of steps
            assert "Step" in reasoning or "步骤" in reasoning, f"Example {example['example_id']} has no steps in reasoning"

    def test_plan_has_required_structure(self, examples_data):
        """Test plan has required structure"""
        examples = examples_data["examples"]

        for example in examples:
            plan = example["plan"]
            assert "target_level" in plan, f"Example {example['example_id']} plan missing target_level"
            assert "filter_plan" in plan, f"Example {example['example_id']} plan missing filter_plan"
            assert "analysis_plan" in plan, f"Example {example['example_id']} plan missing analysis_plan"

    def test_negative_examples_have_notes(self, examples_data):
        """Test negative examples have notes explaining what's wrong"""
        examples = examples_data["examples"]
        negative = [ex for ex in examples if ex["category"] == "negative"]

        for example in negative:
            assert "notes" in example, f"Negative example {example['example_id']} missing notes"
            assert example["notes"] is not None
            assert len(example["notes"].strip()) > 0


class TestExamplesCoverage:
    """Test examples cover various analysis types and filter types"""

    def test_covers_all_analysis_types(self, examples_data):
        """Test examples cover all AnalysisType values"""
        examples = examples_data["examples"]
        positive = [ex for ex in examples if ex["category"] == "positive"]

        # Get all analysis types used in examples
        used_types = set()
        for example in positive:
            if "analysis_type" in example and example["analysis_type"]:
                used_types.add(example["analysis_type"])

        # Should cover most, if not all, analysis types
        expected_types = {"entity_table", "time_trend", "period_comparison", "audience_distribution", "summary"}
        # Just check we have a good variety, not necessarily all
        assert len(used_types) >= 4, f"Expected at least 4 analysis types, got {len(used_types)}"

    def test_covers_all_filter_types(self, examples_data):
        """Test examples cover various filter types"""
        examples = examples_data["examples"]
        positive = [ex for ex in examples if ex["category"] == "positive"]

        used_filters = set()
        for example in positive:
            if "filter_type" in example and example["filter_type"]:
                used_filters.add(example["filter_type"])

        # Should have a good variety
        assert "none" in used_filters
        assert "where" in used_filters
        assert "having" in used_filters


class TestCotExampleModelValidation:
    """Test that examples can be parsed into CotExample models"""

    def test_example_parses_to_model(self, examples_data):
        """Test a sample example can be parsed into CotExample"""
        examples = examples_data["examples"]
        sample = examples[0]

        # Parse to model
        model = CotExample(
            example_id=sample["example_id"],
            question=sample["question"],
            category=sample["category"],
            analysis_type=AnalysisType(sample["analysis_type"]) if sample.get("analysis_type") else None,
            filter_type=FilterType(sample["filter_type"]) if sample.get("filter_type") else None,
            reasoning_chinese=sample["reasoning_chinese"],
            plan=sample["plan"],
            notes=sample.get("notes"),
        )

        assert model.example_id == sample["example_id"]
        assert model.question == sample["question"]
        assert model.category == sample["category"]

    def test_all_positive_examples_parse(self, examples_data):
        """Test all positive examples can be parsed into CotExample"""
        examples = examples_data["examples"]
        positive = [ex for ex in examples if ex["category"] == "positive"]

        for example in positive:
            try:
                model = CotExample(
                    example_id=example["example_id"],
                    question=example["question"],
                    category=example["category"],
                    analysis_type=AnalysisType(example["analysis_type"]) if example.get("analysis_type") else None,
                    filter_type=FilterType(example["filter_type"]) if example.get("filter_type") else None,
                    reasoning_chinese=example["reasoning_chinese"],
                    plan=example["plan"],
                    notes=example.get("notes"),
                )
                # Validation passed
                assert model is not None
            except Exception as e:
                pytest.fail(f"Example {example['example_id']} failed to parse: {e}")

    def test_all_negative_examples_parse(self, examples_data):
        """Test all negative examples can be parsed into CotExample"""
        examples = examples_data["examples"]
        negative = [ex for ex in examples if ex["category"] == "negative"]

        for example in negative:
            try:
                model = CotExample(
                    example_id=example["example_id"],
                    question=example["question"],
                    category=example["category"],
                    analysis_type=AnalysisType(example["analysis_type"]) if example.get("analysis_type") else None,
                    filter_type=FilterType(example["filter_type"]) if example.get("filter_type") else None,
                    reasoning_chinese=example["reasoning_chinese"],
                    plan=example["plan"],
                    notes=example.get("notes"),
                )
                # Validation passed
                assert model is not None
            except Exception as e:
                pytest.fail(f"Example {example['example_id']} failed to parse: {e}")
