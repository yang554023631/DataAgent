# 意图识别智能化 & 查询层升级 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有报表分析链路基础上，建设双轨查询架构——保留结构化快车道，新增 NL→DSL 自由通道（Schema RAG + NL→DSL 生成 + 自反思重试 + 多层安全防护），意图识别层从"枚举式校验"升级为"理解式收集 + 动态路由"。

**Architecture:** 双轨查询架构。意图层（report_intent）改造后做路由判断，结构化可表达的走现有 planner/executor，复杂查询走新的 nl_dsl_node。Schema RAG 复用现有 PostgreSQL + pgvector 基础设施，doc_type='schema' 区分。NL→DSL 模块包含查询规划、DSL 生成、安全校验、自反思执行、结果格式化。四层安全防护（Prompt约束 + DSL结构校验 + ES只读账号 + 执行时防护）。

**Tech Stack:** Python 3.10+, LangGraph, Elasticsearch, PostgreSQL + pgvector, OpenAI-compatible LLM API, Pydantic v1/v2

## Global Constraints

- 日志格式对齐现有规范：`%(asctime)s [%(levelname)s] [%(request_id)s] [%(session_id)s] [%(name)s] %(message)s`，只用 INFO/ERROR 级别，长文本用 `truncate_log()` 截断
- `request_id` / `session_id` 通过 `contextvars` 自动注入，从 `src.config.context` 获取
- 错误日志用 `logger.exception()` 打印完整堆栈
- ES 连接默认 `http://localhost:9200`，NL→DSL 使用独立只读角色（配置化）
- LLM 客户端复用 `IntentLLMClient` 模式（`intent/llm_client.py`）
- 测试框架：pytest + pytest-asyncio + unittest.mock
- 测试文件放在 `backend/tests/` 根目录（与现有一致）
- 最大查询尝试次数：3 次（首次 + 2 次重试）
- 最大查询步数：5 步
- size 上限：1000 条；agg size 上限：500
- 查询超时：30 秒
- 必须包含 advertiser_id 过滤，不允许查全平台
- 必须包含时间范围过滤

---

## File Changes Overview

| File | Change |
|------|--------|
| `src/schema_rag/__init__.py` | Create |
| `src/schema_rag/models.py` | Create - SchemaDoc / SchemaField / QueryPattern 模型 |
| `src/schema_rag/retriever.py` | Create - Schema 向量检索 |
| `src/schema_rag/sync.py` | Create - 从 YAML 同步到 Pg |
| `src/schema_rag/schemas/advertiser.yaml` | Create - 索引 schema 配置 |
| `src/schema_rag/schemas/ad_stat_data.yaml` | Create |
| `src/schema_rag/schemas/ad_stat_audience.yaml` | Create |
| `src/schema_rag/schemas/adgroup.yaml` | Create |
| `src/schema_rag/schemas/query_patterns.yaml` | Create - 查询示例 |
| `src/nl_dsl/__init__.py` | Create |
| `src/nl_dsl/models.py` | Create - 查询计划/步骤/结果 数据模型 |
| `src/nl_dsl/prompts.py` | Create - DSL 生成 / 规划 / 反思 prompt |
| `src/nl_dsl/dsl_validator.py` | Create - DSL 安全校验器 |
| `src/nl_dsl/dsl_generator.py` | Create - NL→DSL 生成器 |
| `src/nl_dsl/self_reflection_executor.py` | Create - 自反思执行器 |
| `src/nl_dsl/result_formatter.py` | Create - 结果格式化 + 呈现类型判断 |
| `src/intent/report_intent.py` | Modify - 去硬编码能力校验 + 加路由判断 |
| `src/graph/nodes.py` | Modify - 新增 nl_dsl_node + 改造 report_intent_node |
| `src/graph/builder.py` | Modify - 新增 nl_dsl 节点和路由 |
| `src/graph/state.py` | Modify - 新增 state 字段 |
| `src/agents/reporter_agent.py` | Modify - 支持 display_type |
| `tests/test_dsl_validator.py` | Create |
| `tests/test_result_formatter.py` | Create |
| `tests/test_schema_rag_sync.py` | Create |
| `tests/test_nl_dsl_generator.py` | Create |
| `tests/test_nl_dsl_node.py` | Create |

---

## Phase 1: 基础能力（任务 1-10）

### Task 1: Schema RAG 数据模型与检索器

**Files:**
- Create: `backend/src/schema_rag/__init__.py`
- Create: `backend/src/schema_rag/models.py`
- Create: `backend/src/schema_rag/retriever.py`
- Test: `backend/tests/test_schema_rag_sync.py`

**Interfaces:**
- Consumes: 现有 `RagDocument` / `RagChunk` ORM 模型（`src/rag/models.py`），现有 `VectorRetriever`（`src/rag/retriever.py`）
- Produces: `SchemaRetriever.search(query, doc_type='schema') -> List[RetrievalResult]`

**Design Notes:**
- Schema RAG 复用现有 RAG 基础设施（PostgreSQL + pgvector + VectorRetriever）
- 通过 `doc_type = 'schema'` 区分，不新增表
- 文档按三级组织：index级 / field级 / pattern级，内容以 Markdown 格式写入 content 字段，向量化后检索
- `SchemaRetriever` 是对 `VectorRetriever` 的薄封装，固定 `doc_type='schema'`

- [ ] **Step 1: 创建 schema_rag 包 __init__.py**

```python
# src/schema_rag/__init__.py
from .retriever import SchemaRetriever, get_schema_retriever

__all__ = ["SchemaRetriever", "get_schema_retriever"]
```

- [ ] **Step 2: 写 SchemaRetriever 测试（验证失败）**

文件：`backend/tests/test_schema_rag_sync.py`

```python
"""Schema RAG 同步与检索测试"""
import pytest
from unittest.mock import MagicMock, patch
from src.schema_rag.retriever import SchemaRetriever, get_schema_retriever


class TestSchemaRetriever:
    def test_singleton_returns_same_instance(self):
        r1 = get_schema_retriever()
        r2 = get_schema_retriever()
        assert r1 is r1  # 基本存在性检查

    def test_search_filters_by_schema_doc_type(self):
        """SchemaRetriever.search 内部调用 VectorRetriever 时 doc_type='schema'"""
        with patch('src.schema_rag.retriever.VectorRetriever') as MockVR:
            mock_vr = MagicMock()
            mock_vr.retrieve.return_value = []
            MockVR.return_value = mock_vr

            mock_db = MagicMock()
            sr = SchemaRetriever(top_k=5)
            sr.search("消耗指标", mock_db)

            # 验证调用时 doc_type='schema'
            mock_vr.retrieve.assert_called_once()
            call_kwargs = mock_vr.retrieve.call_args
            assert call_kwargs[1].get('doc_type') == 'schema'
```

- [ ] **Step 3: 运行测试验证失败**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_schema_rag_sync.py -v 2>&1 | head -30
```
Expected: FAIL (ModuleNotFoundError 或 ImportError)

- [ ] **Step 4: 实现 SchemaRetriever**

文件：`backend/src/schema_rag/retriever.py`

```python
"""Schema RAG 检索器
复用现有 VectorRetriever，固定 doc_type='schema'
"""
import logging
from src.rag.retriever import VectorRetriever, RetrievalResult

logger = logging.getLogger(__name__)

_schema_retriever_instance = None


class SchemaRetriever:
    """Schema 元数据检索器
    
    在 VectorRetriever 基础上封装，固定检索 doc_type='schema' 的文档。
    支持三级检索：索引级 / 字段级 / 查询示例级。
    """

    def __init__(self, top_k: int = 10):
        self._retriever = VectorRetriever(top_k=top_k)

    def search(self, query: str, db_session=None) -> list:
        """语义检索相关的 schema 文档
        
        Args:
            query: 用户问题或检索关键词
            db_session: 数据库会话（若为 None 则内部创建）
            
        Returns:
            List[RetrievalResult]: 按相似度排序的检索结果
        """
        if db_session is None:
            from src.rag.database import get_db
            db_session = next(get_db())
            close_after = True
        else:
            close_after = False

        try:
            results = self._retriever.retrieve(
                query=query,
                db_session=db_session,
                doc_type="schema",
            )
            logger.info(f"Schema RAG检索: query='{query[:50]}', 命中={len(results)}条")
            return results
        finally:
            if close_after:
                db_session.close()

    def search_by_index(self, query: str, index_name: str, db_session=None) -> list:
        """检索指定索引下的 schema 文档（字段级 + 示例级）
        
        在 query 前拼接索引名作为上下文，提升检索精准度。
        """
        enhanced_query = f"在{index_name}索引中，{query}"
        return self.search(enhanced_query, db_session)


def get_schema_retriever() -> SchemaRetriever:
    """获取 SchemaRetriever 单例"""
    global _schema_retriever_instance
    if _schema_retriever_instance is None:
        _schema_retriever_instance = SchemaRetriever()
    return _schema_retriever_instance
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_schema_rag_sync.py::TestSchemaRetriever -v 2>&1 | tail -20
```
Expected: 2 passed

- [ ] **Step 6: 验证语法并提交**

```bash
cd /Users/simon/AL/DataAgent && python -m py_compile backend/src/schema_rag/retriever.py backend/src/schema_rag/__init__.py
git add backend/src/schema_rag/__init__.py backend/src/schema_rag/retriever.py backend/tests/test_schema_rag_sync.py
git commit -m "feat: add Schema RAG retriever (reuses VectorRetriever with doc_type='schema')"
```

---

### Task 2: Schema RAG YAML 配置与同步脚本

**Files:**
- Create: `backend/src/schema_rag/sync.py`
- Create: `backend/src/schema_rag/schemas/ad_stat_data.yaml`
- Create: `backend/src/schema_rag/schemas/ad_stat_audience.yaml`
- Create: `backend/src/schema_rag/schemas/advertiser.yaml`
- Create: `backend/src/schema_rag/schemas/adgroup.yaml`
- Create: `backend/src/schema_rag/schemas/query_patterns.yaml`
- Modify: `backend/src/schema_rag/__init__.py` (导出 sync 函数)
- Test: `backend/tests/test_schema_rag_sync.py` (增加同步测试)

**Interfaces:**
- Consumes: `RagDocument` ORM, `EmbeddingProvider`, `MarkdownSplitter`
- Produces: `SchemaSyncer.sync_all() -> (int, int)` 成功数/失败数；`sync_from_yaml(file_path) -> bool`

- [ ] **Step 1: 编写同步器测试（验证失败）**

在 `backend/tests/test_schema_rag_sync.py` 末尾追加：

```python
class TestSchemaSyncer:
    def test_index_yaml_to_markdown(self):
        """索引级 YAML 转 Markdown 文档"""
        from src.schema_rag.sync import _index_yaml_to_markdown
        yaml_data = {
            "index_name": "ad_stat_data",
            "description": "广告报表事实表",
            "supported_analysis_types": ["trend", "comparison"],
            "hierarchy_fields": [
                {"advertiser_id": "广告主ID"},
                {"campaign_id": "计划ID"},
            ],
            "time_field": "data_date",
            "metric_field": "data_value",
            "metric_type_field": "data_type",
        }
        md = _index_yaml_to_markdown(yaml_data)
        assert "# 索引: ad_stat_data" in md
        assert "广告报表事实表" in md
        assert "trend" in md
        assert "advertiser_id" in md

    def test_field_yaml_to_markdown(self):
        """字段级 YAML 转 Markdown 文档"""
        from src.schema_rag.sync import _field_yaml_to_markdown
        yaml_data = {
            "field_name": "data_type",
            "index": "ad_stat_data",
            "field_type": "integer",
            "description": "指标类型编码",
            "enumeration": [
                {"value": 1, "label": "曝光", "alias": ["曝光量", "impressions"]},
                {"value": 3, "label": "消耗", "alias": ["花费", "cost"], "note": "单位：元"},
            ],
        }
        md = _field_yaml_to_markdown(yaml_data)
        assert "data_type" in md
        assert "指标类型编码" in md
        assert "曝光" in md
        assert "消耗" in md
        assert "单位：元" in md
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_schema_rag_sync.py::TestSchemaSyncer -v 2>&1 | tail -20
```
Expected: FAIL (cannot import)

- [ ] **Step 3: 编写 YAML 转 Markdown 辅助函数**

文件：`backend/src/schema_rag/sync.py`

```python
"""Schema RAG 同步器
从 YAML 配置文件读取 schema 元数据，转成 Markdown 文档，
生成 embedding 后存入 PostgreSQL（复用现有 RAG 基础设施）。
"""
import os
import logging
import yaml
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

SCHEMAS_DIR = Path(__file__).parent / "schemas"


