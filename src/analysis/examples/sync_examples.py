"""CoT Examples Syncer - Sync few-shot examples to pgvector"""

import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml

# Add backend to path for imports
backend_path = Path(__file__).parent.parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_path))

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector
import uuid

from rag.config import get_db_url, EMBEDDING_DIMENSIONS
from rag.database import get_db_session
from rag.embedding import get_embedding_provider

Base = declarative_base()


class CotExampleDocument(Base):
    """CoT Example Document - stores the full example"""
    __tablename__ = "cot_examples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    example_id = Column(String(100), nullable=False, unique=True)
    question = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)  # positive/negative
    analysis_type = Column(String(50))
    filter_type = Column(String(50))
    reasoning_chinese = Column(Text, nullable=False)
    plan_json = Column(Text, nullable=False)  # JSON string of the plan
    notes = Column(Text)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS))  # Embedding of the question
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CotExampleSyncer:
    """Sync CoT examples from YAML to pgvector"""

    def __init__(self, yaml_path: Path = None):
        self.yaml_path = yaml_path or Path(__file__).parent / "cot_examples.yaml"
        self.embedding_provider = get_embedding_provider()

    def _get_content_hash(self, content: str) -> str:
        """Calculate SHA256 hash of content"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def load_examples(self) -> List[Dict[str, Any]]:
        """Load examples from YAML file"""
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"Examples file not found: {self.yaml_path}")

        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return data.get("examples", [])

    def sync_single(self, example: Dict[str, Any], db_session: Session) -> Optional[CotExampleDocument]:
        """Sync a single example to database"""
        example_id = example["example_id"]
        question = example["question"]

        # Serialize plan to JSON
        import json
        plan_json = json.dumps(example["plan"], ensure_ascii=False)

        # Create a unique content hash for change detection
        content_for_hash = f"{question}:{example['category']}:{plan_json}"
        content_hash = self._get_content_hash(content_for_hash)

        # Check if example already exists
        existing_doc = db_session.query(CotExampleDocument).filter_by(example_id=example_id).first()

        try:
            if existing_doc:
                # Check if content has changed by comparing hashes (using updated_at as proxy)
                # We'll just always update for simplicity
                existing_doc.question = question
                existing_doc.category = example["category"]
                existing_doc.analysis_type = example.get("analysis_type")
                existing_doc.filter_type = example.get("filter_type")
                existing_doc.reasoning_chinese = example["reasoning_chinese"]
                existing_doc.plan_json = plan_json
                existing_doc.notes = example.get("notes")
                existing_doc.updated_at = datetime.now()

                # Re-embed the question
                embedding = self.embedding_provider.embed(question)
                existing_doc.embedding = embedding

                db_session.commit()
                return existing_doc
            else:
                # Create new example
                embedding = self.embedding_provider.embed(question)

                doc = CotExampleDocument(
                    example_id=example_id,
                    question=question,
                    category=example["category"],
                    analysis_type=example.get("analysis_type"),
                    filter_type=example.get("filter_type"),
                    reasoning_chinese=example["reasoning_chinese"],
                    plan_json=plan_json,
                    notes=example.get("notes"),
                    embedding=embedding,
                )
                db_session.add(doc)
                db_session.commit()
                return doc

        except Exception as e:
            db_session.rollback()
            raise

    def sync_all(self, db_session: Session) -> int:
        """Sync all examples"""
        examples = self.load_examples()
        synced_count = 0

        try:
            for example in examples:
                doc = self.sync_single(example, db_session)
                if doc:
                    synced_count += 1

            db_session.commit()
            return synced_count
        except Exception as e:
            db_session.rollback()
            raise


def init_cot_examples_table():
    """Initialize the cot_examples table"""
    from sqlalchemy import create_engine, text

    engine = create_engine(get_db_url())

    # Create vector extension if not exists
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    # Create tables
    Base.metadata.create_all(bind=engine)


def sync_cot_examples():
    """Sync CoT examples - main entry point"""
    # First ensure table exists
    init_cot_examples_table()

    # Then sync
    session = get_db_session()
    try:
        syncer = CotExampleSyncer()
        count = syncer.sync_all(session)
        print(f"Synced {count} CoT examples")
        return count
    finally:
        session.close()


if __name__ == "__main__":
    sync_cot_examples()
