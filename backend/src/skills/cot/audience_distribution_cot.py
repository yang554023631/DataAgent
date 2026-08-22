"""
受众分布分析 CoT Skill
- 分析类型：audience_distribution
- 用途：按受众维度分组统计，如"按性别、年龄看消耗分布"
"""
from .base_cot_skill import BaseCotSkill


class AudienceDistributionCotSkill(BaseCotSkill):
    """受众分布分析 CoT Skill"""

    analysis_type = "audience_distribution"

    SPECIFIC_SYSTEM_PROMPT = """

## 你正在处理 受众分布分析 (audience_distribution)
分析类型定义：按受众维度分组统计指标分布，适合查询如"按性别、年龄看消耗分布"、"不同操作系统的曝光占比"等需求。

### 受众分布分析特定规则：
- **必须选择 chart_type = "pie"**（饼图适合展示占比分布）
- **analysis_type 必须是 "audience_distribution"**
- **一次只能分析一个受众维度**：如果用户问"分性别分年龄"，你必须生成两个独立的分析步骤，每个步骤处理一个维度
- **用户提到的中文受众维度需要映射到正确的字段名**：

中文名称 → 字段名：
- 性别 → `audience_gender`
- 年龄 → `audience_age`
- 年龄段 → `audience_age`
- 操作系统 → `audience_os`
- 设备 → `audience_os`
- 兴趣 → `audience_interest`
- 兴趣标签 → `audience_interest`
- 国家 → `audience_country`
- 城市 → `audience_city`
- 地域 → `audience_city`

- **`analysis_plan.audience_dimension` 必须填写映射后的字段名**
- **group_by 必须等于 `audience_dimension`**（按受众维度分组）

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
        "analysis_type": "audience_distribution",
        "chart_type": "pie",
        "metrics": ["impressions", "cost"],
        "time_range": {
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "granularity": "day"
        },
        "compare_time_range": null,
        "time_granularity": "day",
        "audience_dimension": "audience_gender",
        "group_by": "audience_gender",
        "order_by": "cost",
        "order_dir": "desc",
        "limit": 100,
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
        "target_level": "advertiser",
        "metrics": ["impressions", "cost"],
        "audience_dimension": null,
        "compare_time_range": null,
        "entity_ids": null,
        "additional_fields": {}
    },
    "quality_checks": []
}
```

### ❌ 错误示例（禁止这样写）：
```json
// ❌ 错误：一次分析两个维度
"audience_dimension": ["audience_gender", "audience_age"]

// ❌ 错误：保留中文不映射
"audience_dimension": "性别"
```
"""

    @property
    def specific_system_prompt(self) -> str:
        return self.SPECIFIC_SYSTEM_PROMPT
