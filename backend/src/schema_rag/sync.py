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
        f'"{data.get("user_query_example", "")}"',
        "",
        f"- 涉及索引: `{data.get('index', '')}`",
        "",
    ]
    if data.get("dsl_template_summary"):
        lines.append("## DSL 要点")
        lines.append(data["dsl_template_summary"])
        lines.append("")
    return "\n".join(lines)


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