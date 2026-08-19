# 修复设计：支持用户按广告主名称查询

## 问题背景
- 当前系统对"用户给广告主ID"处理正常，但对"用户给广告主名称"处理不好
- LLM不知道该怎么处理，要么留空触发澄清，要么瞎编ID
- 60个多样化query测试中，**24个因此失败**，都是按名称查询的case
- 系统已经实现了 `get_advertiser_by_name()` ES搜索功能，只需要把流程打通

## 设计方案

### 数据模型修改
`backend/src/intent/models.py` → `ReportIntentResult` 添加新字段：
```python
advertiser_names: List[str] = Field(
    default_factory=list,
    description="用户提到的广告主名称，将自动搜索转换为ID"
)
```

### Prompt规则更新
`backend/src/intent/prompts.py` → `REPORT_INTENT_SYSTEM_PROMPT` 添加明确规则：

```markdown
### 广告主识别规则（非常重要！必须严格遵守）
你需要区分用户给的是ID还是名称，分别提取到不同字段：

| 用户表达方式 | 你提取到 |
|-------------|----------|
| **"广告主6" / "id为6的广告主" / "id=6的广告主" / "六号广告主"** | `advertiser_ids: ["6"]`, `advertiser_names` 留空数组 |
| **"广告主digital_0" / "叫digital_0的广告主" / "名字是digital_0的广告主"** | `advertiser_names: ["digital_0"]`, `advertiser_ids` 留空数组（后端会自动搜索匹配ID） |

**规则：**
- 用户提到了**数字ID**就放到 `advertiser_ids`
- 用户提到了**名称**就放到 `advertiser_names`
- 如果用户同时提到多个广告主，**有的给ID有的给名称**，**分别放到对应数组**
- **禁止你猜测名称对应的ID**，猜测100%错，后端会自动搜索匹配正确ID
- 如果用户只说了"广告主"没说ID/名称，两个数组都留空
```

### 后端处理逻辑
`backend/src/intent/report_intent.py` → `_rule_validate` 方法末尾添加：

```python
# 对提取到的advertiser_names搜索转换为ID
if result.advertiser_names:
    from src.services.advertiser_service import get_advertiser_by_name
    for name in result.advertiser_names:
        matched_advertisers = get_advertiser_by_name(name)
        for adv in matched_advertisers:
            adv_id = adv["id"]
            if adv_id not in result.advertiser_ids:
                result.advertiser_ids.append(adv_id)
    logger.info(f"[名称→ID] 输入名称: {result.advertiser_names}, 输出IDs: {result.advertiser_ids}")
```

### 必填检查逻辑
`check_required_fields` 判断条件不变，还是：
```python
if not result.advertiser_ids:
    # 触发澄清
```

逻辑正确：
- 用户给名称 → 搜索得到ID → `advertiser_ids` 不为空 → 继续 ✔️
- 用户给名称 → 搜索不到 → `advertiser_ids` 为空 → 触发澄清 ✔️

## 支持场景

| 用户输入 | 处理流程 | 结果 |
|----------|---------|------|
| `广告主6 四月份消耗` | LLM提取 `advertiser_ids: ["6"]` | 直接通过 |
| `叫 digital_0 的广告主四月份消耗` | LLM提取 `advertiser_names: ["digital_0"]` → ES搜索得到 `advertiser_ids: ["6"]` | 通过 |
| `广告主6 和 双十一_90 四月份消耗对比` | LLM提取 `advertiser_ids: ["6"], advertiser_names: ["双十一_90"]` → 搜索得到第二个ID → `advertiser_ids: ["6", "123"]` | 通过 |
| `digital_0 下名称包含 mini 的广告计划` | LLM提取顶级广告主名称 → 搜索得到ID → 顶级ID有了，下级筛选正常进行 | 通过 |
| `不存在 12345 这个名称` | 搜索不到 → `advertiser_ids` 为空 | 触发澄清，让用户补充 |

## 影响评估
- 只改意图识别模块内部，下游所有模块只读 `advertiser_ids`，**一行代码不用改**
- 完全兼容原有流程，不影响任何现有功能
- 天然支持多个广告主、ID+名称混合场景
