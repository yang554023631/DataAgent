"""
时间趋势分析 CoT Skill
- 分析类型：time_trend
- 用途：展示指标随时间变化的趋势，按日期分组
"""
from .base_cot_skill import BaseCotSkill


class TimeTrendCotSkill(BaseCotSkill):
    """时间趋势分析 CoT Skill"""

    analysis_type = "time_trend"

    SPECIFIC_SYSTEM_PROMPT = """

## 你正在处理 时间趋势分析 (time_trend)
分析类型定义：展示指标随时间变化的趋势，按日期分组，适合查询如"近7天的曝光变化"、"三月份消耗趋势"等需求。

### 时间趋势分析特定规则：
- **必须选择 chart_type = "line"**（折线图是展示时间趋势的最佳选择）
- **group_by 必须是 "data_date"**（按日期分组）
- **analysis_type 必须是 "time_trend"**
- 时间粒度 `time_granularity` 必须和 `time_range.granularity` 保持一致
- 排序 `order_by` 必须是 "data_date"，`order_dir` 默认是 "asc"

### 输出示例：
```json
{
    "target_level": "campaign",
    "filter_plan": {
        "filter_type": "where",
        "target_level": "campaign",
        "steps": [
            {
                "step_id": "step_1",
                "step_type": "where_filter",
                "level": "campaign",
                "index": "campaign",
                "conditions": [
                    {
                        "field": "advertiser_id",
                        "operator": "=",
                        "value": 6
                    }
                ],
                "output_field": "campaign_id"
            }
        ]
    },
    "analysis_plan": {
        "analysis_type": "time_trend",
        "chart_type": "line",
        "metrics": ["impressions", "clicks", "cost"],
        "time_range": {
            "start_date": "2026-08-01",
            "end_date": "2026-08-07",
            "granularity": "day"
        },
        "compare_time_range": null,
        "time_granularity": "day",
        "audience_dimension": null,
        "group_by": "data_date",
        "order_by": "data_date",
        "order_dir": "asc",
        "limit": 100,
        "quality_checks": [],
        "steps": []
    },
    "reasoning": null,
    "field_context": {
        "advertiser_ids": [6],
        "time_range": {
            "start_date": "2026-08-01",
            "end_date": "2026-08-07",
            "granularity": "day"
        },
        "target_level": "campaign",
        "metrics": ["impressions", "clicks", "cost"],
        "audience_dimension": null,
        "compare_time_range": null,
        "entity_ids": null,
        "additional_fields": {}
    },
    "quality_checks": []
}
```
"""

    @property
    def specific_system_prompt(self) -> str:
        return self.SPECIFIC_SYSTEM_PROMPT
