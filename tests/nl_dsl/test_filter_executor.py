"""筛选执行器测试"""
import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any, List
from src.nl_dsl.filter_executor import FilterExecutor
from src.nl_dsl.models import FilterPlan, FilterStep, FilterCondition


@pytest.fixture
def mock_es_client():
    """Mock Elasticsearch client"""
    client = Mock()
    return client


@pytest.fixture
def filter_executor(mock_es_client):
    """Filter executor instance with mocked ES client"""
    return FilterExecutor(es_client=mock_es_client)


@pytest.fixture
def sample_time_range():
    """Sample time range"""
    return {
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
    }


class TestFilterExecutor:
    """筛选执行器测试"""

    def test_execute_none_filter(self, filter_executor, sample_time_range):
        """测试无筛选（全量）"""
        filter_plan = FilterPlan(
            filter_type="none",
            target_level="campaign",
            steps=[],
        )

        result = filter_executor.execute(
            filter_plan=filter_plan,
            advertiser_ids=["6"],
            time_range=sample_time_range,
        )

        assert result.entity_level == "campaign"
        assert result.total_count == 0
        assert len(result.trace) == 1

    def test_execute_none_filter_with_predefined_ids(self, filter_executor, sample_time_range):
        """测试预定义实体 ID 的无筛选"""
        filter_plan = FilterPlan(
            filter_type="none",
            target_level="campaign",
            steps=[],
            entity_ids=[101, 102, 103],
        )

        result = filter_executor.execute(
            filter_plan=filter_plan,
            advertiser_ids=["6"],
            time_range=sample_time_range,
        )

        assert result.entity_ids == [101, 102, 103]
        assert result.total_count == 3

    def test_execute_where_filter(self, filter_executor, mock_es_client, sample_time_range):
        """测试 where 筛选"""
        filter_plan = FilterPlan(
            filter_type="where",
            target_level="campaign",
            steps=[
                FilterStep(
                    step_id="step_1",
                    step_type="where_filter",
                    level="campaign",
                    index="campaign",
                    conditions=[
                        FilterCondition(
                            field="status",
                            operator="=",
                            value="enabled",
                        ),
                    ],
                    output_field="campaign_id",
                ),
            ],
        )

        # Mock ES response
        mock_es_client.search.return_value = {
            "aggregations": {
                "by_campaign": {
                    "buckets": [
                        {"key": 101, "doc_count": 10},
                        {"key": 102, "doc_count": 5},
                    ],
                },
            },
        }

        result = filter_executor.execute(
            filter_plan=filter_plan,
            advertiser_ids=["6"],
            time_range=sample_time_range,
        )

        assert result.entity_ids == [101, 102]
        assert result.total_count == 2
        assert result.trace[0]["status"] == "success"

    def test_execute_having_filter(self, filter_executor, mock_es_client, sample_time_range):
        """测试 having 筛选"""
        filter_plan = FilterPlan(
            filter_type="having",
            target_level="campaign",
            steps=[
                FilterStep(
                    step_id="step_1",
                    step_type="having_filter",
                    level="campaign",
                    index="ad_stat_data",
                    conditions=[
                        FilterCondition(
                            field="data_value",
                            operator=">",
                            value=10,
                            metric="cost",
                        ),
                    ],
                    output_field="campaign_id",
                ),
            ],
        )

        # Mock ES response
        mock_es_client.search.return_value = {
            "aggregations": {
                "by_campaign": {
                    "buckets": [
                        {"key": 101, "doc_count": 10, "metric_sum": {"value": 100}},
                        {"key": 102, "doc_count": 5, "metric_sum": {"value": 50}},
                    ],
                },
            },
        }

        result = filter_executor.execute(
            filter_plan=filter_plan,
            advertiser_ids=["6"],
            time_range=sample_time_range,
        )

        assert result.entity_ids == [101, 102]
        assert mock_es_client.search.called

    def test_execute_derived_having_filter(self, filter_executor, mock_es_client, sample_time_range):
        """测试派生指标 having 筛选"""
        filter_plan = FilterPlan(
            filter_type="having",
            target_level="campaign",
            steps=[
                FilterStep(
                    step_id="step_1",
                    step_type="having_filter",
                    level="campaign",
                    index="ad_stat_data",
                    conditions=[
                        FilterCondition(
                            field="ctr",
                            operator=">",
                            value=0.05,
                            metric="ctr",
                        ),
                    ],
                    output_field="campaign_id",
                ),
            ],
        )

        # Mock ES response
        mock_es_client.search.return_value = {
            "aggregations": {
                "by_campaign": {
                    "buckets": [
                        {"key": 101, "doc_count": 10, "sum_clicks": {"value": 100}, "sum_impressions": {"value": 1000}, "ctr": {"value": 0.1}},
                        {"key": 102, "doc_count": 5, "sum_clicks": {"value": 50}, "sum_impressions": {"value": 1000}, "ctr": {"value": 0.05}},
                    ],
                },
            },
        }

        result = filter_executor.execute(
            filter_plan=filter_plan,
            advertiser_ids=["6"],
            time_range=sample_time_range,
        )

        assert result.entity_ids == [101, 102]
        assert mock_es_client.search.called

    def test_execute_cross_level_up(self, filter_executor, mock_es_client, sample_time_range):
        """测试跨层级向上筛选（从 creative 到 campaign）"""
        filter_plan = FilterPlan(
            filter_type="cross_level",
            target_level="campaign",
            steps=[
                FilterStep(
                    step_id="step_1",
                    step_type="cross_level_up",
                    level="creative",
                    index="creative",
                    conditions=[
                        FilterCondition(
                            field="creative_name",
                            operator="contains",
                            value="618",
                        ),
                    ],
                    output_field="campaign_id",
                ),
            ],
        )

        # Mock ES response - 注意：多个 creative 可能属于同一个 campaign，所以会去重
        mock_es_client.search.return_value = {
            "aggregations": {
                "by_campaign": {
                    "buckets": [
                        {"key": 101, "doc_count": 3},
                        {"key": 102, "doc_count": 2},
                        {"key": 101, "doc_count": 1},  # 重复的 campaign_id
                    ],
                },
            },
        }

        result = filter_executor.execute(
            filter_plan=filter_plan,
            advertiser_ids=["6"],
            time_range=sample_time_range,
        )

        # 检查是否去重（虽然 extract_entity_ids 会去重，但 FilterExecutor 也会再去重一次）
        assert set(result.entity_ids) == {101, 102}

    def test_execute_multistep_filter(self, filter_executor, mock_es_client, sample_time_range):
        """测试多步筛选"""
        filter_plan = FilterPlan(
            filter_type="mixed",
            target_level="creative",
            steps=[
                FilterStep(
                    step_id="step_1",
                    step_type="where_filter",
                    level="campaign",
                    index="campaign",
                    conditions=[
                        FilterCondition(
                            field="status",
                            operator="=",
                            value="enabled",
                        ),
                    ],
                    output_field="campaign_id",
                ),
                FilterStep(
                    step_id="step_2",
                    step_type="having_filter",
                    level="creative",
                    index="ad_stat_data",
                    conditions=[
                        FilterCondition(
                            field="data_value",
                            operator=">",
                            value=5,
                            metric="cost",
                        ),
                    ],
                    output_field="creative_id",
                ),
            ],
        )

        # Mock ES responses
        mock_es_client.search.side_effect = [
            # 第一步：返回 campaign_ids
            {
                "aggregations": {
                    "by_campaign": {
                        "buckets": [
                            {"key": 101, "doc_count": 10},
                            {"key": 102, "doc_count": 5},
                        ],
                    },
                },
            },
            # 第二步：返回 creative_ids
            {
                "aggregations": {
                    "by_creative": {
                        "buckets": [
                            {"key": 1001, "doc_count": 10, "metric_sum": {"value": 10}},
                            {"key": 1002, "doc_count": 5, "metric_sum": {"value": 8}},
                        ],
                    },
                },
            },
        ]

        result = filter_executor.execute(
            filter_plan=filter_plan,
            advertiser_ids=["6"],
            time_range=sample_time_range,
        )

        assert result.entity_ids == [1001, 1002]
        assert result.total_count == 2
        assert len(result.trace) == 2
        assert all(t["status"] == "success" for t in result.trace)

        # 验证第二步的 DSL 包含了第一步的 campaign_ids 作为 terms 过滤
        assert mock_es_client.search.call_count == 2
        # 获取第二步的调用参数
        step2_call = mock_es_client.search.call_args_list[1]
        step2_dsl = step2_call[1]["body"]
        # 检查是否有 terms: {campaign_id: [101, 102]}
        has_campaign_terms = False
        for filter_cond in step2_dsl["query"]["bool"]["filter"]:
            if isinstance(filter_cond, dict) and "terms" in filter_cond:
                if "campaign_id" in filter_cond["terms"]:
                    assert set(filter_cond["terms"]["campaign_id"]) == {101, 102}
                    has_campaign_terms = True
        assert has_campaign_terms, "Step 2 should include terms filter for campaign_ids from step 1"

    def test_execute_with_retry_success(self, filter_executor, mock_es_client, sample_time_range):
        """测试重试成功"""
        filter_plan = FilterPlan(
            filter_type="where",
            target_level="campaign",
            steps=[
                FilterStep(
                    step_id="step_1",
                    step_type="where_filter",
                    level="campaign",
                    index="campaign",
                    conditions=[
                        FilterCondition(
                            field="status",
                            operator="=",
                            value="enabled",
                        ),
                    ],
                    output_field="campaign_id",
                ),
            ],
        )

        # 第一次失败，第二次成功
        mock_es_client.search.side_effect = [
            Exception("Connection error"),
            {
                "aggregations": {
                    "by_campaign": {
                        "buckets": [{"key": 101, "doc_count": 10}],
                    },
                },
            },
        ]

        result = filter_executor.execute(
            filter_plan=filter_plan,
            advertiser_ids=["6"],
            time_range=sample_time_range,
        )

        assert result.entity_ids == [101]
        assert mock_es_client.search.call_count == 2

    def test_execute_with_retry_failure(self, filter_executor, mock_es_client, sample_time_range):
        """测试重试失败"""
        filter_plan = FilterPlan(
            filter_type="where",
            target_level="campaign",
            steps=[
                FilterStep(
                    step_id="step_1",
                    step_type="where_filter",
                    level="campaign",
                    index="campaign",
                    conditions=[
                        FilterCondition(
                            field="status",
                            operator="=",
                            value="enabled",
                        ),
                    ],
                    output_field="campaign_id",
                ),
            ],
        )

        # 两次都失败
        mock_es_client.search.side_effect = Exception("Connection error")

        with pytest.raises(Exception, match="Connection error"):
            filter_executor.execute(
                filter_plan=filter_plan,
                advertiser_ids=["6"],
                time_range=sample_time_range,
            )

        assert mock_es_client.search.call_count == 2

    def test_execute_truncates_ids(self, filter_executor, mock_es_client, sample_time_range):
        """测试 ID 数量超过软上限时被截断"""
        filter_plan = FilterPlan(
            filter_type="where",
            target_level="campaign",
            steps=[
                FilterStep(
                    step_id="step_1",
                    step_type="where_filter",
                    level="campaign",
                    index="campaign",
                    conditions=[
                        FilterCondition(
                            field="status",
                            operator="=",
                            value="enabled",
                        ),
                    ],
                    output_field="campaign_id",
                ),
            ],
        )

        # 生成 600 个 ID
        many_ids = list(range(1, 601))
        buckets = [{"key": id, "doc_count": 1} for id in many_ids]

        mock_es_client.search.return_value = {
            "aggregations": {
                "by_campaign": {
                    "buckets": buckets,
                },
            },
        }

        result = filter_executor.execute(
            filter_plan=filter_plan,
            advertiser_ids=["6"],
            time_range=sample_time_range,
        )

        assert len(result.entity_ids) == 500
        assert result.truncated is True
        assert result.trace[0]["truncated"] is True

    def test_execute_cross_level_down(self, filter_executor, mock_es_client, sample_time_range):
        """测试跨层级向下筛选"""
        filter_plan = FilterPlan(
            filter_type="cross_level",
            target_level="ad_group",
            steps=[
                FilterStep(
                    step_id="step_1",
                    step_type="cross_level_down",
                    level="campaign",
                    index="campaign",
                    conditions=[
                        FilterCondition(
                            field="campaign_name",
                            operator="contains",
                            value="618",
                        ),
                    ],
                    output_field="ad_group_id",
                ),
            ],
        )

        # Mock ES responses
        mock_es_client.search.side_effect = [
            # 第一步: 返回 campaign_ids
            {
                "aggregations": {
                    "by_campaign": {
                        "buckets": [
                            {"key": 101, "doc_count": 10},
                            {"key": 102, "doc_count": 5},
                        ],
                    },
                },
            },
            # 第二步: 返回 ad_group_ids
            {
                "aggregations": {
                    "by_ad_group": {
                        "buckets": [
                            {"key": 201, "doc_count": 3},
                            {"key": 202, "doc_count": 2},
                            {"key": 203, "doc_count": 1},
                        ],
                    },
                },
            },
        ]

        result = filter_executor.execute(
            filter_plan=filter_plan,
            advertiser_ids=["6"],
            time_range=sample_time_range,
        )

        assert result.entity_ids == [201, 202, 203]
        assert result.total_count == 3
        # 检查结果层级是否正确（从 output_field 推断）
        assert result.entity_level == "ad_group"

        # 验证两步查询
        assert mock_es_client.search.call_count == 2

        # 验证第二步查询包含第一步的 campaign_ids
        step2_call = mock_es_client.search.call_args_list[1]
        assert step2_call[1]["index"] == "ad_group"
        step2_dsl = step2_call[1]["body"]
        has_campaign_terms = False
        for filter_cond in step2_dsl["query"]["bool"]["filter"]:
            if isinstance(filter_cond, dict) and "terms" in filter_cond:
                if "campaign_id" in filter_cond["terms"]:
                    assert set(filter_cond["terms"]["campaign_id"]) == {101, 102}
                    has_campaign_terms = True
        assert has_campaign_terms, "Cross level down step 2 should include terms filter for campaign_ids"
