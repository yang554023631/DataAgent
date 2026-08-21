# CoT 分析 Prompt Skill 重构设计文档

## 背景和问题

当前 `analysis` (CoT 主路径) 的 `cot_planner` 使用**大一统的全量 system prompt**，包含了**所有 5 种分析类型**的完整规则：

| 现状 | 问题 |
|------|------|
| 每次调用 LLM，无论要做哪种分析，**所有 5 种分析类型的规则都一起发给 LLM** | 造成 **~35-40% 的 prompt token 浪费** |
| token 浪费 = 成本更高 + 推理更慢 | 需要优化 |

*注：顶级路径（cot / structured / nl_dsl / rag）之间已经是分开的，每个路径有独立 prompt，不存在跨路径冗余。我们只优化 cot 内部的冗余。*

## 重构收益

| 收益 | 具体效果 |
|------|---------|
| ✅ **减少 token 消耗** | 每次 CoT 请求减少 **35-40%** prompt token → 直接降低 API 成本 |
| ✅ **提升 LLM 推理速度** | token 越少 → 推理越快 → 端到端响应更快 |
| ✅ **更好的代码组织** | 每个分析类型独立文件，职责单一 → 更容易维护 |
| ✅ **更好的扩展性** | 新增分析类型只需加新文件 → 不影响现有代码 |

## 设计方案

### Prompt 拆分原则

```
base_cot_skill.py → BASE_GENERAL_PROMPT
  ↑
  所有分析类型**共用**的规则：
  - 实体层级说明
  - 索引命名规则
  - 维度字段说明
  - 操作符规则
  - 筛选规则（where/having/cross_level）
  - 输出格式要求
  - 必填字段检查清单

  ≈ 6000 token

每个具体分析类型 → {analysis_type}_cot.py
  ↑
  只有**当前分析类型**特有的规则：
  - 分析类型定义
  - 类型特定规则（比如时间趋势必须用 line）
  - 类型特定输出示例

  ≈ 2800 token / 每个
```

**最终每次调用**：`BASE_GENERAL_PROMPT + 当前分析类型特定规则` → 总共 ~8800 token，比原来 ~14000 token 节省 **≈ 37%**。

### 文件结构

```
backend/src/
├── skills/
│   └── cot/                           # 🆕 CoT 分析类型 skill
│       ├── __init__.py
│       ├── base_cot_skill.py          # 基础类 + 通用 prompt
│       ├── skill_registry.py         # 分析类型 skill 注册表 + 懒加载
│       ├── time_trend_cot.py        # 时间趋势
│       ├── entity_table_cot.py      # 实体表格
│       ├── period_comparison_cot.py # 周期对比
│       ├── audience_distribution_cot.py # 受众分布
│       └── summary_cot.py          # 多指标汇总
└── ...
```

### 调用流程

```
用户请求 → 主图 → report_intent → analysis_node → cot_planner.plan()
                                       ↓
                              获取 analysis_type
                                       ↓
                          skill_registry.get(analysis_type)
                                       ↓
                    拿到对应 skill → skill.get_system_prompt()
                                       ↓
                通用 + 当前类型特定 → 拼成最终 prompt
                                       ↓
                               调用 LLM
                                       ↓
                          得到计划 → 继续执行
```

### 懒加载

- 启动时：只注册工厂函数，不实例化
- 第一次用到某个分析类型：实例化 → 缓存
- 后续：直接用缓存

## 核心代码示例

### 1. 基础类 + 通用 prompt

