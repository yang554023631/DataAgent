"""
整体数据汇总分析 CoT Skill
- 分析类型：summary
- 用途：对指定范围计算整体汇总指标，不进行二次分组
"""
from .base_cot_skill import BaseCotSkill


class SummaryCotSkill(BaseCotSkill):
    """整体数据汇总分析 CoT Skill"""

    analysis_type = "summary"

    SPECIFIC_SYSTEM_PROMPT = """

## 你正在处理 整体数据汇总分析 (summary)
分析类型定义：对指定范围计算**整体汇总指标**，不进行二次分组，输出最终汇总值。适合查询如"广告主6四月份整体概览"、"某某campaign三月份总消耗"、"某个创意四月份总点击"等需求。

### 整体数据汇总分析特定规则：
- **推荐选择 chart_type = "table"**（表格展示汇总指标清晰）
- **analysis_type 必须是 "summary"**
- **不需要 group_by**（因为只计算整体汇总，不需要分组），但仍然需要填写 `group_by` 字段，建议填 `null` 或者目标层级名称
- 汇总分析会自动计算所有指定范围内的指标总和，不需要额外分组

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
        "analysis_type": "summary",
        "chart_type": "table",
        "metrics": ["impressions", "clicks", "cost", "ctr", "cpc"],
        "time_range": {
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "granularity": "day"
        },
        "compare_time_range": null,
        "time_granularity": "day",
        "audience_dimension": null,
        "group_by": null,
        "order_by": null,
        "order_dir": "asc",
        "limit": 1,
        "quality_checks": [],
        "steps": []
    },
    "reasoning": null,
    "field_context": {
        "advertiser_ids": [6],
        "time_range": {
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "granularity": "day"
        },
        "target_level": "campaign",
        "metrics": ["impressions", "clicks", "cost", "ctr", "cpc"],
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