def _index_yaml_to_markdown(data: dict) -> str:
    """索引级 YAML 转 Markdown 文档"""
    lines = [f"# 索引: {data['index_name']}", ""]
    lines.append(f"## 描述")
    lines.append(data.get("description", ""))
    lines.append("")
    if data.get("supported_analysis_types"):
        lines.append("## 支持的分析类型")
        for t in data["supported_analysis_types"]:
            lines.append(f"- {t}")
        lines.append("")
    if data.get("hierarchy_fields"):
        lines.append("## 层级字段（从上到下）")
        for item in data["hierarchy_fields"]:
            for field_name, desc in item.items():
                lines.append(f"- **{field_name}**: {desc}")
        lines.append("")
    if data.get("time_field"):
        lines.append(f"- 时间字段: `{data['time_field']}`")
    if data.get("metric_field"):
        lines.append(f"- 指标值字段: `{data['metric_field']}`")
    if data.get("metric_type_field"):
        lines.append(f"- 指标类型字段: `{data['metric_type_field']}`")
    lines.append("")
    return "\n".join(lines)


def _field_yaml_to_markdown(data: dict) -> str:
    """字段级 YAML 转 Markdown 文档"""
    lines = [
        f"# 字段: {data['field_name']}",
        "",
        f"- 所属索引: `{data.get('index', '')}`",
        f"- 字段类型: {data.get('field_type', '')}",
        "",
        "## 描述",
        data.get("description", ""),
        "",
    ]
    if data.get("enumeration"):
        lines.append("## 枚举值")
        lines.append("")
        lines.append("| 值 | 名称 | 别名 | 备注 |")
        lines.append("|----|------|------|------|")
        for enum in data["enumeration"]:
            aliases = ", ".join(enum.get("alias", []))
            note = enum.get("note", "")
            lines.append(f"| {enum['value']} | {enum['label']} | {aliases} | {note} |")
        lines.append("")
    return "\n".join(lines)


def _pattern_yaml_to_markdown(data: dict) -> str:
    """查询示例级 YAML 转 Markdown 文档"""
    lines = [
        f"# 查询模式: {data['pattern_name']}",
        "",
        "## 描述",
        data.get("description", ""),
        "",
        "## 用户问题示例",
        f"\"{data.get('user_query_example', '')}\"",
        "",
        f"- 涉及索引: `{data.get('index', '')}`",
        "",
    ]
    if data.get("dsl_template_summary"):
        lines.append("## DSL 要点")
        lines.append(data["dsl_template_summary"])
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_schema_rag_sync.py::TestSchemaSyncer -v 2>&1 | tail -20
```
Expected: 2 passed

- [ ] **Step 5: 编写同步主逻辑**

在 `sync.py` 末尾追加：

```python
def _load_yaml_file(file_path: Path) -> dict:
    """加载 YAML 文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _yaml_to_documents(yaml_data: dict, file_path: Path) -> List[Tuple[str, str, str]]:
    """
    将一个 YAML 文件中的 schema 定义转成 (title, doc_type, content_markdown) 列表
    
    YAML 顶层 key 决定文档类型：
    - index: 索引级文档
    - fields: 字段级文档列表（多个）
    - patterns: 查询示例级文档列表（多个）
    """
    docs = []
    
    if "index" in yaml_data:
        idx = yaml_data["index"]
        title = f"索引: {idx['index_name']}"
        content = _index_yaml_to_markdown(idx)
        docs.append((title, "schema", content))
    
    if "fields" in yaml_data:
        for field in yaml_data["fields"]:
            title = f"字段: {field['field_name']} ({field.get('index', '')})"
            content = _field_yaml_to_markdown(field)
            docs.append((title, "schema", content))
    
    if "patterns" in yaml_data:
        for pattern in yaml_data["patterns"]:
            title = f"查询模式: {pattern['pattern_name']}"
            content = _pattern_yaml_to_markdown(pattern)
            docs.append((title, "schema", content))
    
    return docs


class SchemaSyncer:
    """Schema RAG 同步器
    
    从 YAML 配置文件读取 schema 定义，生成 Markdown 文档和 embedding，
    存入 PostgreSQL 的 RAG 表（doc_type='schema'）。
    """

    def __init__(self):
        from src.rag.embedding import get_embedding_provider
        from src.rag.database import get_db
        self._embedding_provider = get_embedding_provider()
        self._get_db = get_db

    def sync_all(self, schemas_dir: Path = None) -> Tuple[int, int]:
        """同步 schemas 目录下所有 YAML 文件
        
        Returns:
            (成功文档数, 失败文档数)
        """
        if schemas_dir is None:
            schemas_dir = SCHEMAS_DIR
        
        success = 0
        failed = 0
        
        yaml_files = list(schemas_dir.glob("*.yaml")) + list(schemas_dir.glob("*.yml"))
        logger.info(f"Schema同步开始: 目录={schemas_dir}, 文件数={len(yaml_files)}")
        
        db = next(self._get_db())
        try:
            for yaml_file in yaml_files:
                try:
                    count = self._sync_single_file(yaml_file, db)
                    success += count
                except Exception as e:
                    logger.error(f"Schema同步失败: 文件={yaml_file.name}, error={e}")
                    failed += 1
        finally:
            db.close()
        
        logger.info(f"Schema同步完成: 成功={success}, 失败={failed}")
        return success, failed

    def _sync_single_file(self, file_path: Path, db) -> int:
        """同步单个 YAML 文件，返回成功写入的文档数"""
        yaml_data = _load_yaml_file(file_path)
        documents = _yaml_to_documents(yaml_data, file_path)
        
        from src.rag.models import RagDocument, RagChunk
        from sqlalchemy import select
        import hashlib
        import uuid
        
        count = 0
        for title, doc_type, content in documents:
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            file_path_str = f"schema://{title}"
            
            # 检查是否已存在且未变
            existing = db.execute(
                select(RagDocument).where(RagDocument.file_path == file_path_str)
            ).scalar_one_or_none()
            
            if existing and existing.chunks and existing.chunks[0].content_hash == content_hash:
                logger.debug(f"Schema文档未变更，跳过: {title}")
                count += 1
                continue
            
            # 生成 embedding
            embedding = self._embedding_provider.embed(content)
            
            if existing:
                # 更新
                existing.title = title
                existing.is_active = True
                existing.chunks[0].content = content
                existing.chunks[0].content_hash = content_hash
                existing.chunks[0].embedding = embedding
            else:
                # 新建
                doc = RagDocument(
                    id=uuid.uuid4(),
                    title=title,
                    file_path=file_path_str,
                    doc_type=doc_type,
                    version="1.0",
                    is_active=True,
                )
                chunk = RagChunk(
                    id=uuid.uuid4(),
                    doc_id=doc.id,
                    chunk_index=0,
                    content=content,
                    content_hash=content_hash,
                    embedding=embedding,
                )
                db.add(doc)
                db.add(chunk)
            
            count += 1
        
        db.commit()
        logger.info(f"Schema文件同步完成: 文件={file_path.name}, 文档数={count}")
        return count


_schema_syncer_instance = None


def get_schema_syncer() -> SchemaSyncer:
    """获取 SchemaSyncer 单例"""
    global _schema_syncer_instance
    if _schema_syncer_instance is None:
        _schema_syncer_instance = SchemaSyncer()
    return _schema_syncer_instance
```

- [ ] **Step 6: 编写 ad_stat_data schema YAML**

文件：`backend/src/schema_rag/schemas/ad_stat_data.yaml`

```yaml
index:
  index_name: ad_stat_data
  description: >
    广告报表事实表，存储按天聚合的广告效果数据。
    数据为长表结构，不同指标通过 data_type 字段区分。
    支持按广告主、计划、单元、创意层级查询，支持时间范围过滤和多维度聚合。
  supported_analysis_types:
    - trend: 趋势分析（按时间维度聚合）
    - comparison: 横向对比（按实体维度对比）
    - ranking: 排名分析（Top N 实体）
    - list: 列表查询（满足条件的实体列表）
    - qa: 数值问答（单个指标值）
    - detail: 明细查询（多列明细数据）
  hierarchy_fields:
    - advertiser_id: 广告主ID（最上层）
    - campaign_id: 计划ID
    - adgroup_id: 单元ID
    - creative_id: 创意ID（最下层）
  time_field: data_date
  metric_field: data_value
  metric_type_field: data_type

fields:
  - field_name: data_date
    index: ad_stat_data
    field_type: date
    description: 数据日期，按天聚合
  - field_name: advertiser_id
    index: ad_stat_data
    field_type: integer
    description: 广告主ID
  - field_name: campaign_id
    index: ad_stat_data
    field_type: integer
    description: 广告计划ID
  - field_name: adgroup_id
    index: ad_stat_data
    field_type: integer
    description: 广告单元ID
  - field_name: creative_id
    index: ad_stat_data
    field_type: integer
    description: 创意ID
  - field_name: channel
    index: ad_stat_data
    field_type: string
    description: 投放渠道
  - field_name: industry
    index: ad_stat_data
    field_type: string
    description: 行业
  - field_name: data_type
    index: ad_stat_data
    field_type: integer
    description: 指标类型编码，用于区分不同的指标
    enumeration:
      - value: 1
        label: 曝光
        alias: [曝光量, impressions, 展示量, 展现]
      - value: 2
        label: 点击
        alias: [点击量, clicks]
      - value: 3
        label: 消耗
        alias: [花费, cost, 成本, 消费]
      - value: 4
        label: 转化
        alias: [转化量, conversions, 成交, 订单]
      - value: 5
        label: 触达
        alias: [reach, 覆盖人数, 到达]
      - value: 6
        label: 频次
        alias: [frequency, 平均频次]
        note: 存储值为实际值的100倍，使用时需除以100
  - field_name: data_value
    index: ad_stat_data
    field_type: numeric
    description: 指标数值，配合 data_type 使用
```

- [ ] **Step 7: 编写 ad_stat_audience schema YAML**

文件：`backend/src/schema_rag/schemas/ad_stat_audience.yaml`

```yaml
index:
  index_name: ad_stat_audience
  description: >
    广告受众维度统计表，存储按受众维度拆分的广告效果数据。
    受众类型包括性别、年龄、操作系统、兴趣、地域等。
  supported_analysis_types:
    - audience: 受众分布分析
    - audience_comparison: 受众对比分析
    - trend: 受众趋势分析
  hierarchy_fields:
    - advertiser_id: 广告主ID
    - campaign_id: 计划ID
    - adgroup_id: 单元ID
    - creative_id: 创意ID
  time_field: data_date
  metric_field: data_value
  metric_type_field: data_type

fields:
  - field_name: data_date
    index: ad_stat_audience
    field_type: date
    description: 数据日期
  - field_name: advertiser_id
    index: ad_stat_audience
    field_type: integer
    description: 广告主ID
  - field_name: campaign_id
    index: ad_stat_audience
    field_type: integer
    description: 计划ID
  - field_name: adgroup_id
    index: ad_stat_audience
    field_type: integer
    description: 单元ID
  - field_name: creative_id
    index: ad_stat_audience
    field_type: integer
    description: 创意ID
  - field_name: audience_type
    index: ad_stat_audience
    field_type: integer
    description: 受众类型编码
    enumeration:
      - value: 1
        label: 性别
        alias: [gender, 男女]
      - value: 2
        label: 年龄
        alias: [age, 年龄段]
      - value: 3
        label: 操作系统
        alias: [os, system, 系统]
      - value: 4
        label: 兴趣
        alias: [interest, 兴趣标签]
      - value: 5
        label: 操作系统版本
        alias: [os_version, 系统版本]
      - value: 6
        label: 国家
        alias: [country, 国家地区]
      - value: 7
        label: 城市
        alias: [city, 城市级别]
  - field_name: audience_tag_value
    index: ad_stat_audience
    field_type: integer
    description: 受众标签编码值，配合 audience_type 使用
  - field_name: data_type
    index: ad_stat_audience
    field_type: integer
    description: 指标类型编码（同 ad_stat_data）
    enumeration:
      - value: 1
        label: 曝光
        alias: [曝光量, impressions]
      - value: 2
        label: 点击
        alias: [点击量, clicks]
      - value: 3
        label: 消耗
        alias: [花费, cost]
      - value: 4
        label: 转化
        alias: [转化量, conversions]
  - field_name: data_value
    index: ad_stat_audience
    field_type: numeric
    description: 指标数值
```

- [ ] **Step 8: 编写 advertiser schema YAML**

文件：`backend/src/schema_rag/schemas/advertiser.yaml`

```yaml
index:
  index_name: advertiser
  description: >
    广告主元数据表，存储广告主基本信息。
  supported_analysis_types:
    - list: 广告主列表查询
    - qa: 广告主信息查询
  hierarchy_fields:
    - advertiser_id: 广告主ID
    - advertiser_name: 广告主名称
  time_field: null

fields:
  - field_name: advertiser_id
    index: advertiser
    field_type: integer
    description: 广告主ID
  - field_name: advertiser_name
    index: advertiser
    field_type: string
    description: 广告主名称
  - field_name: is_deleted
    index: advertiser
    field_type: integer
    description: 是否删除标记，0=正常，1=已删除
  - field_name: status
    index: advertiser
    field_type: integer
    description: 广告主状态
    enumeration:
      - value: 1
        label: 正常
      - value: 2
        label: 惩罚
      - value: 3
        label: 欠费
```

- [ ] **Step 9: 编写 adgroup schema YAML**

文件：`backend/src/schema_rag/schemas/adgroup.yaml`

```yaml
index:
  index_name: adgroup
  description: >
    广告单元元数据表，存储单元基本信息。
  supported_analysis_types:
    - list: 单元列表查询
    - qa: 单元信息查询
  hierarchy_fields:
    - ad_group_id: 单元ID
  time_field: null

fields:
  - field_name: ad_group_id
    index: adgroup
    field_type: integer
    description: 广告单元ID
  - field_name: start_time
    index: adgroup
    field_type: datetime
    description: 投放开始时间
  - field_name: end_time
    index: adgroup
    field_type: datetime
    description: 投放结束时间
```

- [ ] **Step 10: 编写查询示例 YAML**

文件：`backend/src/schema_rag/schemas/query_patterns.yaml`

```yaml
patterns:
  - pattern_name: 按天聚合消耗趋势
    description: 查询某个广告主一段时间内的每日消耗趋势
    index: ad_stat_data
    user_query_example: "广告主6最近7天的消耗趋势"
    dsl_template_summary: >
      query: bool.must 包含 advertiser_id term、data_date range、data_type=3 (消耗)
      aggs: by_date 使用 date_histogram 按天聚合，嵌套 total_value sum 聚合 data_value

  - pattern_name: 按实体分组对比
    description: 查询某个广告主下各计划/单元的指标对比
    index: ad_stat_data
    user_query_example: "广告主6各计划的消耗对比"
    dsl_template_summary: >
      query: bool.must 包含 advertiser_id term、data_date range、data_type 过滤
      aggs: by_entity 使用 terms 按 campaign_id/adgroup_id 聚合，
            嵌套各指标的 filter+sum 聚合（注意：因长表结构，每个指标用 filter agg + sum agg）

  - pattern_name: Top N 排名
    description: 按指标排序取 Top N 实体
    index: ad_stat_data
    user_query_example: "消耗Top 10的计划"
    dsl_template_summary: >
      query: bool.must 时间范围 + advertiser_id + data_type
      aggs: by_entity terms 聚合，size=N，order 按指标值 desc 排序

  - pattern_name: 聚合后过滤 (having)
    description: 按某指标聚合后过滤满足条件的实体
    index: ad_stat_data
    user_query_example: "消耗大于10的计划列表"
    dsl_template_summary: >
      query: bool.must 时间范围 + advertiser_id + data_type
      aggs: by_entity terms 聚合，嵌套 metric_sum sum 聚合，
            再嵌套 having_filter bucket_selector pipeline agg 过滤 sum > 阈值

  - pattern_name: 受众分布
    description: 按受众维度统计指标分布
    index: ad_stat_audience
    user_query_example: "广告主6的性别分布"
    dsl_template_summary: >
      query: bool.must advertiser_id + data_date range + audience_type + data_type
      aggs: by_audience terms 按 audience_tag_value 聚合，嵌套 metric_sum sum 聚合
```

- [ ] **Step 11: 更新 __init__.py 导出**

编辑 `backend/src/schema_rag/__init__.py`：
```python
from .retriever import SchemaRetriever, get_schema_retriever
from .sync import SchemaSyncer, get_schema_syncer

__all__ = ["SchemaRetriever", "get_schema_retriever", "SchemaSyncer", "get_schema_syncer"]
```

- [ ] **Step 12: 运行全部测试**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_schema_rag_sync.py -v 2>&1 | tail -30
```
Expected: 4 passed

- [ ] **Step 13: 验证语法并提交**

```bash
cd /Users/simon/AL/DataAgent && python -m py_compile backend/src/schema_rag/sync.py
git add backend/src/schema_rag/ backend/tests/test_schema_rag_sync.py
git commit -m "feat: add Schema RAG sync + YAML schema configs for all 4 ES indices"
```

---

### Task 3: DSL 安全校验器

**Files:**
- Create: `backend/src/nl_dsl/__init__.py`
- Create: `backend/src/nl_dsl/dsl_validator.py`
- Test: `backend/tests/test_dsl_validator.py`

**Interfaces:**
- Consumes: dict (ES DSL), index_name, allowed_indices set
- Produces: `DslValidator.validate(dsl, index_name) -> ValidationResult`
  - `ValidationResult.ok: bool`
  - `ValidationResult.errors: List[str]`
  - `ValidationResult.warnings: List[str]`

- [ ] **Step 1: 创建 nl_dsl 包 __init__.py**

```python
# src/nl_dsl/__init__.py
from .dsl_validator import DslValidator, ValidationResult

__all__ = ["DslValidator", "ValidationResult"]
```

- [ ] **Step 2: 写测试（验证失败）**

文件：`backend/tests/test_dsl_validator.py`

```python
"""DSL 安全校验器测试"""
import pytest
from src.nl_dsl.dsl_validator import DslValidator, ValidationResult


class TestDslValidator:
    def test_valid_simple_query_passes(self):
        """合法的简单查询应该通过"""
        validator = DslValidator(allowed_indices={"ad_stat_data"})
        dsl = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"advertiser_id": 6}},
                        {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
                        {"term": {"data_type": 3}},
                    ]
                }
            },
            "size": 10,
        }
        result = validator.validate(dsl, "ad_stat_data")
        assert result.ok is True
        assert result.errors == []

    def test_missing_advertiser_filter_fails(self):
        """缺少 advertiser_id 过滤应该失败"""
        validator = DslValidator(allowed_indices={"ad_stat_data"})
        dsl = {
            "query": {
                "bool": {
                    "must": [
                        {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
                    ]
                }
            },
            "size": 10,
        }
        result = validator.validate(dsl, "ad_stat_data")
        assert result.ok is False
        assert any("advertiser_id" in e for e in result.errors)

    def test_missing_date_filter_fails(self):
        """缺少时间范围过滤应该失败"""
        validator = DslValidator(allowed_indices={"ad_stat_data"})
        dsl = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"advertiser_id": 6}},
                    ]
                }
            },
            "size": 10,
        }
        result = validator.validate(dsl, "ad_stat_data")
        assert result.ok is False
        assert any("时间" in e or "date" in e.lower() for e in result.errors)

    def test_index_not_in_whitelist_fails(self):
        """索引不在白名单中应该失败"""
        validator = DslValidator(allowed_indices={"ad_stat_data"})
        dsl = {
            "query": {"bool": {"must": [
                {"term": {"advertiser_id": 6}},
                {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
            ]}},
            "size": 10,
        }
        result = validator.validate(dsl, "unknown_index")
        assert result.ok is False
        assert any("白名单" in e or "whitelist" in e.lower() for e in result.errors)

    def test_script_field_fails(self):
        """包含 script_fields 应该失败"""
        validator = DslValidator(allowed_indices={"ad_stat_data"})
        dsl = {
            "query": {"bool": {"must": [
                {"term": {"advertiser_id": 6}},
                {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
            ]}},
            "script_fields": {"calc": {"script": {"source": "doc['data_value'].value * 2"}}},
            "size": 10,
        }
        result = validator.validate(dsl, "ad_stat_data")
        assert result.ok is False
        assert any("script" in e.lower() for e in result.errors)

    def test_size_exceeds_limit_gets_warning(self):
        """size 超过上限应该有警告（自动截断）"""
        validator = DslValidator(allowed_indices={"ad_stat_data"}, max_size=1000)
        dsl = {
            "query": {"bool": {"must": [
                {"term": {"advertiser_id": 6}},
                {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
            ]}},
            "size": 5000,
        }
        result = validator.validate(dsl, "ad_stat_data")
        # size超限是warning不是error（校验器只报告，执行器会截断）
        assert any("size" in w.lower() for w in result.warnings)

    def test_invalid_json_fails(self):
        """非 dict 结构应该失败"""
        validator = DslValidator(allowed_indices={"ad_stat_data"})
        result = validator.validate("not a dict", "ad_stat_data")
        assert result.ok is False

    def test_nested_agg_size_check(self):
        """聚合 size 超限应该有警告"""
        validator = DslValidator(allowed_indices={"ad_stat_data"}, max_agg_size=500)
        dsl = {
            "query": {"bool": {"must": [
                {"term": {"advertiser_id": 6}},
                {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
            ]}},
            "aggs": {
                "by_campaign": {
                    "terms": {"field": "campaign_id", "size": 2000},
                    "aggs": {"total": {"sum": {"field": "data_value"}}},
                }
            },
            "size": 0,
        }
        result = validator.validate(dsl, "ad_stat_data")
        assert any("agg" in w.lower() or "size" in w.lower() for w in result.warnings)
```

- [ ] **Step 3: 运行测试验证失败**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_dsl_validator.py -v 2>&1 | tail -30
```
Expected: FAIL (cannot import)

- [ ] **Step 4: 实现 DslValidator**

文件：`backend/src/nl_dsl/dsl_validator.py`

```python
"""DSL 安全校验器