```python
# src/skills/cot/base_cot_skill.py

from abc import ABC, abstractmethod

BASE_GENERAL_PROMPT = """
## 你是广告数据分析专家，擅长将用户的自然语言查询转化为结构化的分析执行计划。

## 你的任务
1. 理解用户的查询意图
2. 逐步推理需要哪些数据筛选和分析操作
3. 输出结构化的 JSON 格式计划

## 可用的实体层级（entity level）
- advertiser: 广告主层级 → 维度表索引名 = `advertiser`
- campaign: 广告计划层级 → 维度表索引名 = `campaign`
- ad_group: 广告组层级 → 维度表索引名 = `adgroup`
- creative: 创意/素材层级 → 维度表索引名 = `creative`

... (所有通用规则，原来大一统里的通用部分都放这里)
"""

class BaseCotSkill(ABC):
    """CoT 分析 Skill 基础类"""

    @property
    @abstractmethod
    def analysis_type(self) -> str:
        """分析类型"""
        ...

    @property
    @abstractmethod
    def specific_system_prompt(self) -> str:
        """当前分析类型特定 prompt"""
        ...

    def get_system_prompt(self) -> str:
        """拼接完整 prompt"""
        return BASE_GENERAL_PROMPT + self.specific_system_prompt
```

### 2. 具体分析类型 Skill 例子

```python
# src/skills/cot/time_trend_cot.py

from .base_cot_skill import BaseCotSkill

class TimeTrendCotSkill(BaseCotSkill):
    """时间趋势分析 CoT Skill"""

    analysis_type = "time_trend"

    SPECIFIC_SYSTEM_PROMPT = """
## 你正在处理 时间趋势分析
分析类型定义：展示指标随时间变化的趋势，按日期分组。

### 规则：
- 必须选择 chart_type = "line"（折线图）
- group_by 必须是 "data_date"
- analysis_type 必须是 "time_trend"
- 只需要单步分析，不需要多步骤

### 输出示例：
... (只放时间趋势相关示例)
"""

    @property
    def specific_system_prompt(self) -> str:
        return self.SPECIFIC_SYSTEM_PROMPT
```

### 3. Skill 注册表

```python
# src/skills/cot/skill_registry.py

from typing import Dict, Callable, Optional
from .base_cot_skill import BaseCotSkill

class CotSkillRegistry:
    """CoT 分析 Skill 注册表，支持懒加载"""

    def __init__(self):
        self._instances: Dict[str, BaseCotSkill] = {}
        self._lazy_factories: Dict[str, Callable[[], BaseCotSkill]] = {}

    def register_lazy(self, analysis_type: str, factory: Callable[[], BaseCotSkill]) -> None:
        """注册懒加载 Skill"""
        self._lazy_factories[analysis_type] = factory

    def get(self, analysis_type: str) -> BaseCotSkill:
        """获取 Skill，懒加载首次调用才实例化"""
        if analysis_type in self._instances:
            return self._instances[analysis_type]

        if analysis_type in self._lazy_factories:
            skill = self._lazy_factories[analysis_type]()
            self._instances[analysis_type] = skill
            return skill

        raise ValueError(f"CoT Skill for analysis_type '{analysis_type}' not found")

# 全局单例
cot_skill_registry = CotSkillRegistry()

# 启动时注册懒加载
from ... import TimeTrendCotSkill
cot_skill_registry.register_lazy("time_trend", lambda: TimeTrendCotSkill())
cot_skill_registry.register_lazy("entity_table", lambda: EntityTableCotSkill())
cot_skill_registry.register_lazy("period_comparison", lambda: PeriodComparisonCotSkill())
cot_skill_registry.register_lazy("audience_distribution", lambda: AudienceDistributionCotSkill())
cot_skill_registry.register_lazy("summary", lambda: SummaryCotSkill())

def get_cot_skill(analysis_type: str) -> BaseCotSkill:
    return cot_skill_registry.get(analysis_type)
```

### 4. 在 cot_planner 中使用

```python
# src/analysis/cot_planner.py

from src.skills.cot.skill_registry import get_cot_skill

...

async def plan(...):
    # ... 前面步骤省略
    analysis_type = infer_analysis_type(field_context)

    # 关键：根据分析类型拿到对应 skill，只拼对应 prompt
    cot_skill = get_cot_skill(analysis_type)
    system_prompt = cot_skill.get_system_prompt().replace("{today_date}", today_str)

    # 调用 LLM，prompt token 已经省了 35-40%
    raw_response = await self._call_llm(system_prompt, current_user_prompt, ...)
```

