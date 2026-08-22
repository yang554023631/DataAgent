"""
实体列表表格分析 CoT Skill
- 分析类型：entity_table
- 用途：查询满足筛选条件的多个实体，每个实体一行数据，支持排序和TopN
"""
from .base_cot_skill import BaseCotSkill


class EntityTableCotSkill(BaseCotSkill):
    """实体列表表格分析 CoT Skill"""

    analysis_type = "entity_table"

    SPECIFIC_SYSTEM_PROMPT = """

## 你正在处理 实体列表表格分析 (entity_table)
分析类型定义：查询满足筛选条件的**多个实体**，每个实体一行数据，支持排序和TopN，适合查询如"广告主6消耗最高的前十名广告计划"、"哪些创意点击量超过1000"等需求。

### 实体列表表格分析特定规则：
- **必须选择 chart_type = "table"**（表格展示明细列表）
- **analysis_type 必须是 "entity_table"**
- **group_by 必须是目标实体层级名称**（例如查询 campaign 列表，`group_by` 就是 `"campaign"`，**不能加 `_id` 后缀**）
- **需要指定 `order_by` 和 `order_dir`**：通常按某个指标降序排序取 TopN（比如按 `cost` 降序）
- **limit 默认 100，用户不指定最多不超过 1000**

### 输出示例：
```json
{
    "target_level": "ad_group",
    "filter_plan": {
        "filter_type": "where",
        "target_level": "ad_group",
        "steps": [
            {
                "step_id": "step_1",
                "step_type": "where_filter",
                "level": "ad_group",
                "index": "adgroup",
                "conditions": [
                    {
                        "field": "advertiser_id",
                        "operator": "=",
                        "value": 6
                    }
                ],
                "output_field": "ad_group_id"
            }
        ]
    },
    "analysis_plan": {
        "analysis_type": "entity_table",
        "chart_type": "table",
        "metrics": ["impressions", "clicks", "cost", "ctr"],
        "time_range": {
            "start_date": "2026-08-01",
            "end_date": "2026-08-07",
            "granularity": "day"
        },
        "compare_time_range": null,
        "time_granularity": "day",
        "audience_dimension": null,
        "group_by": "ad_group",
        "order_by": "cost",
        "order_dir": "desc",
        "limit": 10,
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
        "target_level": "ad_group",
        "metrics": ["impressions", "clicks", "cost", "ctr"],
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