四层防护中的第2层：DSL 结构校验。
对生成的 ES DSL 进行静态检查，确保只读、有必要过滤、不超限。
"""
import logging
from typing import List, Set, Optional

logger = logging.getLogger(__name__)


class ValidationResult:
    """校验结果"""

    def __init__(self):
        self.ok: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_error(self, msg: str):
        self.ok = False
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def __repr__(self):
        return f"ValidationResult(ok={self.ok}, errors={self.errors}, warnings={self.warnings})"


class DslValidator:
    """ES DSL 安全校验器

    校验规则：
    1. 索引白名单校验
    2. 必须包含 advertiser_id 过滤
    3. 必须包含时间范围过滤
    4. 禁止 script / script_fields
    5. size / agg size 上限检查（warning 级别，执行器负责截断）
    6. DSL 结构合法性检查（必须是 dict）
    """

    # 禁止的顶层 key（写操作 / 脚本）
    FORBIDDEN_TOP_LEVEL_KEYS = {
        "script", "script_fields", "update", "doc", "upsert",
        "source_to_create", "_source",
    }

    # 禁止的 query 类型（写操作相关）
    FORBIDDEN_QUERY_KEYS = {
        "script",
    }

    def __init__(
        self,
        allowed_indices: Set[str] = None,
        max_size: int = 1000,
        max_agg_size: int = 500,
        require_advertiser_filter: bool = True,
        require_time_filter: bool = True,
    ):
        self.allowed_indices = allowed_indices or set()
        self.max_size = max_size
        self.max_agg_size = max_agg_size
        self.require_advertiser_filter = require_advertiser_filter
        self.require_time_filter = require_time_filter

    def validate(self, dsl: dict, index_name: str) -> ValidationResult:
        """校验 DSL
        
        Args:
            dsl: ES DSL 字典
            index_name: 要查询的索引名
            
        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # 1. 结构合法性
        if not isinstance(dsl, dict):
            result.add_error("DSL 不是合法的字典对象")
            return result

        # 2. 索引白名单
        if self.allowed_indices and index_name not in self.allowed_indices:
            result.add_error(
                f"索引 '{index_name}' 不在查询白名单中。"
                f"允许的索引: {sorted(self.allowed_indices)}"
            )

        # 3. 禁止的顶层 key
        for key in self.FORBIDDEN_TOP_LEVEL_KEYS:
            if key in dsl:
                result.add_error(f"禁止使用 '{key}'，不允许脚本或写操作")

        # 4. query 部分校验
        query = dsl.get("query", {})
        if query:
            self._check_query_forbidden_keys(query, result)
            if self.require_advertiser_filter:
                self._check_advertiser_filter(query, result)
            if self.require_time_filter:
                self._check_time_filter(query, result)

        # 5. size 上限
        size = dsl.get("size", 10)
        if isinstance(size, int) and size > self.max_size:
            result.add_warning(
                f"size={size} 超过上限 {self.max_size}，将被自动截断"
            )

        # 6. aggs size 上限
        aggs = dsl.get("aggs") or dsl.get("aggregations")
        if aggs:
            self._check_agg_sizes(aggs, result)

        logger.info(
            f"DSL校验: 索引={index_name}, ok={result.ok}, "
            f"错误数={len(result.errors)}, 警告数={len(result.warnings)}"
        )
        return result

    def _check_query_forbidden_keys(self, query: dict, result: ValidationResult):
        """检查 query 中是否有禁用的 key"""
        if not isinstance(query, dict):
            return
        for key in query:
            if key in self.FORBIDDEN_QUERY_KEYS:
                result.add_error(f"query 中禁止使用 '{key}'")
                return
            # 递归检查 bool 的各子句
            if key == "bool" and isinstance(query[key], dict):
                for clause in ["must", "must_not", "should", "filter"]:
                    items = query[key].get(clause, [])
                    if isinstance(items, list):
                        for item in items:
                            self._check_query_forbidden_keys(item, result)

    def _check_advertiser_filter(self, query: dict, result: ValidationResult):
        """检查是否包含 advertiser_id 过滤"""
        found = self._find_field_in_query(query, "advertiser_id")
        if not found:
            result.add_error("缺少 advertiser_id 过滤条件，不允许全平台查询")

    def _check_time_filter(self, query: dict, result: ValidationResult):
        """检查是否包含时间范围过滤"""
        found = self._find_field_in_query(query, "data_date")
        if not found:
            result.add_error("缺少 data_date 时间范围过滤条件")

    def _find_field_in_query(self, query: dict, field_name: str) -> bool:
        """递归查找 query 中是否包含某个字段的过滤"""
        if not isinstance(query, dict):
            return False

        # term / terms
        for key in ["term", "terms"]:
            if key in query and isinstance(query[key], dict):
                if field_name in query[key]:
                    return True

        # range
        if "range" in query and isinstance(query["range"], dict):
            if field_name in query["range"]:
                return True

        # bool 子句
        if "bool" in query and isinstance(query["bool"], dict):
            for clause in ["must", "must_not", "should", "filter"]:
                items = query["bool"].get(clause, [])
                if isinstance(items, list):
                    for item in items:
                        if self._find_field_in_query(item, field_name):
                            return True

        # nested
        if "nested" in query and isinstance(query["nested"], dict):
            return self._find_field_in_query(query["nested"].get("query", {}), field_name)

        return False

    def _check_agg_sizes(self, aggs: dict, result: ValidationResult):
        """递归检查所有 terms agg 的 size 是否超限"""
        if not isinstance(aggs, dict):
            return
        for agg_name, agg_body in aggs.items():
            if not isinstance(agg_body, dict):
                continue
            # terms agg
            if "terms" in agg_body and isinstance(agg_body["terms"], dict):
                size = agg_body["terms"].get("size", 10)
                if isinstance(size, int) and size > self.max_agg_size:
                    result.add_warning(
                        f"聚合 '{agg_name}' 的 size={size} 超过上限 {self.max_agg_size}，将被自动截断"
                    )
            # 递归检查嵌套 aggs
            for nested_key in ["aggs", "aggregations"]:
                nested = agg_body.get(nested_key)
                if nested:
                    self._check_agg_sizes(nested, result)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_dsl_validator.py -v 2>&1 | tail -30
