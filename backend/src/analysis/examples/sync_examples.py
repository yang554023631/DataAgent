"""CoT Examples Syncer - Sync few-shot examples to pgvector using existing RAG infrastructure

Reuses the same RagDocument and RagChunk tables with doc_type='cot_example'
"""

import logging
import yaml
import hashlib
import uuid
import json
from pathlib import Path
from typing import List, Tuple
from sqlalchemy import select

# Add backend src to path for imports
import sys
backend_path = Path(__file__).parent.parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_path))

logger = logging.getLogger(__name__)

# Default path to examples YAML
EXAMPLES_PATH = Path(__file__).parent / "cot_examples.yaml"


def _example_to_content(example: dict) -> Tuple[str, str, str]:
    """
    Convert a single example to a format suitable for RAG storage.

    Returns:
        (title, doc_type, content) tuple
    """
    example_id = example["example_id"]
    question = example["question"]
    category = example["category"]
    analysis_type = example.get("analysis_type", "")
    filter_type = example.get("filter_type", "")

    # Build content with metadata and reasoning
    lines = [f"# CoT Example: {example_id}", ""]
    lines.append(f"## 问题 (Question)")
    lines.append(question)
    lines.append("")
    lines.append(f"## 元数据 (Metadata)")
    lines.append(f"- example_id: {example_id}")
    lines.append(f"- category: {category}")
    lines.append(f"- analysis_type: {analysis_type}")
    lines.append(f"- filter_type: {filter_type}")
    lines.append("")
    lines.append(f"## 推理过程 (Reasoning)")
    lines.append(example["reasoning_chinese"])
    lines.append("")
    lines.append(f"## 生成计划 (Plan)")
    lines.append("```json")
    lines.append(json.dumps(example["plan"], ensure_ascii=False, indent=2))
    lines.append("```")

    if "notes" in example and example["notes"]:
        lines.append("")
        lines.append(f"## 备注 (Notes)")
        lines.append(example["notes"])

    content = "\n".join(lines)
    title = f"CoT Example: {example_id}"
    doc_type = "cot_example"

    return title, doc_type, content


def _load_yaml_examples(file_path: Path) -> List[dict]:
    """Load examples from YAML file"""
    if not file_path.exists():
        raise FileNotFoundError(f"Examples file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data.get("examples", [])


class CotExamplesSyncer:
    """CoT Examples Syncer

    Reads examples from YAML, generates embeddings, stores in existing RAG tables
    with doc_type='cot_example'.
    """

    def __init__(self):
        from src.rag.embedding import get_embedding_provider
        from src.rag.database import get_db
        from src.rag.models import RagDocument, RagChunk

        self._embedding_provider = get_embedding_provider()
        self._get_db = get_db
        self.RagDocument = RagDocument
        self.RagChunk = RagChunk

    def sync_all(self, examples_path: Path = None) -> Tuple[int, int]:
        """
        Sync all examples from YAML to RAG database

        Returns:
            (success_count, failed_count)
        """
        if examples_path is None:
            examples_path = EXAMPLES_PATH

        success = 0
        failed = 0

        try:
            examples = _load_yaml_examples(examples_path)
            logger.info(f"CoT examples sync started: {len(examples)} examples found")
        except Exception as e:
            logger.exception(f"Failed to load examples: {e}")
            return 0, 1

        db = next(self._get_db())
        try:
            for example in examples:
                try:
                    self._sync_single_example(example, db)
                    success += 1
                except Exception as e:
                    logger.exception(f"Failed to sync example {example.get('example_id', 'unknown')}: {e}")
                    failed += 1
        finally:
            db.close()

        logger.info(f"CoT examples sync complete: success={success}, failed={failed}")
        return success, failed

    def _sync_single_example(self, example: dict, db) -> None:
        """Sync a single example to RAG database"""
        example_id = example["example_id"]
        title, doc_type, content = _example_to_content(example)
        question = example["question"]

        # Compute hash on full content for change detection
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        file_path = f"cot_example://{example_id}"

        # Check if document already exists
        existing = db.execute(
            select(self.RagDocument).where(self.RagDocument.file_path == file_path)
        ).scalar_one_or_none()

        # Generate embedding for the QUESTION (not full content) per task requirements
        embedding = self._embedding_provider.embed(question)

        if existing and existing.chunks and len(existing.chunks) > 0:
            # Update existing document
            if existing.chunks[0].content_hash == content_hash:
                logger.debug(f"Example unchanged, skipping: {example_id}")
                return

            existing.title = title
            existing.is_active = True
            existing.chunks[0].content = content
            existing.chunks[0].content_hash = content_hash
            existing.chunks[0].embedding = embedding
            logger.debug(f"Updated existing example: {example_id}")
        else:
            # Create new document and chunk
            doc = self.RagDocument(
                id=uuid.uuid4(),
                title=title,
                file_path=file_path,
                doc_type=doc_type,
                version="1.0",
                is_active=True,
            )
            chunk = self.RagChunk(
                id=uuid.uuid4(),
                doc_id=doc.id,
                chunk_index=0,
                content=content,
                content_hash=content_hash,
                embedding=embedding,
            )
            db.add(doc)
            db.add(chunk)
            logger.debug(f"Created new example: {example_id}")

        db.commit()


# Singleton instance
_cot_syncer_instance = None


def get_cot_examples_syncer() -> CotExamplesSyncer:
    """Get the CoT Examples Syncer singleton"""
    global _cot_syncer_instance
    if _cot_syncer_instance is None:
        _cot_syncer_instance = CotExamplesSyncer()
    return _cot_syncer_instance


def sync_cot_examples():
    """Main entry point for syncing CoT examples"""
    logging.basicConfig(level=logging.INFO)
    syncer = get_cot_examples_syncer()
    success, failed = syncer.sync_all()
    print(f"Synced {success} examples successfully, {failed} failed")


if __name__ == "__main__":
    sync_cot_examples()
