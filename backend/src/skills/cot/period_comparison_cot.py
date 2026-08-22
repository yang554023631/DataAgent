"""
时期对比分析 CoT Skill
- 分析类型：period_comparison
- 用途：对比两个不同时间段的数据，如"三月份 vs 四月份消耗对比"
"""
from .base_cot_skill import BaseCotSkill


class PeriodComparisonCotSkill(BaseCotSkill):
    """时期对比分析 CoT Skill"""

    analysis_type = "period_comparison"

    SPECIFIC_SYSTEM_PROMPT = """

## 你正在处理 时期对比分析 (period_comparison)
分析类型定义：对比两个不同时间段的数据，计算两个时间段的指标差异，适合查询如"三月份 vs 四月份消耗对比"、"本周和上周点击率对比"等需求。

### 时期对比分析特定规则：
- **必须选择 chart_type = "bar"**（柱状图适合对比不同时间段）
- **analysis_type 必须是 "period_comparison"**
- **必须同时提供 `time_range` 和 `compare_time_range`**，两个时间段不能重叠
- **`compare_time_range` 必须包含 `compare_start_date` 和 `compare_end_date`**，不能使用 `start_date`/`end_date` 命名
- group_by 必须是 `data_date` 或者按时间段分组（通常保持 `data_date`）
- 所有 metrics 需要同时统计两个时间段

### 输出示例：
```json
{
    "target_level": "advertiser",
    "filter_plan": {
        "filter_type": "none",
        "target_level": "advertiser",
        "steps": []
    },
    "analysis_plan": {
        "analysis_type": "period_comparison",
        "chart_type": "bar",
        "metrics": ["impressions", "clicks", "cost"],
        "time_range": {
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "granularity": "day"
        },
        "compare_time_range": {
            "compare_start_date": "2026-04-01",
            "compare_end_date": "2026-04-30",
            "granularity": "day"
        },
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
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "granularity": "day"
        },
        "compare_time_range": {
            "compare_start_date": "2026-04-01",
            "compare_end_date": "2026-04-30",
            "granularity": "day"
        },
        "target_level": "advertiser",
        "metrics": ["impressions", "clicks", "cost"],
        "audience_dimension": null,
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