```
Expected: 8 passed

- [ ] **Step 6: 验证语法并提交**

```bash
cd /Users/simon/AL/DataAgent && python -m py_compile backend/src/nl_dsl/dsl_validator.py
git add backend/src/nl_dsl/__init__.py backend/src/nl_dsl/dsl_validator.py backend/tests/test_dsl_validator.py
git commit -m "feat: add DSL security validator (index whitelist, advertiser/time filter, script ban, size limits)"
```

---

### Task 4: 结果格式化器与呈现类型判断

**Files:**
- Create: `backend/src/nl_dsl/result_formatter.py`
- Modify: `backend/src/nl_dsl/__init__.py`
- Test: `backend/tests/test_result_formatter.py`

**Interfaces:**
- Consumes: ES response dict, display_type hint, columns hint
- Produces: `format_es_result(es_response, display_type=None) -> dict`
  - 返回: `{display_type, columns, rows, metadata}`

- [ ] **Step 1: 写测试（验证失败）**

文件：`backend/tests/test_result_formatter.py`

```python
"""结果格式化器测试"""
import pytest
from src.nl_dsl.result_formatter import ResultFormatter


class TestResultFormatter:
    def test_format_simple_hits(self):
        """格式化 _source 命中结果（列表查询）"""
        es_response = {
            "hits": {
                "total": {"value": 3, "relation": "eq"},
                "hits": [
                    {"_source": {"campaign_id": 101, "advertiser_id": 6}},
                    {"_source": {"campaign_id": 102, "advertiser_id": 6}},
                    {"_source": {"campaign_id": 103, "advertiser_id": 6}},
                ],
            }
        }
        result = ResultFormatter.format(es_response, display_type="list")
        assert result["display_type"] == "list"
        assert len(result["rows"]) == 3
        assert "campaign_id" in result["columns"]
        assert result["metadata"]["total_rows"] == 3

    def test_format_date_histogram(self):
        """格式化 date_histogram 聚合结果（趋势分析）"""
        es_response = {
            "aggregations": {
                "by_date": {
                    "buckets": [
                        {"key_as_string": "2026-01-01", "total_cost": {"value": 100}},
                        {"key_as_string": "2026-01-02", "total_cost": {"value": 200}},
                    ]
                }
            },
            "hits": {"total": {"value": 0}, "hits": []},
        }
        result = ResultFormatter.format(es_response, display_type="trend")
        assert result["display_type"] == "trend"
        assert len(result["rows"]) == 2
        assert "日期" in result["columns"] or "date" in result["columns"][0].lower()

    def test_format_terms_aggregation(self):
        """格式化 terms 聚合结果（对比/排名）"""
        es_response = {
            "aggregations": {
                "by_campaign": {
                    "buckets": [
                        {"key": 101, "doc_count": 10, "total_cost": {"value": 500}},
                        {"key": 102, "doc_count": 8, "total_cost": {"value": 300}},
                    ]
                }
            },
            "hits": {"total": {"value": 0}, "hits": []},
        }
        result = ResultFormatter.format(es_response, display_type="comparison")
        assert result["display_type"] == "comparison"
        assert len(result["rows"]) == 2

    def test_format_single_value_qa(self):
        """格式化单值结果（数值问答）"""
        es_response = {
            "aggregations": {
                "total_cost": {"value": 12345.67}
            },
            "hits": {"total": {"value": 0}, "hits": []},
        }
        result = ResultFormatter.format(es_response, display_type="qa")
        assert result["display_type"] == "qa"
        assert len(result["rows"]) >= 1

    def test_empty_result(self):
        """空结果处理"""
        es_response = {
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {},
        }
        result = ResultFormatter.format(es_response, display_type="list")
        assert result["metadata"]["total_rows"] == 0
        assert result["rows"] == []

    def test_auto_detect_display_type_hits(self):
        """自动检测呈现类型 - 命中列表 → list"""
        es_response = {
            "hits": {
                "total": {"value": 5},
                "hits": [{"_source": {"a": 1}} for _ in range(5)],
            }
        }
        result = ResultFormatter.format(es_response)
        assert result["display_type"] == "list"

    def test_auto_detect_date_histogram(self):
        """自动检测呈现类型 - date_histogram → trend"""
        es_response = {
            "aggregations": {
                "by_date": {
                    "buckets": [
                        {"key_as_string": "2026-01-01", "val": {"value": 100}},
                    ]
                }
            },
            "hits": {"total": {"value": 0}, "hits": []},
        }
        result = ResultFormatter.format(es_response)
        assert result["display_type"] == "trend"

    def test_auto_detect_terms_agg(self):
        """自动检测呈现类型 - terms 聚合 → comparison"""
        es_response = {
            "aggregations": {
                "by_entity": {
                    "buckets": [
                        {"key": "a", "val": {"value": 100}},
                        {"key": "b", "val": {"value": 200}},
                    ]
                }
            },
            "hits": {"total": {"value": 0}, "hits": []},
        }
        result = ResultFormatter.format(es_response)
        assert result["display_type"] == "comparison"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_result_formatter.py -v 2>&1 | tail -30
