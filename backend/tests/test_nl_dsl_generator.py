"""NL→DSL 生成器测试"""
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from src.nl_dsl.dsl_generator import DslGenerator


def _make_mock_llm(response_dict: dict):
    """创建 mock LLM 客户端"""
    mock = MagicMock()
    mock.call = AsyncMock(return_value=json.dumps(response_dict))
    return mock


class TestDslGenerator:
    @pytest.mark.asyncio
    async def test_plan_query_returns_plan(self):
        """查询规划能返回结构化 QueryPlan"""
        mock_llm = _make_mock_llm({
            "steps": [
                {
                    "step_id": "step_1",
                    "description": "查询广告主最近7天消耗趋势",
                    "index": "ad_stat_data",
                    "output_fields": ["data_date", "total_cost"],
                    "purpose": "获取每日消耗数据"
                }
            ],
            "final_output": "step_1.output"
        })
        mock_schema_retriever = MagicMock()
        mock_schema_retriever.search.return_value = []

        generator = DslGenerator(llm_client=mock_llm, schema_retriever=mock_schema_retriever)
        plan = await generator.plan_query(
            user_input="广告主6最近7天消耗趋势",
            constraints={
                "advertiser_ids": ["6"],
                "time_range": {"start": "2026-07-30", "end": "2026-08-05"},
                "metrics": ["消耗"],
                "analysis_type": "trend",
            }
        )

        assert len(plan.steps) == 1
        assert plan.steps[0].step_id == "step_1"
        assert plan.steps[0].index == "ad_stat_data"

    @pytest.mark.asyncio
    async def test_generate_step_returns_dict(self):
        """生成单步 DSL 返回字典"""
        mock_llm = _make_mock_llm({
            "query": {
                "bool": {
                    "must": [
                        {"term": {"advertiser_id": 6}},
                        {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
                        {"term": {"data_type": 3}},
                    ]
                }
            },
            "size": 0,
            "aggs": {
                "by_date": {
                    "date_histogram": {"field": "data_date", "calendar_interval": "day"},
                    "aggs": {"total_cost": {"sum": {"field": "data_value"}}}
                }
            }
        })
        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(ok=True, errors=[], warnings=[])
        mock_schema_retriever = MagicMock()
        mock_schema_retriever.search.return_value = []

        from src.nl_dsl.models import QueryStep
        step = QueryStep(
            step_id="step_1",
            description="查消耗趋势",
            index="ad_stat_data",
            output_fields=["data_date"],
            purpose="趋势",
        )

        generator = DslGenerator(
            llm_client=mock_llm,
            schema_retriever=mock_schema_retriever,
            validator=mock_validator,
        )

        dsl, result = await generator.generate_step(
            step=step,
            advertiser_ids=["6"],
            time_range={"start": "2026-01-01", "end": "2026-01-31"},
        )

        assert isinstance(dsl, dict)
        assert "query" in dsl
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_generate_with_reflection(self):
        """重试时能根据反思信息修正 DSL"""
        # 直接返回修正后的 DSL（因为测试是直接传入 retry_info 进行的）
        async def mock_call(system_prompt, user_prompt, json_mode=True):
            # 反思模式返回
            return json.dumps({
                "reflection": "添加了 advertiser_id 过滤",
                "fixed_dsl": {
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"advertiser_id": 6}},
                                {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
                            ]
                        }
                    },
                    "size": 10,
                }
            })

        mock_llm = MagicMock()
        mock_llm.call = mock_call

        # validator 检查 DSL 是否包含 advertiser_id 过滤
        def mock_validate(dsl, index_name):
            from src.nl_dsl.dsl_validator import ValidationResult
            result = ValidationResult()
            # 检查 DSL 中是否有 advertiser_id 过滤
            has_advertiser = False
            query = dsl.get("query", {})
            if isinstance(query, dict):
                # 简单的检查逻辑：查找 advertiser_id 相关的键
                dsl_str = str(dsl)
                has_advertiser = "advertiser_id" in dsl_str
            if not has_advertiser:
                result.add_error("缺少 advertiser_id 过滤")
            return result

        mock_validator = MagicMock()
        mock_validator.validate.side_effect = mock_validate
        mock_schema_retriever = MagicMock()
        mock_schema_retriever.search.return_value = []

        from src.nl_dsl.models import QueryStep
        step = QueryStep(
            step_id="step_1",
            description="查数据",
            index="ad_stat_data",
            output_fields=[],
            purpose="test",
        )

        generator = DslGenerator(
            llm_client=mock_llm,
            schema_retriever=mock_schema_retriever,
            validator=mock_validator,
        )

        from src.nl_dsl.models import RetryInfo
        retry_info = RetryInfo(
            attempt=2,
            failure_type="validation",
            error_message="缺少 advertiser_id 过滤",
            previous_dsl={
                "query": {
                    "bool": {
                        "must": [
                            {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
                        ]
                    }
                },
                "size": 10,
            },
            reflection="需要添加 advertiser_id=6 的过滤",
        )
        dsl, result = await generator.generate_step(
            step=step,
            advertiser_ids=["6"],
            time_range={"start": "2026-01-01", "end": "2026-01-31"},
            retry_info=retry_info,
        )

        # 应该通过
        assert result.ok is True
        # DSL 里应该有 advertiser_id
        assert "advertiser_id" in str(dsl.get("query", {}))
