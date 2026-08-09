"""空结果自查器测试"""
import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any, List
from src.nl_dsl.empty_checker import EmptyResultChecker
from src.nl_dsl.models import (
    AnalysisPlan,
    AnalysisTimeRange,
    FilterResult,
    EmptyCheckErrorType,
)


@pytest.fixture
def mock_es_client():
    """Mock Elasticsearch client"""
    client = Mock()
    return client


@pytest.fixture
def empty_checker(mock_es_client):
    """Empty result checker instance"""
    return EmptyResultChecker(es_client=mock_es_client)


@pytest.fixture
def sample_time_range():
    """Sample time range"""
    return AnalysisTimeRange(
        start_date="2026-04-01",
        end_date="2026-04-30",
        granularity="day",
    )


@pytest.fixture
def sample_analysis_plan(sample_time_range):
    """Sample analysis plan"""
    return AnalysisPlan(
        analysis_type="time_trend",
        time_range=sample_time_range,
        metrics=["cost", "impressions", "ctr"],
    )


class TestEmptyResultChecker:
    """空结果自查器测试"""

    def test_check_passed(
        self,
        empty_checker,
        mock_es_client,
        sample_analysis_plan,
    ):
        """测试通过检查"""
        # Mock ES responses
        mock_es_client.search.side_effect = [
            # 第一次调用：文档数检查
            {"hits": {"total": {"value": 1000}}},
            # 第二次调用：核心指标和检查
            {
                "aggregations": {
                    "sum_dt_1": {"total": {"value": 10000}},
                    "sum_dt_2": {"total": {"value": 500000}},
                }
            },
        ]

        result = empty_checker.check(
            analysis_plan=sample_analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.found_error is False
        assert result.error_type is None

    def test_check_invalid_time_range_swapped(
        self,
        empty_checker,
        sample_analysis_plan,
    ):
        """测试无效时间范围：开始日期晚于结束日期"""
        sample_analysis_plan.time_range.start_date = "2026-04-30"
        sample_analysis_plan.time_range.end_date = "2026-04-01"

        result = empty_checker.check(
            analysis_plan=sample_analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.found_error is True
        assert result.error_type == EmptyCheckErrorType.INVALID_TIME_RANGE
        assert len(result.hints) > 0
        assert "晚于" in result.hints[0]
        # 检查是否提供了校正建议
        assert result.correction is not None
        assert result.correction["start_date"] == "2026-04-01"
        assert result.correction["end_date"] == "2026-04-30"

    def test_check_invalid_time_range_format(
        self,
        empty_checker,
        sample_analysis_plan,
    ):
        """测试无效时间范围：格式错误"""
        sample_analysis_plan.time_range.start_date = "2026/04/01"  # 错误格式

        result = empty_checker.check(
            analysis_plan=sample_analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.found_error is True
        assert result.error_type == EmptyCheckErrorType.INVALID_TIME_RANGE
        assert "格式无效" in result.hints[0]

    def test_check_invalid_time_range_too_large(
        self,
        empty_checker,
        sample_analysis_plan,
    ):
        """测试无效时间范围：范围过大"""
        sample_analysis_plan.time_range.start_date = "2020-01-01"
        sample_analysis_plan.time_range.end_date = "2026-04-30"  # 超过3年

        result = empty_checker.check(
            analysis_plan=sample_analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.found_error is True
        assert result.error_type == EmptyCheckErrorType.INVALID_TIME_RANGE
        assert "时间范围过大" in result.hints[0]

    def test_check_invalid_metrics(
        self,
        empty_checker,
        sample_analysis_plan,
    ):
        """测试无效指标"""
        sample_analysis_plan.metrics = ["cost", "invalid_metric", "another_bad_one"]

        result = empty_checker.check(
            analysis_plan=sample_analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.found_error is True
        assert result.error_type == EmptyCheckErrorType.INVALID_METRICS
        assert "未知的指标" in result.hints[0]
        assert "invalid_metric" in result.hints[0]
        assert "another_bad_one" in result.hints[0]

    def test_check_empty_entity_ids(
        self,
        empty_checker,
        sample_analysis_plan,
    ):
        """测试空实体ID列表"""
        filter_result = FilterResult(
            entity_ids=[],
            entity_level="campaign",
            total_count=0,
        )

        result = empty_checker.check(
            analysis_plan=sample_analysis_plan,
            advertiser_ids=["6"],
            filter_result=filter_result,
        )

        assert result.found_error is True
        assert result.error_type == EmptyCheckErrorType.NO_ENTITY_IDS
        assert "筛选结果为空" in result.hints[0]

    def test_check_entity_ids_parameter(
        self,
        empty_checker,
        sample_analysis_plan,
    ):
        """测试通过 entity_ids 参数传递空列表"""
        result = empty_checker.check(
            analysis_plan=sample_analysis_plan,
            advertiser_ids=["6"],
            entity_ids=[],
            entity_level="campaign",
        )

        assert result.found_error is True
        assert result.error_type == EmptyCheckErrorType.NO_ENTITY_IDS

    def test_check_no_documents(
        self,
        empty_checker,
        mock_es_client,
        sample_analysis_plan,
    ):
        """测试ES查询无文档"""
        mock_es_client.search.return_value = {
            "hits": {"total": {"value": 0}},
        }

        result = empty_checker.check(
            analysis_plan=sample_analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.found_error is True
        assert result.error_type == EmptyCheckErrorType.NO_DOCUMENTS
        assert "没有找到任何数据" in result.hints[0]

    def test_check_no_data_values(
        self,
        empty_checker,
        mock_es_client,
        sample_analysis_plan,
    ):
        """测试ES查询有文档但核心指标全零"""
        mock_es_client.search.side_effect = [
            # 文档数检查
            {"hits": {"total": {"value": 1000}}},
            # 核心指标和检查
            {
                "aggregations": {
                    "sum_dt_1": {"total": {"value": 0}},
                    "sum_dt_2": {"total": {"value": 0}},
                }
            },
        ]

        result = empty_checker.check(
            analysis_plan=sample_analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.found_error is True
        assert result.error_type == EmptyCheckErrorType.NO_DATA_VALUES
        assert "总和为零" in result.hints[0]

    def test_check_with_entity_filter(
        self,
        empty_checker,
        mock_es_client,
        sample_analysis_plan,
    ):
        """测试带实体过滤的检查"""
        mock_es_client.search.side_effect = [
            {"hits": {"total": {"value": 500}}},
            {
                "aggregations": {
                    "sum_dt_1": {"total": {"value": 5000}},
                    "sum_dt_2": {"total": {"value": 200000}},
                }
            },
        ]

        filter_result = FilterResult(
            entity_ids=[101, 102, 103],
            entity_level="campaign",
            total_count=3,
        )

        result = empty_checker.check(
            analysis_plan=sample_analysis_plan,
            advertiser_ids=["6"],
            filter_result=filter_result,
        )

        assert result.found_error is False
        # 验证 ES 查询被正确调用
        assert mock_es_client.search.called

    def test_check_es_error_fallback(
        self,
        empty_checker,
        mock_es_client,
        sample_analysis_plan,
    ):
        """测试ES查询错误时的降级处理"""
        mock_es_client.search.side_effect = Exception("ES connection error")

        result = empty_checker.check(
            analysis_plan=sample_analysis_plan,
            advertiser_ids=["6"],
        )

        # ES 出错时应该降级通过，继续后续流程
        assert result.found_error is False

    def test_check_derived_metrics(
        self,
        empty_checker,
        mock_es_client,
        sample_analysis_plan,
    ):
        """测试派生指标的检查"""
        sample_analysis_plan.metrics = ["ctr", "cvr"]  # 都是派生指标

        mock_es_client.search.side_effect = [
            {"hits": {"total": {"value": 1000}}},
            {
                "aggregations": {
                    "sum_dt_1": {"total": {"value": 1000}},  # cost
                    "sum_dt_2": {"total": {"value": 500000}},  # impressions
                    "sum_dt_3": {"total": {"value": 2500}},  # clicks
                    "sum_dt_4": {"total": {"value": 50}},  # conversions
                }
            },
        ]

        result = empty_checker.check(
            analysis_plan=sample_analysis_plan,
            advertiser_ids=["6"],
        )

        assert result.found_error is False