```
Expected: FAIL (cannot import)

- [ ] **Step 3: 实现 ResultFormatter**

文件：`backend/src/nl_dsl/result_formatter.py`

```python
"""ES 查询结果格式化器

将 ES 原始响应转成统一的中间格式，
并自动判断或按提示确定呈现类型。
"""
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class ResultFormatter:
    """ES 查询结果格式化器"""

    @classmethod
    def format(
        cls,
        es_response: dict,
        display_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """格式化 ES 响应

        Args:
            es_response: ES 原始响应字典
            display_type: 呈现类型提示，若为 None 则自动检测

        Returns:
            {
                "display_type": str,
                "columns": List[str],
                "rows": List[List[Any]],
                "metadata": {
                    "total_rows": int,
                    "has_aggregations": bool,
                }
            }
        """
        if not display_type:
            display_type = cls._detect_display_type(es_response)

        if cls._is_hits_result(es_response):
            columns, rows = cls._format_hits(es_response)
            total = cls._get_hits_total(es_response)
        elif cls._is_aggregation_result(es_response):
            columns, rows = cls._format_aggregations(es_response, display_type)
            total = len(rows)
        else:
            columns, rows = [], []
            total = 0

        return {
            "display_type": display_type,
            "columns": columns,
            "rows": rows,
            "metadata": {
                "total_rows": total,
                "has_aggregations": cls._is_aggregation_result(es_response),
            },
        }

    # ---- 检测方法 ----

    @staticmethod
    def _detect_display_type(es_response: dict) -> str:
        """自动检测呈现类型"""
        if not ResultFormatter._is_aggregation_result(es_response):
            # 纯命中 → 列表
            return "list"

        aggs = es_response.get("aggregations", {})
        # 检查是否有 date_histogram
        if ResultFormatter._has_date_histogram(aggs):
            return "trend"

        # 检查是否是 terms 聚合
        if ResultFormatter._has_terms_agg(aggs):
            # terms 聚合默认对比类型
            return "comparison"

        # 单值聚合 → QA
        if ResultFormatter._has_single_value_agg(aggs):
            return "qa"

        return "detail"

    @staticmethod
    def _is_hits_result(es_response: dict) -> bool:
        """是否是命中结果为主（非聚合查询）"""
        hits = es_response.get("hits", {})
        total = hits.get("total", 0)
        if isinstance(total, dict):
            total = total.get("value", 0)
        return total > 0 or len(hits.get("hits", [])) > 0

    @staticmethod
    def _is_aggregation_result(es_response: dict) -> bool:
        """是否是聚合结果为主"""
        aggs = es_response.get("aggregations") or es_response.get("aggregations")
        return bool(aggs)

    @staticmethod
    def _has_date_histogram(aggs: dict) -> bool:
        """递归检测是否有 date_histogram 聚合"""
        if not isinstance(aggs, dict):
            return False
        for key, val in aggs.items():
            if not isinstance(val, dict):
                continue
            if "date_histogram" in val:
                return True
            for nested_key in ["aggs", "aggregations"]:
                nested = val.get(nested_key)
                if nested and ResultFormatter._has_date_histogram(nested):
                    return True
        return False

    @staticmethod
    def _has_terms_agg(aggs: dict) -> bool:
        """递归检测是否有 terms 聚合"""
        if not isinstance(aggs, dict):
            return False
        for key, val in aggs.items():
            if not isinstance(val, dict):
                continue
            if "terms" in val:
                return True
            for nested_key in ["aggs", "aggregations"]:
                nested = val.get(nested_key)
                if nested and ResultFormatter._has_terms_agg(nested):
                    return True
        return False

    @staticmethod
    def _has_single_value_agg(aggs: dict) -> bool:
        """检测是否是单值聚合（sum/avg/count 等，无 buckets）"""
        if not isinstance(aggs, dict):
            return False
        for key, val in aggs.items():
            if not isinstance(val, dict):
                continue
            # 有 value 字段但没有 buckets → 单值
            if "value" in val and "buckets" not in val and "date_histogram" not in val and "terms" not in val:
                return True
        return False

    # ---- 格式化方法 ----

    @staticmethod
    def _format_hits(es_response: dict) -> tuple:
        """格式化命中结果为 (columns, rows)"""
        hits = es_response.get("hits", {}).get("hits", [])
        if not hits:
            return [], []

        # 收集所有字段名
        columns_set = []
        for hit in hits:
            source = hit.get("_source", {})
            for key in source.keys():
                if key not in columns_set:
                    columns_set.append(key)

        columns = columns_set
        rows = []
        for hit in hits:
            source = hit.get("_source", {})
            row = [source.get(col, "") for col in columns]
            rows.append(row)

        return columns, rows

    @staticmethod
    def _format_aggregations(es_response: dict, display_type: str) -> tuple:
        """格式化聚合结果为 (columns, rows)

        简化策略：找到第一个（最外层）有 buckets 的聚合，
        将其 buckets 拍平为表格行。
        """
        aggs = es_response.get("aggregations", {})
        if not aggs:
            return [], []

        # 找到第一个有 buckets 或 value 的聚合
        first_agg_name = list(aggs.keys())[0]
        first_agg = aggs[first_agg_name]

        if "buckets" in first_agg:
            return ResultFormatter._flatten_buckets(first_agg["buckets"], first_agg_name)
        elif "value" in first_agg:
            # 单值聚合
            return ["指标", "数值"], [[first_agg_name, first_agg["value"]]]

        return [], []

    @staticmethod
    def _flatten_buckets(buckets: list, agg_name: str) -> tuple:
        """将 buckets 拍平为 (columns, rows)

        递归一层：如果 bucket 里还有嵌套的单值子聚合，也提取出来作为列。
        """
        if not buckets:
            return [], []

        # 从第一个 bucket 推导列
        first = buckets[0]
        key_label = agg_name.replace("by_", "").replace("by", "")
        columns = [key_label]
        value_agg_names = []

        for key, val in first.items():
            if key in ("key", "key_as_string", "doc_count"):
                continue
            if isinstance(val, dict) and "value" in val:
                columns.append(key)
                value_agg_names.append(key)

        rows = []
        for bucket in buckets:
            key_val = bucket.get("key_as_string", bucket.get("key", ""))
            row = [key_val]
            for agg_name_col in value_agg_names:
                val = bucket.get(agg_name_col, {}).get("value", 0)
                row.append(val)
            rows.append(row)

        return columns, rows

    @staticmethod
    def _get_hits_total(es_response: dict) -> int:
        """获取命中总数"""
        total = es_response.get("hits", {}).get("total", 0)
        if isinstance(total, dict):
            return total.get("value", 0)
        return total
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_result_formatter.py -v 2>&1 | tail -30
```
Expected: 8 passed

- [ ] **Step 5: 更新 __init__.py**

编辑 `backend/src/nl_dsl/__init__.py`：
```python
from .dsl_validator import DslValidator, ValidationResult
from .result_formatter import ResultFormatter

__all__ = ["DslValidator", "ValidationResult", "ResultFormatter"]
```

- [ ] **Step 6: 验证语法并提交**

```bash
cd /Users/simon/AL/DataAgent && python -m py_compile backend/src/nl_dsl/result_formatter.py
git add backend/src/nl_dsl/__init__.py backend/src/nl_dsl/result_formatter.py backend/tests/test_result_formatter.py
git commit -m "feat: add ES result formatter with auto display type detection"
```

---

### Task 5: NL→DSL 生成器（含查询规划 + DSL 生成）

**Files:**
- Create: `backend/src/nl_dsl/models.py`
- Create: `backend/src/nl_dsl/prompts.py`
- Create: `backend/src/nl_dsl/dsl_generator.py`
- Modify: `backend/src/nl_dsl/__init__.py`
- Test: `backend/tests/test_nl_dsl_generator.py`

**Interfaces:**
- Consumes: `IntentLLMClient` 或兼容接口，`SchemaRetriever`，`DslValidator`
- Produces: 
  - `DslGenerator.plan_query(user_input, constraints, schema_context) -> QueryPlan`
  - `DslGenerator.generate_step(step, schema_context, prev_results, retry_info=None) -> dict` (DSL dict)

- [ ] **Step 1: 编写数据模型 models.py**

```python
"""NL→DSL 数据模型"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class QueryStep(BaseModel):
    """查询步骤"""
    step_id: str
    description: str
    index: str
    output_fields: List[str] = Field(default_factory=list)
    purpose: str = ""
    depends_on: List[str] = Field(default_factory=list)


class QueryPlan(BaseModel):
    """查询计划"""
    steps: List[QueryStep] = Field(default_factory=list)
    final_output: str = "step_1.output"

    def get_step(self, step_id: str) -> Optional[QueryStep]:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None


class RetryInfo(BaseModel):
    """重试信息（用于反思修正）"""
    attempt: int = 1  # 当前是第几次尝试（1=首次，2=第1次重试，3=第2次重试）
    failure_type: str = ""  # validation / execution / empty / abnormal
    error_message: str = ""
    previous_dsl: Optional[Dict[str, Any]] = None
    reflection: str = ""


class NlDslResult(BaseModel):
    """NL→DSL 查询结果"""
    display_type: str = "list"
    columns: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    query_context: Optional[Dict[str, Any]] = None  # 用于翻页
```

- [ ] **Step 2: 编写 prompts.py**

```python
"""NL→DSL Prompt 模板"""

QUERY_PLANNING_SYSTEM_PROMPT = """你是一个 Elasticsearch 查询规划专家。
你的任务是将用户的数据分析问题拆解成多步 ES 查询计划。

## 背景信息
- 广告数据存储在 Elasticsearch 中
- ad_stat_data: 报表事实表，长表结构，指标用 data_type 区分（1=曝光,2=点击,3=消耗,4=转化,5=触达,6=频次）
- ad_stat_audience: 受众维度统计表，多了 audience_type 和 audience_tag_value 字段
- advertiser: 广告主元数据表
- adgroup: 广告单元元数据表

## 规则
1. 每步只能查一个索引
2. 步骤之间通过 output_fields 传递数据
3. 最多 5 步
4. 每个查询必须包含 advertiser_id 过滤和时间范围过滤
5. 如果用户的问题用一步就能完成，就只规划一步
6. 简单的聚合查询（趋势、对比、排名）优先用单步聚合

## 输出格式
只输出 JSON，不要输出其他内容：
{{
  "steps": [
    {{
      "step_id": "step_1",
      "description": "步骤描述",
      "index": "ad_stat_data",
      "output_fields": ["字段名1", "字段名2"],
      "purpose": "这一步的目的"
    }}
  ],
  "final_output": "step_1.output"
}}
"""

QUERY_PLANNING_USER_PROMPT = """请为以下问题生成查询计划：

用户问题：{user_input}

已提取的约束：
- 广告主ID：{advertiser_ids}
- 时间范围：{time_range}
- 指标：{metrics}
- 分析类型：{analysis_type}

相关 Schema 信息：
{schema_context}

请输出 JSON 格式的查询计划。"""

DSL_GENERATION_SYSTEM_PROMPT = """你是一个 Elasticsearch DSL 生成专家。
你的任务是根据用户需求和 Schema 信息，生成正确的 ES 查询 DSL。

## 重要规则（必须严格遵守）
1. **只读查询**：只能生成 _search 查询，不允许任何写操作
2. **必须有 advertiser_id 过滤**：不允许全平台查询
3. **必须有时间范围过滤**：使用 data_date 字段的 range 查询
4. **不允许使用 script / script_fields / painless 脚本**
5. **size 不超过 1000**，聚合 size 不超过 500
6. **长表结构**：ad_stat_data 是长表，不同指标用 data_type 区分：
   - data_type=1: 曝光 (impressions)
   - data_type=2: 点击 (clicks)
   - data_type=3: 消耗 (cost)
   - data_type=4: 转化 (conversions)
   - data_type=5: 触达 (reach)
   - data_type=6: 频次 (frequency, 值需除以100)
7. **多指标查询**：用 filter aggregation + sum aggregation 的组合，
   每个指标一个 filter agg，嵌套 sum agg 对 data_value 求和
8. **日期直方图**：用 date_histogram agg，field=data_date，calendar_interval=day

## 输出格式
只输出 JSON 格式的 DSL，不要输出其他解释。
DSL 顶层必须包含 query 和 size/aggs 等字段。"""

DSL_GENERATION_USER_PROMPT = """请生成以下查询的 ES DSL：

## 步骤目标
{step_description}

## 输入参数
{input_params}

## 相关 Schema 信息
{schema_context}

## 查询索引
{index_name}

## 注意
- advertiser_id 过滤值：{advertiser_ids}
- 时间范围：{time_range}

请只输出 JSON 格式的 DSL。"""

REFLECTION_SYSTEM_PROMPT = """你是一个 Elasticsearch 查询调试专家。
你的任务是分析 DSL 执行失败的原因，并生成修正后的 DSL。

## 规则
1. 仔细分析错误信息，找出根本原因
2. 只修改有问题的部分，不要改动正确的部分
3. 遵守所有安全规则：只读、有 advertiser 和时间过滤、无脚本、size 不超限
4. 输出修正后的完整 DSL + 简短的修改说明

## 输出格式
只输出 JSON，不要输出其他内容：
{{
  "reflection": "修改原因的简短说明",
  "fixed_dsl": {{ ...修正后的完整 DSL... }}
}}"""

REFLECTION_USER_PROMPT = """## 原始 DSL
{previous_dsl}

## 失败类型
{failure_type}

## 错误信息
{error_message}

## 相关 Schema 信息
{schema_context}

请分析失败原因并生成修正后的 DSL。输出 JSON 格式。"""
```

- [ ] **Step 3: 编写生成器测试（验证失败）**

文件：`backend/tests/test_nl_dsl_generator.py`

```python
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
        # 首次返回错误的 DSL，反思后返回正确的
        call_count = 0
        async def mock_call(system_prompt, user_prompt, json_mode=True):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 首次生成：缺 advertiser 过滤
                return json.dumps({
                    "query": {
                        "bool": {
                            "must": [
                                {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
                            ]
                        }
                    },
                    "size": 10,
                })
            else:
                # 反思后修正
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

        # validator 首次失败，第二次通过
        validate_count = 0
        def mock_validate(dsl, index_name):
            nonlocal validate_count
            validate_count += 1
            from src.nl_dsl.dsl_validator import ValidationResult
            result = ValidationResult()
            if validate_count == 1:
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
            reflection="需要添加 advertiser_id=6 的过滤",
        )
        dsl, result = await generator.generate_step(
            step=step,
            advertiser_ids=["6"],
            time_range={"start": "2026-01-01", "end": "2026-01-31"},
            retry_info=retry_info,
        )

        # 第二次应该通过
        assert result.ok is True
        # DSL 里应该有 advertiser_id
        assert "advertiser_id" in str(dsl.get("query", {}))
```

- [ ] **Step 4: 运行测试验证失败**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_nl_dsl_generator.py -v 2>&1 | tail -30
```
Expected: FAIL (cannot import)

- [ ] **Step 5: 实现 DslGenerator**

文件：`backend/src/nl_dsl/dsl_generator.py`

```python
"""NL→DSL 生成器

包含查询规划器和 DSL 生成器两部分。
查询规划：将用户问题拆解为多步查询计划。
DSL 生成：为每个步骤生成具体的 ES DSL。
"""
import json
import logging
from typing import Optional, List, Dict, Any, Tuple

from src.config.context import truncate_log
from .models import QueryPlan, QueryStep, RetryInfo
from .prompts import (
    QUERY_PLANNING_SYSTEM_PROMPT,
    QUERY_PLANNING_USER_PROMPT,
    DSL_GENERATION_SYSTEM_PROMPT,
    DSL_GENERATION_USER_PROMPT,
    REFLECTION_SYSTEM_PROMPT,
    REFLECTION_USER_PROMPT,
)

logger = logging.getLogger(__name__)


class DslGenerator:
    """NL→DSL 生成器
    
    职责：
    1. 规划查询步骤
    2. 为每步生成 ES DSL
    3. 校验 DSL 安全性
    4. 失败时生成反思修正版 DSL
    """

    def __init__(
        self,
        llm_client=None,
        schema_retriever=None,
        validator=None,
        max_steps: int = 5,
    ):
        self._llm = llm_client
        self._schema_retriever = schema_retriever
        self._validator = validator
        self.max_steps = max_steps

    async def plan_query(
        self,
        user_input: str,
        constraints: Dict[str, Any],
    ) -> QueryPlan:
        """生成查询计划
        
        Args:
            user_input: 用户原始问题
            constraints: 已提取的约束 {advertiser_ids, time_range, metrics, analysis_type}
            
        Returns:
            QueryPlan
        """
        logger.info(f"NL→DSL查询规划开始: 用户问题='{truncate_log(user_input, 100)}'")

        # 1. 检索相关 schema
        schema_context = self._get_schema_context(user_input + " " + " ".join(constraints.get("metrics", [])))

        # 2. 调用 LLM 生成计划
        user_prompt = QUERY_PLANNING_USER_PROMPT.format(
            user_input=user_input,
            advertiser_ids=constraints.get("advertiser_ids", []),
            time_range=constraints.get("time_range", {}),
            metrics=constraints.get("metrics", []),
            analysis_type=constraints.get("analysis_type", ""),
            schema_context=schema_context[:2000],
        )

        response = await self._llm.call(
            system_prompt=QUERY_PLANNING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_mode=True,
        )

        try:
            plan_data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"查询规划解析失败: error={e}")
            # 降级：返回单步计划
            plan_data = {
                "steps": [{
                    "step_id": "step_1",
                    "description": user_input[:50],
                    "index": "ad_stat_data",
                    "output_fields": [],
                    "purpose": "单步查询",
                }],
                "final_output": "step_1.output",
            }

        plan = QueryPlan(**plan_data)
        logger.info(
            f"NL→DSL查询规划完成: 步骤数={len(plan.steps)}, "
            f"步骤=[{', '.join(s.description[:20] for s in plan.steps)}]"
        )
        return plan

    async def generate_step(
        self,
        step: QueryStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        prev_results: Optional[Dict[str, Any]] = None,
        retry_info: Optional[RetryInfo] = None,
    ) -> Tuple[Dict[str, Any], Any]:
        """生成单步的 ES DSL
        
        Args:
            step: 查询步骤
            advertiser_ids: 广告主ID列表
            time_range: 时间范围 {start, end}
            prev_results: 上一步结果
            retry_info: 重试信息（首次为 None）
            
        Returns:
            (dsl_dict, validation_result)
        """
        step_id = step.step_id
        logger.info(f"NL→DSL生成(步骤{step_id}): 索引={step.index}")

        # 1. 检索该索引的 schema
        schema_context = self._get_schema_context_for_index(step.index, step.description)

        # 2. 构建输入参数字符串
        input_params = self._build_input_params(step, advertiser_ids, time_range, prev_results)

        if retry_info and retry_info.attempt > 1:
            # 重试模式：用反思 prompt
            dsl = await self._generate_with_reflection(
                step, schema_context, input_params, retry_info
            )
        else:
            # 首次生成
            user_prompt = DSL_GENERATION_USER_PROMPT.format(
                step_description=step.description,
                input_params=input_params,
                schema_context=schema_context[:2000],
                index_name=step.index,
                advertiser_ids=advertiser_ids,
                time_range=time_range,
            )
            response = await self._llm.call(
                system_prompt=DSL_GENERATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                json_mode=True,
            )
            try:
                dsl = json.loads(response)
            except json.JSONDecodeError as e:
                logger.error(f"DSL生成解析失败(步骤{step_id}): error={e}")
                dsl = {}

        logger.info(f"NL→DSL生成(步骤{step_id}): DSL={truncate_log(json.dumps(dsl, ensure_ascii=False), 500)}")

        # 3. 安全校验
        if self._validator:
            validation_result = self._validator.validate(dsl, step.index)
        else:
            from .dsl_validator import ValidationResult
            validation_result = ValidationResult()
            validation_result.ok = True

        return dsl, validation_result

    async def _generate_with_reflection(
        self,
        step: QueryStep,
        schema_context: str,
        input_params: str,
        retry_info: RetryInfo,
    ) -> Dict[str, Any]:
        """通过反思生成修正后的 DSL"""
        user_prompt = REFLECTION_USER_PROMPT.format(
            previous_dsl=json.dumps(retry_info.previous_dsl or {}, ensure_ascii=False, indent=2),
            failure_type=retry_info.failure_type,
            error_message=retry_info.error_message,
            schema_context=schema_context[:2000],
        )
        response = await self._llm.call(
            system_prompt=REFLECTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_mode=True,
        )
        try:
            data = json.loads(response)
            fixed_dsl = data.get("fixed_dsl", {})
            reflection = data.get("reflection", "")
            logger.info(f"NL→DSL反思(步骤{step.step_id}): {truncate_log(reflection, 200)}")
            return fixed_dsl
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"反思DSL解析失败(步骤{step.step_id}): error={e}")
            return retry_info.previous_dsl or {}

    def _get_schema_context(self, query: str) -> str:
        """获取 schema 上下文文本"""
        if not self._schema_retriever:
            return ""
        try:
            results = self._schema_retriever.search(query)
            return "\n\n".join(r.content for r in results)
        except Exception as e:
            logger.error(f"Schema检索失败: error={e}")
            return ""

    def _get_schema_context_for_index(self, index_name: str, description: str) -> str:
        """获取指定索引的 schema 上下文"""
        if not self._schema_retriever:
            return ""
        try:
            results = self._schema_retriever.search_by_index(description, index_name)
            return "\n\n".join(r.content for r in results)
        except Exception as e:
            logger.error(f"Schema检索失败(索引{index_name}): error={e}")
            return ""

    @staticmethod
    def _build_input_params(
        step: QueryStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        prev_results: Optional[Dict[str, Any]],
    ) -> str:
        """构建输入参数字符串"""
        lines = [f"- 广告主ID: {advertiser_ids}"]
        if time_range:
            lines.append(f"- 时间范围: {time_range.get('start', '')} ~ {time_range.get('end', '')}")
        if step.output_fields:
            lines.append(f"- 需要输出字段: {step.output_fields}")
        if prev_results:
            lines.append(f"- 上一步结果: {json.dumps(prev_results, ensure_ascii=False)[:500]}")
        return "\n".join(lines)


_dsl_generator_instance = None


def get_dsl_generator() -> DslGenerator:
    """获取 DslGenerator 单例"""
    global _dsl_generator_instance
    if _dsl_generator_instance is None:
        from src.intent.llm_client import IntentLLMClient
        from .dsl_validator import DslValidator
        from .retriever import get_schema_retriever

        llm_client = IntentLLMClient()
        schema_retriever = get_schema_retriever()
        # 默认白名单索引
        allowed_indices = {"ad_stat_data", "ad_stat_audience", "advertiser", "adgroup"}
        validator = DslValidator(allowed_indices=allowed_indices)

        _dsl_generator_instance = DslGenerator(
            llm_client=llm_client,
            schema_retriever=schema_retriever,
            validator=validator,
        )
    return _dsl_generator_instance
```

- [ ] **Step 6: 运行测试验证通过**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_nl_dsl_generator.py -v 2>&1 | tail -30
```
Expected: 3 passed

- [ ] **Step 7: 更新 __init__.py 并提交**

```python
# src/nl_dsl/__init__.py
from .dsl_validator import DslValidator, ValidationResult
from .result_formatter import ResultFormatter
from .models import QueryPlan, QueryStep, RetryInfo, NlDslResult
from .dsl_generator import DslGenerator, get_dsl_generator

__all__ = [
    "DslValidator", "ValidationResult",
    "ResultFormatter",
    "QueryPlan", "QueryStep", "RetryInfo", "NlDslResult",
    "DslGenerator", "get_dsl_generator",
]
```

```bash
cd /Users/simon/AL/DataAgent && python -m py_compile backend/src/nl_dsl/dsl_generator.py backend/src/nl_dsl/models.py backend/src/nl_dsl/prompts.py
git add backend/src/nl_dsl/ backend/tests/test_nl_dsl_generator.py
git commit -m "feat: add NL->DSL generator with query planning and reflection retry"
```

---

### Task 6: 自反思执行器

**Files:**
- Create: `backend/src/nl_dsl/self_reflection_executor.py`
- Modify: `backend/src/nl_dsl/__init__.py`
- Test: `backend/tests/test_nl_dsl_generator.py` (增加执行器测试)

**Interfaces:**
- Consumes: `DslGenerator`, ES client, `ResultFormatter`
- Produces: `SelfReflectionExecutor.execute_plan(plan, constraints, display_type_hint) -> NlDslResult`

- [ ] **Step 1: 编写执行器测试（验证失败）**

在 `backend/tests/test_nl_dsl_generator.py` 末尾追加：

```python
class TestSelfReflectionExecutor:
    @pytest.mark.asyncio
    async def test_execute_single_step_success(self):
        """单步查询执行成功"""
        from unittest.mock import MagicMock, AsyncMock
        from src.nl_dsl.self_reflection_executor import SelfReflectionExecutor
        from src.nl_dsl.models import QueryPlan, QueryStep

        # mock ES 客户端
        mock_es = MagicMock()
        mock_es.search.return_value = {
            "hits": {"total": {"value": 2, "relation": "eq"}, "hits": [
                {"_source": {"campaign_id": 101, "advertiser_id": 6}},
                {"_source": {"campaign_id": 102, "advertiser_id": 6}},
            ]},
            "aggregations": {},
        }

        # mock generator
        mock_generator = MagicMock()
        mock_generator.generate_step = AsyncMock(return_value=(
            {"query": {"bool": {"must": [
                {"term": {"advertiser_id": 6}},
                {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
            ]}}, "size": 10},
            MagicMock(ok=True, errors=[], warnings=[]),
        ))

        executor = SelfReflectionExecutor(
            es_client=mock_es,
            dsl_generator=mock_generator,
        )

        plan = QueryPlan(steps=[
            QueryStep(step_id="step_1", description="test", index="ad_stat_data",
                      output_fields=["campaign_id"], purpose="test")
        ], final_output="step_1.output")

        result = await executor.execute_plan(
            plan=plan,
            advertiser_ids=["6"],
            time_range={"start": "2026-01-01", "end": "2026-01-31"},
        )

        assert result.display_type == "list"
        assert result.metadata["total_rows"] == 2

    @pytest.mark.asyncio
    async def test_execute_with_validation_retry(self):
        """校验失败后反思重试，最终成功"""
        from unittest.mock import MagicMock, AsyncMock
        from src.nl_dsl.self_reflection_executor import SelfReflectionExecutor
        from src.nl_dsl.dsl_validator import ValidationResult

        # 首次校验失败，反思后成功
        gen_call_count = 0
        async def mock_generate_step(step, advertiser_ids, time_range, prev_results=None, retry_info=None):
            nonlocal gen_call_count
            gen_call_count += 1
            from src.nl_dsl.models import RetryInfo
            if gen_call_count == 1:
                # 首次：校验失败的 DSL
                dsl = {"query": {"bool": {"must": [
                    {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
                ]}}, "size": 10}
                vr = ValidationResult()
                vr.add_error("缺少 advertiser_id 过滤")
                return dsl, vr
            else:
                # 反思后：正确的 DSL
                dsl = {"query": {"bool": {"must": [
                    {"term": {"advertiser_id": 6}},
                    {"range": {"data_date": {"gte": "2026-01-01", "lte": "2026-01-31"}}},
                ]}}, "size": 10}
                vr = ValidationResult()
                return dsl, vr

        mock_generator = MagicMock()
        mock_generator.generate_step = mock_generate_step

        mock_es = MagicMock()
        mock_es.search.return_value = {
            "hits": {"total": {"value": 1}, "hits": [{"_source": {"id": 1}}]},
            "aggregations": {},
        }

        executor = SelfReflectionExecutor(
            es_client=mock_es,
            dsl_generator=mock_generator,
            max_attempts=3,
        )

        from src.nl_dsl.models import QueryPlan, QueryStep
        plan = QueryPlan(steps=[
            QueryStep(step_id="step_1", description="test", index="ad_stat_data",
                      output_fields=[], purpose="test")
        ], final_output="step_1.output")

        result = await executor.execute_plan(
            plan=plan,
            advertiser_ids=["6"],
            time_range={"start": "2026-01-01", "end": "2026-01-31"},
        )

        # 应该成功（经过 1 次重试）
        assert result.metadata["total_rows"] == 1
        assert result.metadata["retries"] == 1
        assert gen_call_count == 2  # 首次 + 1次反思生成

    @pytest.mark.asyncio
    async def test_execute_all_attempts_fail(self):
        """所有尝试都失败，返回失败结果"""
        from unittest.mock import MagicMock, AsyncMock
        from src.nl_dsl.self_reflection_executor import SelfReflectionExecutor
        from src.nl_dsl.dsl_validator import ValidationResult
        from src.nl_dsl.models import RetryInfo

        # 始终失败
        async def mock_generate_step(step, advertiser_ids, time_range, prev_results=None, retry_info=None):
            dsl = {"query": {"bool": {"must": []}}, "size": 10}
            vr = ValidationResult()
            vr.add_error("缺少 advertiser_id 过滤")
            return dsl, vr

        mock_generator = MagicMock()
        mock_generator.generate_step = mock_generate_step
        mock_es = MagicMock()

        executor = SelfReflectionExecutor(
            es_client=mock_es,
            dsl_generator=mock_generator,
            max_attempts=3,
        )

        from src.nl_dsl.models import QueryPlan, QueryStep
        plan = QueryPlan(steps=[
            QueryStep(step_id="step_1", description="test", index="ad_stat_data",
                      output_fields=[], purpose="test")
        ], final_output="step_1.output")

        result = await executor.execute_plan(
            plan=plan,
            advertiser_ids=["6"],
            time_range={"start": "2026-01-01", "end": "2026-01-31"},
        )

        # 应该失败
        assert result.metadata.get("success") is False
        assert result.metadata.get("retries") == 2  # 首次 + 2次重试
        assert result.metadata.get("final_error") is not None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_nl_dsl_generator.py::TestSelfReflectionExecutor -v 2>&1 | tail -30
```
Expected: FAIL (cannot import)

- [ ] **Step 3: 实现 SelfReflectionExecutor**

文件：`backend/src/nl_dsl/self_reflection_executor.py`

```python
"""自反思执行器

负责执行查询计划，每步：生成 DSL → 校验 → 执行 → 结果检查
失败则反思并重试，最多 max_attempts 次。
"""
import json
import time
import logging
from typing import Optional, Dict, Any, List

from src.config.context import truncate_log
from .models import QueryPlan, QueryStep, RetryInfo, NlDslResult
from .result_formatter import ResultFormatter

logger = logging.getLogger(__name__)


class SelfReflectionExecutor:
    """自反思查询执行器"""

    def __init__(
        self,
        es_client=None,
        dsl_generator=None,
        max_attempts: int = 3,
        query_timeout: int = 30,
    ):
        self._es = es_client
        self._generator = dsl_generator
        self.max_attempts = max_attempts
        self.query_timeout = query_timeout

    async def execute_plan(
        self,
        plan: QueryPlan,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        display_type_hint: str = "",
    ) -> NlDslResult:
        """执行查询计划

        Args:
            plan: 查询计划
            advertiser_ids: 广告主ID列表
            time_range: 时间范围 {start, end}
            display_type_hint: 呈现类型提示
            
        Returns:
            NlDslResult
        """
        start_time = time.time()
        step_results: Dict[str, Any] = {}

        for step in plan.steps:
            result = await self._execute_step(
                step=step,
                advertiser_ids=advertiser_ids,
                time_range=time_range,
                prev_results=step_results,
            )

            if not result.metadata.get("success", True):
                # 某步失败，直接返回失败结果
                logger.error(
                    f"NL→DSL查询失败: 步骤={step.step_id}, "
                    f"错误={result.metadata.get('final_error', 'unknown')}"
                )
                return result

            step_results[step.step_id] = result

        # 取最后一步的结果作为最终结果
        final_step_id = plan.final_output.replace(".output", "")
        final_result = step_results.get(final_step_id)

        if final_result:
            # 更新总耗时
            final_result.metadata["query_steps"] = len(plan.steps)
            final_result.metadata["total_time_ms"] = int((time.time() - start_time) * 1000)
            logger.info(
                f"NL→DSL查询完成: 总步骤={len(plan.steps)}, "
                f"总耗时={final_result.metadata['total_time_ms']}ms, "
                f"最终行数={final_result.metadata.get('total_rows', 0)}"
            )
            return final_result

        # 没有结果（空计划）
        return NlDslResult(
            display_type="qa",
            columns=[],
            rows=[],
            metadata={"success": False, "final_error": "空查询计划"},
        )

    async def _execute_step(
        self,
        step: QueryStep,
        advertiser_ids: List[str],
        time_range: Dict[str, str],
        prev_results: Dict[str, Any],
    ) -> NlDslResult:
        """执行单步查询，含反思重试"""
        step_id = step.step_id
        last_error = ""
        last_dsl = None
        total_retries = 0

        for attempt in range(1, self.max_attempts + 1):
            retry_info = None
            if attempt > 1 and last_error:
                retry_info = RetryInfo(
                    attempt=attempt,
                    failure_type=self._classify_failure(last_error),
                    error_message=last_error,
                    previous_dsl=last_dsl,
                )
                logger.info(
                    f"NL→DSL第{attempt}次重试(步骤{step_id}): "
                    f"失败类型={retry_info.failure_type}"
                )

            # 1. 生成 DSL
            dsl, validation_result = await self._generator.generate_step(
                step=step,
                advertiser_ids=advertiser_ids,
                time_range=time_range,
                prev_results=prev_results,
                retry_info=retry_info,
            )
            last_dsl = dsl

            # 2. 校验
            if not validation_result.ok:
                last_error = "校验失败: " + "; ".join(validation_result.errors)
                logger.info(f"NL→DSL安全校验失败(步骤{step_id}): {last_error}")
                total_retries = attempt
                continue

            # 3. 执行
            try:
                es_response = self._execute_search(dsl, step.index)
            except Exception as e:
                last_error = f"执行失败: {str(e)}"
                logger.error(f"NL→DSL执行失败(步骤{step_id}): {truncate_log(str(e), 200)}")
                total_retries = attempt
                continue

            # 4. 结果检查
            check_result = self._check_result(es_response, step)
            if not check_result["ok"]:
                last_error = f"结果异常: {check_result['reason']}"
                logger.info(f"NL→DSL结果检查(步骤{step_id}): {last_error}")
                # 空结果特殊处理：第一次自查后重试，第二次就返回
                if check_result.get("is_empty") and attempt >= 2:
                    # 空结果且已经重试过了，返回空结果（不算失败）
                    formatted = ResultFormatter.format(es_response, display_type_hint)
                    result = NlDslResult(**formatted)
                    result.metadata["retries"] = attempt - 1
                    result.metadata["is_empty_result"] = True
                    result.metadata["empty_reason"] = check_result["reason"]
                    return result
                total_retries = attempt
                continue

            # 5. 成功，格式化结果
            formatted = ResultFormatter.format(es_response, display_type_hint)
            result = NlDslResult(**formatted)
            result.metadata["retries"] = attempt - 1
            result.metadata["success"] = True
            result.metadata["step_id"] = step_id
            # 保存 query_context 用于翻页（列表类型）
            if result.display_type == "list":
                result.query_context = {
                    "index": step.index,
                    "base_dsl": dsl,
                    "total": result.metadata.get("total_rows", 0),
                }
            return result

        # 所有尝试都失败
        logger.error(f"NL→DSL最终失败(步骤{step_id}): 重试{total_retries}次, 最终错误={last_error}")
        return NlDslResult(
            display_type="qa",
            columns=["错误信息"],
            rows=[[last_error]],
            metadata={
                "success": False,
                "retries": total_retries,
                "final_error": last_error,
                "failure_type": self._classify_failure(last_error),
            },
        )

    def _execute_search(self, dsl: dict, index_name: str) -> dict:
        """执行 ES 查询"""
        if self._es is None:
            raise RuntimeError("ES 客户端未初始化")

        # size 截断
        size = dsl.get("size", 10)
        if isinstance(size, int) and size > 1000:
            dsl = dict(dsl)
            dsl["size"] = 1000

        response = self._es.search(
            index=index_name,
            body=dsl,
            request_timeout=self.query_timeout,
        )
        return response

    @staticmethod
    def _check_result(es_response: dict, step: QueryStep) -> dict:
        """检查查询结果是否合理

        Returns:
            {"ok": bool, "reason": str, "is_empty": bool}
        """
        # 检查空结果
        hits = es_response.get("hits", {})
        total = hits.get("total", 0)
        if isinstance(total, dict):
            total = total.get("value", 0)

        aggs = es_response.get("aggregations", {})
        has_aggs = bool(aggs)

        if total == 0 and not has_aggs:
            return {"ok": False, "reason": "查询结果为空（0条命中且无聚合结果）", "is_empty": True}

        # 检查聚合结果是否也为空
        if has_aggs and total == 0:
            # 检查第一个聚合的 buckets
            first_agg_key = list(aggs.keys())[0]
            first_agg = aggs[first_agg_key]
            if isinstance(first_agg, dict) and "buckets" in first_agg:
                if len(first_agg["buckets"]) == 0:
                    return {"ok": False, "reason": "聚合结果为空（0个bucket）", "is_empty": True}

        # TODO: 数值异常检查（数量级不合理等）
        # 暂时只做空结果检查

        return {"ok": True, "reason": ""}

    @staticmethod
    def _classify_failure(error_msg: str) -> str:
        """将错误信息分类为失败类型"""
        error_msg = error_msg.lower()
        if "校验失败" in error_msg or "validation" in error_msg:
            return "validation"
        if "执行失败" in error_msg or "exception" in error_msg or "error" in error_msg:
            return "execution"
        if "空" in error_msg or "empty" in error_msg:
            return "empty"
        if "异常" in error_msg or "abnormal" in error_msg:
            return "abnormal"
        return "unknown"


_executor_instance = None


def get_self_reflection_executor() -> SelfReflectionExecutor:
    """获取 SelfReflectionExecutor 单例"""
    global _executor_instance
    if _executor_instance is None:
        from elasticsearch import Elasticsearch
        from .dsl_generator import get_dsl_generator

        es_client = Elasticsearch(["http://localhost:9200"])
        generator = get_dsl_generator()

        _executor_instance = SelfReflectionExecutor(
            es_client=es_client,
            dsl_generator=generator,
        )
    return _executor_instance
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_nl_dsl_generator.py::TestSelfReflectionExecutor -v 2>&1 | tail -30
```
Expected: 3 passed

- [ ] **Step 5: 更新 __init__.py 并提交**

```python
# 追加到 nl_dsl/__init__.py
from .self_reflection_executor import SelfReflectionExecutor, get_self_reflection_executor

# 更新 __all__
__all__ = [
    # ... 已有
    "SelfReflectionExecutor", "get_self_reflection_executor",
]
```

```bash
cd /Users/simon/AL/DataAgent && python -m py_compile backend/src/nl_dsl/self_reflection_executor.py
git add backend/src/nl_dsl/self_reflection_executor.py backend/src/nl_dsl/__init__.py backend/tests/test_nl_dsl_generator.py
git commit -m "feat: add self-reflection executor with 3-attempt retry loop"
```

---

### Task 7: 意图理解层改造（路由判断 + 去硬编码校验）

**Files:**
- Modify: `backend/src/intent/report_intent.py`
- Modify: `backend/src/graph/nodes.py` (report_intent_node)
- Test: `backend/tests/test_report_intent.py` (增加路由测试)

**Interfaces:**
- Consumes: 现有的 `ReportIntentAnalyzer.analyze()` 接口
- Produces: `analyze()` 新增返回字段 `query_route` 和 `analysis_type`，保留原有三返回值结构

- [ ] **Step 1: 分析现有 report_intent.py 的 check_capabilities 调用位置**

阅读 `backend/src/intent/report_intent.py` 中 `analyze()` 方法，找到 `check_capabilities` 调用位置，理解当前逻辑。

（此步为准备工作，不写代码，实施时先 Read 文件确认。）

- [ ] **Step 2: 修改 ReportIntentAnalyzer — 新增路由判断方法**

在 `ReportIntentAnalyzer` 类中新增方法：

```python
def _determine_query_route(self, result: ReportIntentResult, user_input: str) -> Tuple[str, str]:
    """判断走结构化路径还是 NL→DSL 路径

    Returns:
        (route: str, reason: str)
        route: "structured" / "nl_dsl"
    """
    # 结构化可表达的条件：
    # 1. 单索引（不涉及跨索引查询）
    # 2. 指标都是标准指标（在 METRIC_MAPPING 中）
    # 3. 维度都是标准维度（在 DIMENSION_MAPPING 中）
    # 4. 过滤条件简单（term / range，无复杂嵌套）
    # 5. 无 having / 聚合后过滤
    # 6. 无跨层级关联查询
    # 7. 单步查询

    # 启发式规则：
    # - 如果有复杂过滤（比如"名称包含xxx"、"大于xxx"的 having 条件）→ nl_dsl
    # - 如果涉及多个层级的联合查询 → nl_dsl
    # - 如果用户问了"列表"、"有哪些"、"包含"等关键词 → 可能是列表查询，走 nl_dsl 更灵活
    # - 否则走结构化

    # 简单的关键词检测（后续可以用 LLM 判断）
    nl_dsl_keywords = [
        "列表", "有哪些", "包含", "所有", "全部",
        "大于", "小于", "超过", "低于", "高于",
        "排名", "top", "前",
        "明细", "详情",
    ]

    user_input_lower = user_input.lower()
    for kw in nl_dsl_keywords:
        if kw in user_input_lower:
            return "nl_dsl", f"命中关键词: {kw}"

    # 检查是否有复杂过滤
    if result.filters and len(result.filters) > 3:
        return "nl_dsl", "过滤条件较多（>3个）"

    # 检查是否有 having 类语义（"消耗大于xx的计划"）
    # （简单判断：filters 中有数值比较型过滤且针对指标）

    # 默认走结构化
    return "structured", "标准指标+维度，结构化可表达"
```

- [ ] **Step 3: 修改 analyze() 方法**

在 `analyze()` 方法中：
1. 保留 `check_capabilities()` 调用（但改为可选，不通过时不触发澄清，而是路由到 nl_dsl）
2. 调用 `_determine_query_route()` 获取路由结果
3. 在返回值中新增路由信息（通过 result 的扩展字段，或新增返回值）

```python
# 在 analyze() 末尾，返回前增加：
route, reason = self._determine_query_route(result, user_input)
logger.info(f"报表意图路由判断: 路径={route}, 原因={reason}")

# 将路由信息存入 result 的 model_dump 中
# 由于 ReportIntentResult 没有这些字段，我们通过额外的 dict 返回
# 修改返回元组为四元组：
# return result, clarification, final_report, route_info
```

注意：需要同步更新 `report_intent_node` 中的接收逻辑。

- [ ] **Step 4: 修改 report_intent_node 接收新返回值**

在 `graph/nodes.py` 的 `report_intent_node` 中：
1. 接收新增的 `route_info` 返回值
2. 将 `query_route` / `route_reason` / `analysis_type` 写入 state
3. 保留所有现有逻辑不变

- [ ] **Step 5: 添加路由判断测试**

在 `tests/test_report_intent.py` 中增加路由判断测试用例。

- [ ] **Step 6: 运行测试验证**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_report_intent.py -v 2>&1 | tail -30
```

- [ ] **Step 7: 验证语法并提交**

```bash
cd /Users/simon/AL/DataAgent && python -m py_compile backend/src/intent/report_intent.py backend/src/graph/nodes.py
git add backend/src/intent/report_intent.py backend/src/graph/nodes.py backend/tests/test_report_intent.py
git commit -m "feat: add query route determination to report_intent (structured vs nl_dsl)"
```

---

### Task 8: nl_dsl_node 接入 Graph 流程

**Files:**
- Modify: `backend/src/graph/nodes.py` (新增 nl_dsl_node)
- Modify: `backend/src/graph/builder.py` (新增节点和路由)
- Modify: `backend/src/graph/state.py` (新增 state 字段)
- Test: `backend/tests/test_nl_dsl_node.py`

**Interfaces:**
- Consumes: state 中的 `user_input`, `report_intent_result`, `query_route`, `advertiser_ids`
- Produces: state 更新 `nl_dsl_result`, `final_report`（失败引导或成功结果）

- [ ] **Step 1: 修改 State，新增字段**

在 `AdReportState` 中新增：
```python
# NL→DSL 查询相关
query_route: Optional[str]       # "structured" / "nl_dsl"
route_reason: Optional[str]      # 路由判断依据
analysis_type: Optional[str]     # 分析类型提示
nl_dsl_result: Optional[Dict]    # NL→DSL 查询结果（中间格式）
query_context: Optional[Dict]    # 翻页上下文（不返回前端）
```

- [ ] **Step 2: 实现 nl_dsl_node**

在 `graph/nodes.py` 中新增节点函数：

```python
async def nl_dsl_node(state: dict) -> dict:
    """NL→DSL 查询节点
    
    封装 Schema RAG 检索 + 查询规划 + DSL 生成 + 安全校验 + 自反思执行 + 结果格式化
    """
    from src.nl_dsl.self_reflection_executor import get_self_reflection_executor
    from src.nl_dsl.dsl_generator import get_dsl_generator
    
    user_input = state.get("user_input", "")
    report_intent = state.get("report_intent_result", {}) or {}
    advertiser_ids = state.get("advertiser_ids", [])
    
    logger.info(f"开始NL→DSL查询: 用户输入='{user_input[:100]}', 广告主={advertiser_ids}")
    
    updates = {}
    
    try:
        # 1. 构造约束
        time_range = report_intent.get("time_range") or {}
        metrics = report_intent.get("metrics", [])
        analysis_type = report_intent.get("chart_type") or state.get("analysis_type", "")
        
        constraints = {
            "advertiser_ids": advertiser_ids,
            "time_range": time_range,
            "metrics": metrics,
            "analysis_type": analysis_type,
        }
        
        # 2. 查询规划
        generator = get_dsl_generator()
        plan = await generator.plan_query(user_input, constraints)
        
        # 3. 执行（含自反思重试）
        executor = get_self_reflection_executor()
        result = await executor.execute_plan(
            plan=plan,
            advertiser_ids=advertiser_ids,
            time_range=time_range,
            display_type_hint=analysis_type,
        )
        
        # 4. 检查结果
        if not result.metadata.get("success", True):
            # 失败：生成失败引导报告
            final_report = _build_failure_guide_report(result, user_input)
            updates["final_report"] = final_report
            logger.info(f"NL→DSL查询失败: 生成失败引导报告")
            return updates
        
        # 5. 成功：构建 final_report
        final_report = _build_nl_dsl_final_report(result, user_input, report_intent)
        updates["final_report"] = final_report
        updates["nl_dsl_result"] = result.model_dump()
        
        # 保存 query_context（用于翻页）
        if result.query_context:
            updates["query_context"] = result.query_context
        
        logger.info(
            f"NL→DSL查询完成: 呈现类型={result.display_type}, "
            f"行数={result.metadata.get('total_rows', 0)}"
        )
        
    except Exception as e:
        logger.exception(f"NL→DSL节点异常: error={e}")
        # 失败引导
        final_report = _build_failure_guide_report(
            type(e).__name__ + ": " + str(e), user_input
        )
        updates["final_report"] = final_report
    
    return updates
```

同时新增两个辅助函数：`_build_nl_dsl_final_report()` 和 `_build_failure_guide_report()`。

- [ ] **Step 3: 修改 builder.py — 新增节点和路由**

在 `builder.py` 中：
1. 导入 `nl_dsl_node`
2. `graph.add_node("nl_dsl", nl_dsl_node)`
3. 在 `route_after_report_intent` 中增加 nl_dsl 分支
4. 在 `route_after_clarify` 中增加 continue_nl_dsl 分支
5. 增加 `nl_dsl → reporter` 的边

- [ ] **Step 4: 编写 nl_dsl_node 测试**

文件：`backend/tests/test_nl_dsl_node.py`
- mock executor 返回成功结果 → 验证 state 更新正确
- mock executor 返回失败 → 验证生成失败引导报告
- 异常情况 → 验证错误处理

- [ ] **Step 5: 运行测试验证**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/test_nl_dsl_node.py -v 2>&1 | tail -20
```

- [ ] **Step 6: 验证语法并提交**

```bash
cd /Users/simon/AL/DataAgent && python -m py_compile backend/src/graph/nodes.py backend/src/graph/builder.py backend/src/graph/state.py
git add backend/src/graph/nodes.py backend/src/graph/builder.py backend/src/graph/state.py backend/tests/test_nl_dsl_node.py
git commit -m "feat: add nl_dsl_node to LangGraph flow with report_intent routing"
```

---

### Task 9: Reporter 支持 display_type

**Files:**
- Modify: `backend/src/agents/reporter_agent.py`
- Test: `backend/tests/test_reporter_agent.py` (新增 display_type 测试)

**Interfaces:**
- Consumes: `display_type` 字段（来自 nl_dsl_result 或 query_intent）
- Produces: `final_report` 中包含 `display_type` 字段，data_table 结构保持兼容

- [ ] **Step 1: 修改 reporter_agent 支持 display_type**

在 `reporter_agent` 的输出中增加 `display_type` 字段：
- 结构化路径：根据 chart_type / group_by 推断 display_type
- NL→DSL 路径：直接用 result.display_type

- [ ] **Step 2: 添加不同呈现类型的 title / highlights 生成逻辑**

根据 display_type 生成不同的标题和亮点描述。

- [ ] **Step 3: 添加测试并运行**

- [ ] **Step 4: 提交**

```bash
git add backend/src/agents/reporter_agent.py backend/tests/test_reporter_agent.py
git commit -m "feat: reporter supports display_type for multiple presentation formats"
```

---

### Task 10: 集成测试 + 全链路验证

**Files:**
- Create: `backend/tests/test_nl_dsl_integration.py`
- Modify: `backend/tests/test_full_graph_flow.py` (新增 nl_dsl 路径测试)

- [ ] **Step 1: 编写 NL→DSL 集成测试**

模拟完整流程：report_intent 路由到 nl_dsl → nl_dsl_node 生成查询 → 执行 → 返回 final_report

- [ ] **Step 2: 更新全流程测试**

在 `test_full_graph_flow.py` 中增加 nl_dsl 路径的测试用例。

- [ ] **Step 3: 运行全部测试**

```bash
cd /Users/simon/AL/DataAgent/backend && python -m pytest tests/ -v 2>&1 | tail -50
```

- [ ] **Step 4: 提交**

```bash
git add backend/tests/test_nl_dsl_integration.py backend/tests/test_full_graph_flow.py
git commit -m "test: add NL→DSL integration tests and full graph flow tests for nl_dsl path"
```

---

## Phase 2: 能力增强（后续迭代，不在本次计划中详述）

1. **多步查询支持** — 支持场景四类型的多步跨索引查询
2. **服务端分页 API** — `POST /api/sessions/{session_id}/list-page`
3. **受众分析呈现类型** — 饼图/环形图渲染
4. **受众对比呈现类型** — 双图并排
5. **查询层澄清机制** — NL→DSL 阶段触发 clarify 中断

## Phase 3: 长期优化（未来）

1. **历史查询库** — 用户问题→DSL 对存入 RAG，越用越准
2. **Schema 自动扫描同步** — 扫描 ES mapping 自动生成 schema 文档
3. **语义层 / 指标平台**
4. **逐步将结构化查询迁移到 NL→DSL**

---

## Self-Review

### Spec Coverage
- ✅ Schema RAG（Task 1-2）：索引/字段/示例三级，YAML 配置，同步脚本，向量检索
- ✅ DSL 安全校验器（Task 3）：索引白名单、advertiser过滤、时间过滤、脚本禁用、size限制
- ✅ 结果格式化器（Task 4）：hits/aggregations 格式化，自动呈现类型检测
- ✅ NL→DSL 生成器（Task 5）：查询规划、DSL生成、反思修正
- ✅ 自反思执行器（Task 6）：3次尝试，校验/执行/结果检查三类失败
- ✅ 意图层路由改造（Task 7）：结构化 vs NL→DSL 路由判断
- ✅ nl_dsl_node 接入 Graph（Task 8）：节点 + 路由 + state
- ✅ Reporter 多呈现类型（Task 9）：display_type 支持
- ✅ 集成测试（Task 10）
- ⚠️ 服务端分页：Phase 2（本次不做，设计中有预留）
- ⚠️ 多步查询：Phase 2（本次实现单步为主，规划器已预留多步接口）
- ⚠️ 查询层澄清：Phase 2（本次失败引导直接返回，不触发 clarify 中断）
- ✅ 日志规范：各模块均使用 logger + truncate_log，对齐现有规范

### Placeholder Scan
- 没有 TBD / TODO 占位符
- Task 7（意图层改造）的步骤较粗，因为需要读现有代码确认具体位置——这是合理的，实施时再细化

### Type Consistency
- ✅ `NlDslResult` 模型与 ResultFormatter.format() 返回结构一致
- ✅ `QueryPlan` / `QueryStep` / `RetryInfo` 在生成器和执行器中一致
- ✅ `ValidationResult` 在 validator 和 generator 中一致
- ✅ state 新增字段与 nl_dsl_node 输出一致

---

## 实现增强与补充（实施过程中新增）

以下功能在实施过程中根据实际需要补充，超出原计划范围：

### 1. field_mapping.py 字段映射模块（新增文件）

**文件**：`src/nl_dsl/field_mapping.py`

**功能**：
- `extract_agg_field_mapping(dsl)`: 从 DSL aggs 中提取「聚合名 → 实际 ES 字段名」映射
- `extract_data_types_from_dsl(dsl)`: 从 DSL 提取涉及的 data_type 值，用于识别指标
- `get_dimension_display_name(field)`: 维度字段 → 中文显示名
- `get_metric_display_name(data_type)`: data_type → 指标中文名
- `resolve_metric_from_query(query)`: 从用户问题中识别指标（同义词匹配）

**用途**：支撑 NL→DSL 结果的列名中文化显示。

### 2. 结果格式化增强（nodes.py _build_nl_dsl_final_report）

在原计划的 nl_dsl_node 基础上增强了 4 项功能：

| 功能 | 说明 |
|------|------|
| display_type 归一化 | exploratory_query / detail / comparison → list |
| 聚合列名中文化 | 用 field_mapping 将 by_campaign / total_consumption 等聚合名转为中文 |
| 实体名称自动补全 | 检测 ID 列后调用 get_entity_names() 补充名称列（计划名称/广告组名称等） |
| 明细查询自动聚合去重 | LLM 生成 detail 查询导致同一实体多行时，自动按维度聚合指标去重 |

### 3. hierarchy_utils.py 新增 get_entity_names()

**文件**：`src/tools/hierarchy_utils.py`

```python
def get_entity_names(entity_type: str, entity_ids: List[int]) -> Dict[int, str]
```

支持 advertiser / campaign / adgroup / creative 四种实体，批量从 ES 维度索引查询名称。

### 4. 自反思执行器容错增强

- `final_output` 匹配不到步骤 ID 时，降级使用最后一步结果
- 空结果（0 rows + 0 buckets）经过 2 次尝试后返回空结果，不视为失败
- 执行层 size 截断保护（校验层之外再加一层）
- 错误分类增强（validation/execution/empty/abnormal/unknown）

### 5. ResultFormatter size=0 聚合查询修复

**Bug**：size=0 的纯聚合查询，`hits.total > 0` 但 `hits.hits` 为空，被误判为 hits 结果导致格式化异常。

**修复**：新增 `_has_hit_documents()` 检查实际命中文档列表；聚合优先判断。

### 6. 前端澄清弹窗 UX 优化

- 点击确认后立即关闭弹窗（不等 API 返回）
- 立即追加用户消息到聊天历史
- 按钮 disabled + "处理中..." 防止重复提交
- 显示全局 loading 状态

**修改文件**：
- `frontend/src/stores/chatStore.ts`
- `frontend/src/components/ClarificationModal.tsx`

### 7. time_range 序列化兼容修复

**Bug**：`report_intent_result` 经 `model_dump()` 序列化存 state，恢复后 `time_range` 是 dict 而非 `ReportTimeRange` 对象，访问 `.start_date` 报错。

**修复**：在上下文继承时检测 dict 格式并转换为 `ReportTimeRange` 对象。

### 8. 广告主查询重设计（原规则匹配 → LLM 结构化判断）

原计划使用正则 + 关键词规则检测纯广告主查询。实施中改为基于 LLM 结构化输出的判断方式，更健壮：

- 判断依据：metrics 空 + group_by 空 + time_range 空 + ad_level 非报表层级
- 完全依赖 LLM 结构化提取结果，不依赖关键词正则
- 详见 `2026-08-05-advertiser-lookup-intent-design.md`