## 日志统计设计

### 1. 在 llm_client 统一记录

```python
# src/intent/llm_client.py

import json
import logging
import time

logger = logging.getLogger("llm_usage")

async def call(self, system_prompt: str, user_prompt: str, ...) -> str:
    start_time = time.time()

    # 调用 LLM
    response = await self._client.chat(...)

    elapsed_ms = int((time.time() - start_time) * 1000)
    prompt_tokens = response.usage.prompt_tokens

    # 记 JSON 日志
    logger.info(json.dumps({
        "event": "llm_call",
        "prompt_tokens": prompt_tokens,
        "elapsed_ms": elapsed_ms,
        "model": self.model,
        "timestamp": time.time()
    }, ensure_ascii=False))

    return response.text
```

### 2. 统计脚本

```python
# scripts/stats_llm_usage.py

import json
import statistics
import sys

def main(log_file: str):
    tokens = []
    times = []

    with open(log_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if '"event": "llm_call"' in line:
                try:
                    data = json.loads(line)
                    tokens.append(data["prompt_tokens"])
                    times.append(data["elapsed_ms"])
                except Exception:
                    continue

    print(f"=== LLM 调用统计 ===\n")
    print(f"总调用次数: {len(tokens)}")
    print()
    print(f"平均 prompt token: {statistics.mean(tokens):.0f}")
    print(f"中位数 prompt token: {statistics.median(tokens):.0f}")
    print(f"总 prompt token: {sum(tokens):.0f}")
    print()
    print(f"平均 LLM 响应时间 (ms): {statistics.mean(times):.0f}")
    print(f"中位数 LLM 响应时间 (ms): {statistics.median(times):.0f}")

if __name__ == "__main__":
    main(sys.argv[1])
```

### 对比方法

```bash
# 旧分支（当前）
./run-benchmark.sh > old.log
python scripts/stats_llm_usage.py old.log > old.stats
cat old.stats

# 新分支（重构后）
./run-benchmark.sh > new.log
python scripts/stats_llm_usage.py new.log > new.stats
cat new.stats

# 对比
diff old.stats new.stats
```

## 实现计划步骤

| 步骤 | 内容 | 预计新增/改动行数 |
|------|------|------------------|
| 1 | 创建分支 `refactor-skill-architecture-0819` | - |
| 2 | 创建 `src/skills/cot/` 目录结构 | - |
| 3 | 写 `base_cot_skill.py` + `skill_registry.py` | + ~150 行 |
| 4 | 创建 5 个分析类型 skill | + ~5 × 80 = 400 行 |
| 5 | 修改 `src/analysis/cot_planner.py` 使用 skill registry | ~改动 150 行 |
| 6 | 拆分大一统 prompt → 通用放 base，特定放对应 skill | ~改动 100 行 |
| 7 | 在 `llm_client.py` 添加 token/耗时日志 | ~改动 20 行 |
| 8 | 添加统计脚本 `scripts/stats_llm_usage.py` | + ~50 行 |
| 9 | 跑测试验证全量通过 | - |
| **合计** | | **~ 770 行** |

## 验收标准

1. ✅ 所有现有测试用例全量通过
2. ✅ 每个 CoT 请求 prompt token **减少 35-40%**
3. ✅ 日志正确输出 `llm_call` JSON 日志，统计脚本正常工作

## 预期效果

| 指标 | 重构前 | 预期重构后 | 变化 |
|------|---------|-----------|------|
| 平均 prompt token / CoT 请求 | ~14,000 | ~8,800 | ↓ 37% |
| 总 token 61 个测试用例 | ~850,000 | ~530,000 | ↓ 38% |
