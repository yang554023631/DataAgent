import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session

from .config import RAG_DOCS_DIR
from .database import get_db_session
from .models import RagDocument, RagChunk
from .splitter import MarkdownSplitter
from .embedding import get_embedding_provider


class DocumentSyncer:
    """文档同步器 - 负责将 Markdown 文件同步到向量数据库"""

    def __init__(self, docs_dir: Path = None):
        self.docs_dir = docs_dir or RAG_DOCS_DIR
        self.splitter = MarkdownSplitter()
        self.embedding_provider = get_embedding_provider()

    def scan_directory(self) -> List[Path]:
        """扫描目录下所有 Markdown 文件"""
        if not self.docs_dir.exists():
            return []

        md_files = []
        for root, dirs, files in os.walk(self.docs_dir):
            for file in files:
                if file.endswith(".md"):
                    md_files.append(Path(root) / file)
        return sorted(md_files)

    def _extract_title(self, content: str, file_path: Path) -> str:
        """从 Markdown 内容中提取标题"""
        lines = content.strip().split("\n")
        for line in lines:
            if line.startswith("# "):
                return line[2:].strip()
        # 如果没有一级标题，使用文件名
        return file_path.stem

    def _extract_doc_type(self, file_path: Path) -> str:
        """从目录结构中提取文档类型"""
        rel_path = file_path.relative_to(self.docs_dir)
        # 取第一级目录名作为类型
        if len(rel_path.parts) > 1:
            type_dir = rel_path.parts[0]
            # 去掉前缀序号 01_xxx -> xxx
            if "_" in type_dir:
                return type_dir.split("_", 1)[1]
            return type_dir
        return "unknown"

    def _get_file_hash(self, file_path: Path) -> str:
        """计算文件内容 SHA256 hash"""
        content = file_path.read_text(encoding="utf-8")
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def sync_single(self, file_path: Path, db_session: Session) -> Optional[RagDocument]:
        """同步单个 Markdown 文件"""
        if not file_path.exists():
            return None

        content = file_path.read_text(encoding="utf-8")

        try:
            # 预先计算分片（避免重复计算）
            new_chunks = self.splitter.split(content)
            new_hashes = set(c.content_hash for c in new_chunks)

            # 检查是否已存在且未修改
            existing_doc = db_session.query(RagDocument).filter_by(file_path=str(file_path)).first()

            if existing_doc:
                # 比较所有分片的 hash 总和，判断是否需要重新同步
                existing_hashes = set(c.content_hash for c in existing_doc.chunks)

                if existing_hashes == new_hashes:
                    # 内容未变化，只更新同步时间
                    existing_doc.last_synced_at = datetime.now()
                    db_session.commit()
                    return existing_doc

                # 内容变化，删除旧分片
                for chunk in existing_doc.chunks:
                    db_session.delete(chunk)

            # 提取元数据
            title = self._extract_title(content, file_path)
            doc_type = self._extract_doc_type(file_path)

            # 创建/更新文档
            if existing_doc:
                doc = existing_doc
                doc.title = title
                doc.doc_type = doc_type
                doc.updated_at = datetime.now()
                doc.last_synced_at = datetime.now()
            else:
                doc = RagDocument(
                    title=title,
                    file_path=str(file_path),
                    doc_type=doc_type,
                    last_synced_at=datetime.now(),
                )
                db_session.add(doc)
                db_session.flush()  # 获取 doc.id

            # 批量生成向量（重用预先计算的分片）
            chunk_contents = [c.content for c in new_chunks]
            embeddings = self.embedding_provider.embed_batch(chunk_contents)

            # 创建分片记录（重用预先计算的分片）
            for chunk, embedding in zip(new_chunks, embeddings):
                db_chunk = RagChunk(
                    doc_id=doc.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    content_hash=chunk.content_hash,
                    embedding=embedding,
                )
                db_session.add(db_chunk)

            db_session.commit()
            return doc
        except Exception as e:
            db_session.rollback()
            raise

    def sync_all(self, db_session: Session, incremental: bool = True) -> int:
        """
        同步所有 Markdown 文件

        Args:
            db_session: 数据库会话
            incremental: 是否增量同步

        Returns:
            同步的文件数量
        """
        md_files = self.scan_directory()
        synced_count = 0

        try:
            for file_path in md_files:
                doc = self.sync_single(file_path, db_session)
                if doc:
                    synced_count += 1

            db_session.commit()
            return synced_count
        except Exception as e:
            db_session.rollback()
            raise


def sync_documents(incremental: bool = True) -> int:
    """同步文档入口函数"""
    session = get_db_session()
    try:
        syncer = DocumentSyncer()
        count = syncer.sync_all(session, incremental=incremental)
        return count
    finally:
        session.close()
