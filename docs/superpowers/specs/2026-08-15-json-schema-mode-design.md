# 设计文档：启用火山方舟原生JSON Schema模式降低推理节点幻觉

## 概述

在报表分析的各个推理节点，启用火山方舟原生JSON Schema，通过模型输出，`json_schema`模式强制模型严格按照定义的JSON结构输出，从根源降低幻觉率。

## 背景

当前问题：
- 当前仅通过prompt提示词要求模型输出JSON，但模型仍可能输出非法JSON、遗漏必填字段、额外增加多余字段
- 火山方舟原生支持 `json_object` 和 `json_schema` 两种结构化输出模式
- `json_schema` 模式通过API层强制约束，幻觉更少

## 设计方案

### 各场景分类与模式选择

| # | 场景 | 文件 | 行号 | 输出结构固定？ | 推荐模式 | 模型 |
|---|------|------|------|-------------|----------|------|
| 1 | 顶层意图分类 | `intent/top_classifier.py | 186 | ✅ 固定 | `json_schema` | 主模型 |
| 2 | 报表意图提取 | `intent/report_intent.py` | 93 | ✅ 固定 | `json_schema` | 主模型 |
| 3 | 意图变更检测 | `intent/clarify_node.py | 88 | ✅ 固定 | `json_schema` | 主模型 |
| 4 | 查询规划 | `nl_dsl/dsl_generator.py` | 83 | ✅ 固定 | `json_schema` | 轻量模型 |
| 5 | DSL单步生成 | `nl_dsl/dsl_generator.py` | 160 | ❌ 任意ES DSL | `json_object` | 轻量模型 |
| 6 | DSL反思修正 | `nl_dsl/dsl_generator.py | 196 | ✅ 固定 | `json_schema` | 轻量模型 |
| 7 | CoT分析规划 | `analysis/cot_planner.py | 254 | ✅ 固定 | `json_schema` | 主模型 |
| 8 | RAG知识库回答 | `rag/agents.py` | 240 | ❌ 自由文本 | 不启用 | 主模型 |

### 新增Pydantic模型

| 名称 | 位置 | 说明 |
|------|------|------|
| `IntentChangeDetectionResult` | `src/intent/models.py` | 新增，用于意图变更检测 |
| `ReflectionResult` | `src/nl_dsl/models.py` | 新增，用于DSL反思修正 |

### API调用参数格式（火山方舟Responses API）

```json
{
  "text": {
    "format": {
      "type": "json_schema",
      "name": "TopClassificationResult",
      "schema": {...},
      "strict": true
    }
  }
}
```

- `type`: 固定为 `json_schema`
- `name`: schema名称 = pydantic类名
- `schema`: 完整JSON Schema，通过 `pydantic.model_json_schema()` 生成
- `strict`: `true` 强制严格遵守

### 代码修改

#### 1. `src/intent/llm_client.py 修改

`IntentLLMClient.call()` 方法增加参数：

```python
async def call(
    self,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = True,
    schema: Optional[type[BaseModel]] = None,
) -> str:
```

逻辑：
- 如果 `schema` 不为 `None` → 使用 `json_schema` 模式，动态构建 response_format 传入schema
- 如果 `schema` 为 `None` 且 `json_mode=True` → 使用 `json_object` 模式
- 如果 `json_mode=False` → 普通文本输出

#### 2. 各个调用点修改

所有需要JSON Schema的调用改为：

```python
response_text = await self.llm_client.call(
    system_prompt=...,
    user_prompt=...,
    json_mode=True,
    schema=TopClassificationResult,
)
```

#### 3. `src/analysis/cot_planner.py 修改

当前直接调用 `self.llm.invoke()` → 改为通过 `IntentLLMClient.call()` 并传入 `schema=AnalysisPlanResult`。

## 收益

1. **减少幻觉：模型在API层被强制输出合法JSON，减少JSON语法错误、遗漏字段、多余字段的概率
2. **不需要大幅改动：复用现有pydantic模型，只需要增加schema参数传递
3. **保持灵活性：DSL生成仍然用 `json_object`，适应任意结构，满足ES DSL的灵活性

## 实施步骤

1. 添加两个新pydantic模型
2. 修改 `IntentLLMClient.call` 增加schema参数支持
3. 修改各个调用点传入schema
4. 修改 `cot_planner.py` 接入client和schema
5. 测试验证

## 参考

- 火山方舟结构化输出文档：`/Users/simon/Downloads/火山方舟_结构化输出(beta)_1782549049.pdf`
