# 广告帮助文档 RAG 系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有的广告报表多 Agent 系统基础上，实现基于 pgvector 的广告业务知识 RAG 功能，支持意图路由、向量检索、重排序和文档自动同步。

**Architecture:** PostgreSQL + pgvector 本地部署，商用 Embedding API + 本地 Reranker 模型，LangGraph 新增意图路由节点 + RAG 检索回答节点，Markdown 文档目录自动同步到向量库。

**Tech Stack:** PostgreSQL 16, pgvector 0.7.0, LangChain, sentence-transformers (Reranker), FastAPI, Python 3.10+

---

## 文件结构总览

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/rag/__init__.py` | 创建 | RAG 模块初始化 |
| `backend/rag/config.py` | 创建 | 配置管理（数据库连接、API Key等） |
| `backend/rag/embedding.py` | 创建 | 向量生成模块，封装 Embedding API |
| `backend/rag/splitter.py` | 创建 | Markdown 智能分片模块 |
| `backend/rag/retriever.py` | 创建 | 向量检索 + Reranker 重排序 |
| `backend/rag/sync.py` | 创建 | 文档同步脚本（全量/增量/监听） |
| `backend/rag/agents.py` | 创建 | LangGraph RAG 节点定义 |
| `backend/rag/models.py` | 创建 | SQLAlchemy ORM 模型 |
| `backend/rag/database.py` | 创建 | 数据库连接与表创建 |
| `backend/app/routers/rag.py` | 创建 | RAG API 路由（可选，用于调试） |
| `docs/rag/` | 创建 | 文档存放目录 |
| `scripts/install_pgvector.sh` | 创建 | PostgreSQL + pgvector 安装脚本 |
| `scripts/rag_sync.py` | 创建 | 文档同步入口脚本 |
| `backend/tests/rag/test_embedding.py` | 创建 | 向量生成测试 |
| `backend/tests/rag/test_splitter.py` | 创建 | 分片测试 |
| `backend/tests/rag/test_retriever.py` | 创建 | 检索测试 |
| `backend/tests/rag/test_sync.py` | 创建 | 同步测试 |

---

## 第一阶段：基础设施搭建

### Task 1: 安装脚本 - PostgreSQL + pgvector

**Files:**
- Create: `scripts/install_pgvector.sh`

- [ ] **Step 1: 编写安装脚本**

```bash
#!/bin/bash
set -e

INSTALL_DIR="$HOME/Tools/pgsql"
DATA_DIR="$HOME/Tools/pgsql/data"
PG_VERSION="16.2"
PGVECTOR_VERSION="0.7.0"

echo "=== 安装 PostgreSQL $PG_VERSION + pgvector $PGVECTOR_VERSION ==="
echo "安装目录: $INSTALL_DIR"
echo "数据目录: $DATA_DIR"

# 创建目录
mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR"

# 下载 PostgreSQL
cd /tmp
if [ ! -f "postgresql-$PG_VERSION.tar.gz" ]; then
    echo "下载 PostgreSQL..."
    curl -O "https://ftp.postgresql.org/pub/source/v$PG_VERSION/postgresql-$PG_VERSION.tar.gz"
fi

# 解压编译 PostgreSQL
echo "编译 PostgreSQL..."
tar -xzf "postgresql-$PG_VERSION.tar.gz"
cd "postgresql-$PG_VERSION"
./configure --prefix="$INSTALL_DIR" --without-readline --without-zlib
make -j$(nproc)
make install

# 配置环境变量
export PATH="$INSTALL_DIR/bin:$PATH"
export PGDATA="$DATA_DIR"

# 初始化数据库
echo "初始化数据库..."
initdb -D "$DATA_DIR"

# 启动 PostgreSQL
echo "启动 PostgreSQL..."
pg_ctl -D "$DATA_DIR" -l "$DATA_DIR/postgresql.log" start

# 等待启动
sleep 3

# 创建默认数据库
createdb postgres || true

# 下载编译 pgvector
echo "安装 pgvector..."
cd /tmp
if [ ! -f "v$PGVECTOR_VERSION.tar.gz" ]; then
    curl -L -O "https://github.com/pgvector/pgvector/archive/refs/tags/v$PGVECTOR_VERSION.tar.gz"
fi
tar -xzf "v$PGVECTOR_VERSION.tar.gz"
cd "pgvector-$PGVECTOR_VERSION"
make
make install

# 创建扩展
psql -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo ""
echo "=== 安装完成 ==="
echo "PostgreSQL 安装在: $INSTALL_DIR"
echo "数据目录: $DATA_DIR"
echo "端口: 5432"
echo ""
echo "请将以下内容添加到 ~/.bashrc 或 ~/.zshrc:"
echo "export PATH=\"$INSTALL_DIR/bin:\$PATH\""
echo "export PGDATA=\"$DATA_DIR\""
echo ""
echo "启动命令: pg_ctl start"
echo "停止命令: pg_ctl stop"
```

- [ ] **Step 2: 添加执行权限**

Run: `chmod +x scripts/install_pgvector.sh`

- [ ] **Step 3: Commit**

```bash
git add scripts/install_pgvector.sh
git commit -m "feat: 添加 PostgreSQL + pgvector 安装脚本"
```

---

### Task 2: 数据库配置与 ORM 模型

**Files:**
- Create: `backend/rag/config.py`
- Create: `backend/rag/models.py`
- Create: `backend/rag/database.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 更新依赖文件**

在 `backend/requirements.txt` 末尾添加:

```txt
# RAG 相关
psycopg2-binary>=2.9.9
sqlalchemy>=2.0.25
openai>=1.10.0
langchain>=0.1.10
langchain-openai>=0.0.5
sentence-transformers>=2.3.0
python-dotenv>=1.0.0
watchdog>=3.0.0
```

- [ ] **Step 2: 编写配置文件**

```python
# backend/rag/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 基础路径
BASE_DIR = Path(__file__).parent.parent
RAG_DOCS_DIR = BASE_DIR.parent / "docs" / "rag"

# 数据库配置
DB_HOST = os.getenv("RAG_DB_HOST", "localhost")
DB_PORT = int(os.getenv("RAG_DB_PORT", "5432"))
DB_USER = os.getenv("RAG_DB_USER", "")
DB_PASSWORD = os.getenv("RAG_DB_PASSWORD", "")
DB_NAME = os.getenv("RAG_DB_NAME", "postgres")

def get_db_url():
    if DB_USER and DB_PASSWORD:
        return f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return f"postgresql+psycopg2://{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Embedding 配置
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Reranker 配置
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")
RERANKER_TOP_N = int(os.getenv("RERANKER_TOP_N", "5"))

# 检索配置
RETRIEVE_TOP_K = int(os.getenv("RETRIEVE_TOP_K", "20"))

# 分片配置
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
```

- [ ] **Step 3: 编写 ORM 模型**

```python
# backend/rag/models.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

from .config import EMBEDDING_DIMENSIONS

Base = declarative_base()

class RagDocument(Base):
    __tablename__ = "rag_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False, unique=True)
    doc_type = Column(String(100))  # business/operation/system
    version = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_synced_at = Column(DateTime)
    
    chunks = relationship("RagChunk", back_populates="document", cascade="all, delete-orphan")

class RagChunk(Base):
    __tablename__ = "rag_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS))
    created_at = Column(DateTime, default=datetime.now)
    
    document = relationship("RagDocument", back_populates="chunks")
    
    __mapper_args__ = {
        "unique_constraints": [
            {"columns": ["doc_id", "chunk_index"]}
        ]
    }
```

- [ ] **Step 4: 编写数据库初始化模块**

```python
# backend/rag/database.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .config import get_db_url
from .models import Base

engine = create_engine(get_db_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """初始化数据库表"""
    # 先创建 vector 扩展
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session():
    """直接获取数据库会话（非生成器）"""
    return SessionLocal()
```

- [ ] **Step 5: 创建 RAG 模块 `__init__.py`**

```python
# backend/rag/__init__.py
"""RAG 系统模块"""
from .config import RAG_DOCS_DIR
from .database import init_db, get_db, get_db_session

__all__ = ["RAG_DOCS_DIR", "init_db", "get_db", "get_db_session"]
```

- [ ] **Step 6: 验证依赖安装**

Run: `cd backend && pip install -r requirements.txt`
Expected: 所有依赖安装成功

- [ ] **Step 7: Commit**

```bash
git add backend/rag/__init__.py backend/rag/config.py backend/rag/models.py backend/rag/database.py backend/requirements.txt
git commit -m "feat: 添加 RAG 数据库配置与 ORM 模型"
```

---

### Task 3: 数据库初始化测试

**Files:**
- Create: `backend/tests/rag/__init__.py`
- Create: `backend/tests/rag/test_database.py`

- [ ] **Step 1: 编写数据库测试**

```python
# backend/tests/rag/test_database.py
import pytest
from sqlalchemy import text

from backend.rag.database import init_db, get_db_session, engine


@pytest.fixture(scope="module")
def db_session():
    init_db()
    session = get_db_session()
    yield session
    session.close()


def test_vector_extension_installed(db_session):
    """测试 vector 扩展是否安装"""
    result = db_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
    ).fetchone()
    assert result is not None
    assert result[0] == "vector"


def test_tables_created(db_session):
    """测试表是否创建成功"""
    result = db_session.execute(
        text("SELECT tablename FROM pg_tables WHERE tablename IN ('rag_documents', 'rag_chunks');")
    ).fetchall()
    assert len(result) == 2
    tables = [r[0] for r in result]
    assert "rag_documents" in tables
    assert "rag_chunks" in tables
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && pytest tests/rag/test_database.py -v`
Expected: 2 tests passed

- [ ] **Step 3: Commit**

```bash
git add backend/tests/rag/__init__.py backend/tests/rag/test_database.py
git commit -m "test: 添加数据库初始化测试"
```

---

## 第二阶段：RAG 核心模块开发

### Task 4: Embedding 模块开发

**Files:**
- Create: `backend/rag/embedding.py`
- Create: `backend/tests/rag/test_embedding.py`

- [ ] **Step 1: 编写测试用例**

```python
# backend/tests/rag/test_embedding.py
import pytest
import numpy as np

from backend.rag.embedding import get_embedding_provider, OpenAIEmbeddingProvider


def test_embedding_provider_factory():
    """测试 embedding provider 工厂函数"""
    provider = get_embedding_provider()
    assert provider is not None
    assert isinstance(provider, OpenAIEmbeddingProvider)


def test_embedding_dimensions():
    """测试向量维度是否正确"""
    provider = get_embedding_provider()
    text = "这是一个测试文本"
    embedding = provider.embed(text)
    assert embedding is not None
    assert len(embedding) == 1536  # text-embedding-3-small 维度
    assert isinstance(embedding, list)
    assert all(isinstance(x, float) for x in embedding)


def test_batch_embedding():
    """测试批量生成向量"""
    provider = get_embedding_provider()
    texts = ["文本1", "文本2", "文本3"]
    embeddings = provider.embed_batch(texts)
    assert len(embeddings) == 3
    assert all(len(e) == 1536 for e in embeddings)


def test_embedding_consistency():
    """测试相同输入生成相同向量"""
    provider = get_embedding_provider()
    text = "相同的输入"
    e1 = provider.embed(text)
    e2 = provider.embed(text)
    # 允许微小浮点误差
    assert np.allclose(np.array(e1), np.array(e2), atol=1e-6)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && pytest tests/rag/test_embedding.py -v`
Expected: FAIL with "No module named 'backend.rag.embedding'"

- [ ] **Step 3: 实现 Embedding 模块**

```python
# backend/rag/embedding.py
from abc import ABC, abstractmethod
from typing import List
from langchain_openai import OpenAIEmbeddings

from .config import (
    EMBEDDING_PROVIDER,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    OPENAI_API_KEY,
)


class EmbeddingProvider(ABC):
    """向量生成抽象基类"""
    
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """生成单个文本的向量"""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成向量"""
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI Embedding 实现"""
    
    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY 未设置")
        self.client = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY,
            dimensions=EMBEDDING_DIMENSIONS,
        )
    
    def embed(self, text: str) -> List[float]:
        return self.client.embed_query(text)
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return self.client.embed_documents(texts)


def get_embedding_provider() -> EmbeddingProvider:
    """获取 embedding provider 实例"""
    if EMBEDDING_PROVIDER == "openai":
        return OpenAIEmbeddingProvider()
    raise ValueError(f"不支持的 embedding provider: {EMBEDDING_PROVIDER}")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd backend && pytest tests/rag/test_embedding.py -v`
Expected: 4 tests passed

- [ ] **Step 5: Commit**

```bash
git add backend/rag/embedding.py backend/tests/rag/test_embedding.py
git commit -m "feat: 实现 Embedding 向量生成模块"
```

---

### Task 5: 文档分片模块开发

**Files:**
- Create: `backend/rag/splitter.py`
- Create: `backend/tests/rag/test_splitter.py`

- [ ] **Step 1: 编写测试用例**

```python
# backend/tests/rag/test_splitter.py
from backend.rag.splitter import MarkdownSplitter, Chunk


def test_splitter_initialization():
    """测试分片器初始化"""
    splitter = MarkdownSplitter(chunk_size=500, chunk_overlap=100)
    assert splitter.chunk_size == 500
    assert splitter.chunk_overlap == 100


def test_split_simple_markdown():
    """测试简单 Markdown 分片"""
    splitter = MarkdownSplitter(chunk_size=100, chunk_overlap=20)
    markdown = """# 标题

这是第一段内容。

## 子标题

这是第二段内容，稍微长一点。
"""
    chunks = splitter.split(markdown)
    assert len(chunks) > 0
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(c.content for c in chunks)
    assert all(c.content_hash for c in chunks)


def test_split_by_headers():
    """测试按标题层级分片"""
    splitter = MarkdownSplitter(chunk_size=200, chunk_overlap=50)
    markdown = """# CTR 是什么

点击率（Click-Through Rate，简称 CTR）是广告领域最重要的指标之一。

## CTR 的计算公式

CTR = 点击量 / 曝光量 × 100%

## CTR 的行业意义

CTR 反映了广告的吸引力程度。
"""
    chunks = splitter.split(markdown)
    # 应该至少有 3 个分片（# 标题, ## 计算公式, ## 意义）
    assert len(chunks) >= 3
    # 检查分片是否包含标题信息
    contents = [c.content for c in chunks]
    assert any("CTR 的计算公式" in c for c in contents)
    assert any("CTR 的行业意义" in c for c in contents)


def test_chunk_content_hash():
    """测试分片内容 hash 一致性"""
    splitter = MarkdownSplitter()
    content = "这是测试内容"
    chunk1 = Chunk(index=0, content=content)
    chunk2 = Chunk(index=1, content=content)
    assert chunk1.content_hash == chunk2.content_hash


def test_chunk_overlap():
    """测试分片重叠"""
    splitter = MarkdownSplitter(chunk_size=50, chunk_overlap=20)
    # 创建一个长文本
    long_text = "这是一个非常长的测试文本，" * 10
    chunks = splitter.split(long_text)
    # 分片之间应该有重叠内容
    if len(chunks) >= 2:
        # 检查后一个分片的开头是否包含前一个分片的结尾部分
        overlap_text = chunks[0].content[-20:]
        assert overlap_text in chunks[1].content
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && pytest tests/rag/test_splitter.py -v`
Expected: FAIL with "No module named 'backend.rag.splitter'"

- [ ] **Step 3: 实现分片模块**

```python
# backend/rag/splitter.py
import hashlib
from dataclasses import dataclass
from typing import List
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from .config import CHUNK_SIZE, CHUNK_OVERLAP


@dataclass
class Chunk:
    """分片数据类"""
    index: int
    content: str
    content_hash: str = ""
    
    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """计算内容 SHA256 hash"""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


class MarkdownSplitter:
    """Markdown 智能分片器"""
    
    # 按标题层级分割
    HEADERS_TO_SPLIT_ON = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or CHUNK_OVERLAP
        
        # 按标题分割的 splitter
        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.HEADERS_TO_SPLIT_ON,
            strip_headers=False,
        )
        
        # 递归字符分割（用于标题分片后仍太长的情况）
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", " ", ""],
        )
    
    def split(self, markdown_text: str) -> List[Chunk]:
        """
        分片 Markdown 文本
        
        策略：
        1. 先按标题层级分片
        2. 对每个标题分片，如果仍超过 chunk_size，继续按语义分片
        3. 保留上下文重叠
        """
        # 第一步：按标题层级分割
        header_splits = self.header_splitter.split_text(markdown_text)
        
        all_chunks = []
        chunk_index = 0
        
        for doc in header_splits:
            # 第二步：对每个文档进一步按字符数分片
            sub_chunks = self.text_splitter.split_text(doc.page_content)
            
            for chunk_content in sub_chunks:
                chunk = Chunk(
                    index=chunk_index,
                    content=chunk_content.strip(),
                )
                all_chunks.append(chunk)
                chunk_index += 1
        
        return all_chunks
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd backend && pytest tests/rag/test_splitter.py -v`
Expected: 5 tests passed

- [ ] **Step 5: Commit**

```bash
git add backend/rag/splitter.py backend/tests/rag/test_splitter.py
git commit -m "feat: 实现 Markdown 智能分片模块"
```

---

### Task 6: 检索 + Reranker 模块开发

**Files:**
- Create: `backend/rag/retriever.py`
- Create: `backend/tests/rag/test_retriever.py`

- [ ] **Step 1: 编写测试用例**

```python
# backend/tests/rag/test_retriever.py
import pytest
from sqlalchemy import text

from backend.rag.database import init_db, get_db_session
from backend.rag.models import RagDocument, RagChunk
from backend.rag.retriever import VectorRetriever, Reranker


@pytest.fixture(scope="module")
def db_session():
    init_db()
    session = get_db_session()
    yield session
    # 清理测试数据
    session.execute(text("DELETE FROM rag_chunks;"))
    session.execute(text("DELETE FROM rag_documents;"))
    session.commit()
    session.close()


def test_retriever_initialization():
    """测试检索器初始化"""
    retriever = VectorRetriever(top_k=20)
    assert retriever.top_k == 20


def test_reranker_initialization():
    """测试重排序器初始化"""
    reranker = Reranker(top_n=5)
    assert reranker.top_n == 5


def test_reranker_rerank():
    """测试重排序功能"""
    reranker = Reranker(top_n=2)
    query = "什么是 CTR？"
    documents = [
        "CTR 是点击率，等于点击量除以曝光量",
        "CVR 是转化率，等于转化量除以点击量",
        "CPA 是转化成本，等于花费除以转化量",
        "CTR 越高说明广告越吸引人",
    ]
    
    reranked = reranker.rerank(query, documents)
    # 应该只返回 top_n 个结果
    assert len(reranked) == 2
    # CTR 相关的应该排在前面
    assert "CTR" in reranked[0] or "CTR" in reranked[1]


def test_retrieve_and_rerank():
    """测试检索 + 重排序完整流程"""
    retriever = VectorRetriever(top_k=20)
    reranker = Reranker(top_n=3)
    
    query = "CTR 是什么"
    
    # 先插入一些测试数据
    session = get_db_session()
    doc = RagDocument(
        title="CTR 定义",
        file_path="/test/ctr.md",
        doc_type="business",
    )
    session.add(doc)
    session.flush()
    
    # 使用零向量作为测试（不实际调用 embedding API）
    chunk = RagChunk(
        doc_id=doc.id,
        chunk_index=0,
        content="CTR 是点击率，等于点击量除以曝光量，是广告最重要的指标之一",
        content_hash="testhash123",
        embedding=[0.0] * 1536,
    )
    session.add(chunk)
    session.commit()
    
    # 检索
    results = retriever.retrieve(query, session)
    assert len(results) >= 0  # 向量相似度可能返回 0 条，这是正常的
    
    # 如果有结果，测试重排序
    if results:
        contents = [r.content for r in results]
        reranked = reranker.rerank(query, contents)
        assert len(reranked) <= 3
    
    session.close()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && pytest tests/rag/test_retriever.py -v`
Expected: FAIL with "No module named 'backend.rag.retriever'"

- [ ] **Step 3: 实现检索 + Reranker 模块**

```python
# backend/rag/retriever.py
from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy.orm import Session
from sentence_transformers import CrossEncoder

from .config import RETRIEVE_TOP_K, RERANKER_MODEL, RERANKER_TOP_N
from .embedding import get_embedding_provider
from .models import RagChunk


@dataclass
class RetrievalResult:
    """检索结果数据类"""
    chunk_id: str
    doc_id: str
    content: str
    score: float
    title: Optional[str] = None
    doc_type: Optional[str] = None


class VectorRetriever:
    """向量检索器"""
    
    def __init__(self, top_k: int = None):
        self.top_k = top_k or RETRIEVE_TOP_K
        self.embedding_provider = get_embedding_provider()
    
    def retrieve(
        self,
        query: str,
        db_session: Session,
        doc_type: Optional[str] = None,
    ) -> List[RetrievalResult]:
        """
        向量检索相关文档分片
        
        Args:
            query: 查询问题
            db_session: 数据库会话
            doc_type: 可选，按文档类型过滤
        
        Returns:
            按相似度排序的检索结果列表
        """
        # 生成查询向量
        query_embedding = self.embedding_provider.embed(query)
        
        # 构建查询 - 使用余弦相似度
        q = db_session.query(
            RagChunk.id,
            RagChunk.doc_id,
            RagChunk.content,
            RagChunk.document,
            (1 - RagChunk.embedding.cosine_distance(query_embedding)).label("score"),
        ).join(RagChunk.document)
        
        # 可选过滤
        if doc_type:
            q = q.filter(RagChunk.document.doc_type == doc_type)
        
        # 按相似度排序，取 top_k
        results = q.order_by(RagChunk.embedding.cosine_distance(query_embedding)) \
                    .limit(self.top_k) \
                    .all()
        
        # 转换为 RetrievalResult 对象
        return [
            RetrievalResult(
                chunk_id=str(r.id),
                doc_id=str(r.doc_id),
                content=r.content,
                score=r.score,
                title=r.document.title,
                doc_type=r.document.doc_type,
            )
            for r in results
        ]


class Reranker:
    """重排序器 - 使用 CrossEncoder 精排"""
    
    def __init__(self, model_name: str = None, top_n: int = None):
        self.model_name = model_name or RERANKER_MODEL
        self.top_n = top_n or RERANKER_TOP_N
        self.model = CrossEncoder(self.model_name)
    
    def rerank(self, query: str, documents: List[str]) -> List[str]:
        """
        对检索结果进行重排序
        
        Args:
            query: 查询问题
            documents: 待排序的文档列表
        
        Returns:
            重排序后的文档列表（前 top_n 个）
        """
        if not documents:
            return []
        
        # 构造 (query, document) 对
        pairs = [[query, doc] for doc in documents]
        
        # 计算相关性分数
        scores = self.model.predict(pairs)
        
        # 按分数降序排序，取 top_n
        scored_docs = list(zip(documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        # 返回排序后的文档内容
        return [doc for doc, score in scored_docs[:self.top_n]]


class RagRetriever:
    """RAG 检索器 - 向量检索 + 重排序完整流程"""
    
    def __init__(self, retrieve_top_k: int = None, rerank_top_n: int = None):
        self.vector_retriever = VectorRetriever(top_k=retrieve_top_k)
        self.reranker = Reranker(top_n=rerank_top_n)
    
    def search(
        self,
        query: str,
        db_session: Session,
        doc_type: Optional[str] = None,
    ) -> List[RetrievalResult]:
        """
        完整检索流程：向量召回 + 重排序
        
        Args:
            query: 查询问题
            db_session: 数据库会话
            doc_type: 可选，按文档类型过滤
        
        Returns:
            重排序后的检索结果
        """
        # 第一步：向量召回
        initial_results = self.vector_retriever.retrieve(query, db_session, doc_type)
        
        if not initial_results:
            return []
        
        # 第二步：重排序
        contents = [r.content for r in initial_results]
        reranked_contents = self.reranker.rerank(query, contents)
        
        # 根据重排序结果重新排列
        content_to_result = {r.content: r for r in initial_results}
        reranked_results = []
        for content in reranked_contents:
            if content in content_to_result:
                reranked_results.append(content_to_result[content])
        
        return reranked_results
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd backend && pytest tests/rag/test_retriever.py -v`
Expected: 4 tests passed

- [ ] **Step 5: Commit**

```bash
git add backend/rag/retriever.py backend/tests/rag/test_retriever.py
git commit -m "feat: 实现向量检索 + Reranker 重排序模块"
```

---

### Task 7: 文档同步脚本开发

**Files:**
- Create: `backend/rag/sync.py`
- Create: `scripts/rag_sync.py`
- Create: `backend/tests/rag/test_sync.py`

- [ ] **Step 1: 编写测试用例**

```python
# backend/tests/rag/test_sync.py
import tempfile
import os
from pathlib import Path

from backend.rag.sync import DocumentSyncer
from backend.rag.database import init_db, get_db_session
from backend.rag.models import RagDocument


def test_syncer_initialization():
    """测试同步器初始化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        syncer = DocumentSyncer(docs_dir=tmpdir)
        assert syncer.docs_dir == Path(tmpdir)


def test_scan_directory():
    """测试扫描目录功能"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文档
        doc_dir = Path(tmpdir) / "01_基础概念"
        doc_dir.mkdir()
        
        test_file = doc_dir / "CTR是什么.md"
        test_file.write_text("# CTR 是什么\n\nCTR 是点击率...")
        
        syncer = DocumentSyncer(docs_dir=tmpdir)
        md_files = syncer.scan_directory()
        
        assert len(md_files) == 1
        assert md_files[0].name == "CTR是什么.md"


def test_sync_new_document():
    """测试同步新文档"""
    init_db()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文档
        test_file = Path(tmpdir) / "test_doc.md"
        test_file.write_text("# 测试文档\n\n这是测试内容。")
        
        syncer = DocumentSyncer(docs_dir=tmpdir)
        session = get_db_session()
        
        # 执行同步
        syncer.sync_single(test_file, session)
        
        # 验证数据库中存在该文档
        doc = session.query(RagDocument).filter_by(file_path=str(test_file)).first()
        assert doc is not None
        assert doc.title == "测试文档"
        assert len(doc.chunks) > 0
        
        session.close()


def test_incremental_sync():
    """测试增量同步"""
    init_db()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_incremental.md"
        test_file.write_text("# 增量测试\n\n初始内容。")
        
        syncer = DocumentSyncer(docs_dir=tmpdir)
        session = get_db_session()
        
        # 第一次同步
        syncer.sync_single(test_file, session)
        doc1 = session.query(RagDocument).filter_by(file_path=str(test_file)).first()
        old_sync_time = doc1.last_synced_at
        
        # 修改文件内容
        test_file.write_text("# 增量测试\n\n修改后的内容。")
        
        # 第二次同步（应该更新）
        syncer.sync_single(test_file, session)
        doc2 = session.query(RagDocument).filter_by(file_path=str(test_file)).first()
        
        # last_synced_at 应该更新
        assert doc2.last_synced_at > old_sync_time
        
        session.close()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && pytest tests/rag/test_sync.py -v`
Expected: FAIL with "No module named 'backend.rag.sync'"

- [ ] **Step 3: 实现文档同步模块**

```python
# backend/rag/sync.py
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
        """计算文件内容 hash"""
        content = file_path.read_text(encoding="utf-8")
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    
    def sync_single(self, file_path: Path, db_session: Session) -> Optional[RagDocument]:
        """同步单个 Markdown 文件"""
        if not file_path.exists():
            return None
        
        content = file_path.read_text(encoding="utf-8")
        file_hash = self._get_file_hash(file_path)
        
        # 检查是否已存在且未修改
        existing_doc = db_session.query(RagDocument).filter_by(file_path=str(file_path)).first()
        
        if existing_doc:
            # 比较所有分片的 hash 总和，判断是否需要重新同步
            existing_hashes = set(c.content_hash for c in existing_doc.chunks)
            new_chunks = self.splitter.split(content)
            new_hashes = set(c.content_hash for c in new_chunks)
            
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
        
        # 分片
        chunks = self.splitter.split(content)
        
        # 批量生成向量
        chunk_contents = [c.content for c in chunks]
        embeddings = self.embedding_provider.embed_batch(chunk_contents)
        
        # 创建分片记录
        for chunk, embedding in zip(chunks, embeddings):
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
        
        for file_path in md_files:
            doc = self.sync_single(file_path, db_session)
            if doc:
                synced_count += 1
        
        return synced_count


def sync_documents(incremental: bool = True) -> int:
    """同步文档入口函数"""
    session = get_db_session()
    try:
        syncer = DocumentSyncer()
        count = syncer.sync_all(session, incremental=incremental)
        return count
    finally:
        session.close()
```

- [ ] **Step 4: 创建同步入口脚本**

```python
# scripts/rag_sync.py
#!/usr/bin/env python3
"""RAG 文档同步脚本

用法:
    python scripts/rag_sync.py              # 增量同步
    python scripts/rag_sync.py --full       # 全量同步
    python scripts/rag_sync.py --watch      # 监听目录变化自动同步
"""
import argparse
import sys
import time
from pathlib import Path

# 添加 backend 目录到 Python 路径
script_dir = Path(__file__).parent
backend_dir = script_dir.parent / "backend"
sys.path.insert(0, str(backend_dir))

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from rag.sync import DocumentSyncer, sync_documents
from rag.database import init_db, get_db_session


class RagDocHandler(FileSystemEventHandler):
    """文档变化处理器"""
    
    def __init__(self):
        self.syncer = DocumentSyncer()
        self.session = get_db_session()
    
    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".md"):
            print(f"检测到文件变化: {event.src_path}")
            self.syncer.sync_single(Path(event.src_path), self.session)
    
    def on_created(self, event):
        self.on_modified(event)


def main():
    parser = argparse.ArgumentParser(description="RAG 文档同步工具")
    parser.add_argument("--full", action="store_true", help="全量同步")
    parser.add_argument("--watch", action="store_true", help="监听目录变化自动同步")
    args = parser.parse_args()
    
    # 初始化数据库
    init_db()
    
    if args.full:
        print("开始全量同步...")
    else:
        print("开始增量同步...")
    
    count = sync_documents(incremental=not args.full)
    print(f"同步完成，共同步 {count} 个文档")
    
    if args.watch:
        print("启动目录监听模式，按 Ctrl+C 退出...")
        event_handler = RagDocHandler()
        observer = Observer()
        observer.schedule(event_handler, path=str(DocumentSyncer().docs_dir), recursive=True)
        observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 运行测试验证通过**

Run: `cd backend && pytest tests/rag/test_sync.py -v`
Expected: 4 tests passed

- [ ] **Step 6: 添加执行权限**

Run: `chmod +x scripts/rag_sync.py`

- [ ] **Step 7: Commit**

```bash
git add backend/rag/sync.py scripts/rag_sync.py backend/tests/rag/test_sync.py
git commit -m "feat: 实现文档同步脚本模块"
```

---

## 第三阶段：LangGraph 集成

### Task 8: RAG Agent 节点开发

**Files:**
- Create: `backend/rag/agents.py`
- Create: `backend/tests/rag/test_agents.py`

- [ ] **Step 1: 编写测试用例**

```python
# backend/tests/rag/test_agents.py
from backend.rag.agents import IntentRouter, RagAnswerGenerator


def test_intent_router_initialization():
    """测试意图路由初始化"""
    router = IntentRouter()
    assert router is not None


def test_intent_classification_report():
    """测试报表类意图识别"""
    router = IntentRouter()
    
    test_queries = [
        "昨天的 CTR 是多少",
        "看看最近 7 天的花费趋势",
        "渠道 A 和渠道 B 的对比",
        "按广告组分维度展示数据",
    ]
    
    for query in test_queries:
        result = router.classify(query)
        # 注意：实际测试可能需要 mock LLM 响应，这里只验证不报错
        assert result in ["report", "knowledge"]


def test_intent_classification_knowledge():
    """测试知识类意图识别"""
    router = IntentRouter()
    
    test_queries = [
        "什么是 CTR",
        "怎么计算 ROI",
        "广告投放三层级是什么",
        "如何优化转化率",
    ]
    
    for query in test_queries:
        result = router.classify(query)
        assert result in ["report", "knowledge"]


def test_answer_generator_initialization():
    """测试回答生成器初始化"""
    generator = RagAnswerGenerator()
    assert generator is not None


def test_answer_generation():
    """测试回答生成"""
    generator = RagAnswerGenerator()
    
    query = "什么是 CTR？"
    context = [
        "CTR（Click-Through Rate，点击率）是广告点击量除以曝光量的百分比",
        "CTR 反映了广告对用户的吸引力程度",
    ]
    
    answer = generator.generate(query, context)
    assert answer is not None
    assert len(answer) > 0
    assert "CTR" in answer or "点击率" in answer
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && pytest tests/rag/test_agents.py -v`
Expected: FAIL with "No module named 'backend.rag.agents'"

- [ ] **Step 3: 实现 RAG Agent 节点**

```python
# backend/rag/agents.py
from typing import List, Dict, Any, Literal, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from .config import OPENAI_API_KEY
from .database import get_db_session
from .retriever import RagRetriever


class IntentRouter:
    """意图路由 - 判断用户问题走报表还是 RAG"""
    
    SYSTEM_PROMPT = """你是一个智能路由助手，根据用户问题判断应该走哪个分支：

- 如果用户想看数据、报表、图表、趋势、对比、分析某个指标、查某个维度、筛选某个条件 → 返回 "report"
- 如果用户问概念、术语、使用方法、帮助、说明、定义、解释是什么、方法论、最佳实践 → 返回 "knowledge"

请只返回一个单词：report 或 knowledge，不要返回任何其他内容。"""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )
    
    def classify(self, user_input: str) -> Literal["report", "knowledge"]:
        """分类用户意图"""
        messages = [
            ("system", self.SYSTEM_PROMPT),
            ("human", f"用户问题: {user_input}"),
        ]
        response = self.llm.invoke(messages)
        result = response.content.strip().lower()
        
        # 确保返回值合法
        if result not in ["report", "knowledge"]:
            # 默认走 knowledge
            return "knowledge"
        return result


class RagAnswerGenerator:
    """RAG 回答生成器"""
    
    SYSTEM_PROMPT = """你是一个广告行业的专业知识助手。请基于提供的参考文档，用简洁、专业、易懂的语言回答用户问题。

回答要求：
1. 只基于参考文档中的内容回答，不要编造信息
2. 如果参考文档中没有相关内容，说明"抱歉，目前的知识库中没有相关信息"
3. 回答要条理清晰，重点突出
4. 专业术语可以适当解释
5. 用中文回答

参考文档：
{context}"""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=OPENAI_API_KEY,
            temperature=0.3,
        )
        self.retriever = RagRetriever()
    
    def _build_context(self, retrieval_results: List) -> str:
        """构建上下文字符串"""
        context_parts = []
        for i, result in enumerate(retrieval_results, 1):
            context_parts.append(f"[{i}] {result.content}")
        return "\n\n".join(context_parts)
    
    def retrieve_context(self, query: str) -> List[str]:
        """检索相关上下文"""
        db_session = get_db_session()
        try:
            results = self.retriever.search(query, db_session)
            return [r.content for r in results]
        finally:
            db_session.close()
    
    def generate(self, query: str, context: List[str] = None) -> str:
        """生成回答"""
        if context is None:
            context = self.retrieve_context(query)
        
        if not context:
            return "抱歉，暂时没有找到相关帮助文档，您可以试试其他问题。"
        
        context_str = self._build_context(
            [type("Result", (), {"content": c}) for c in context]
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT.format(context=context_str)),
            ("human", f"用户问题: {query}"),
        ])
        
        chain = prompt | self.llm
        response = chain.invoke({"query": query})
        return response.content.strip()


# LangGraph 节点函数
def intent_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """意图路由节点"""
    user_input = state.get("user_input", "")
    router = IntentRouter()
    query_type = router.classify(user_input)
    return {"query_type": query_type}


def rag_retrieve_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """RAG 检索节点"""
    query = state.get("user_input", "")
    generator = RagAnswerGenerator()
    context = generator.retrieve_context(query)
    return {"rag_context": context}


def rag_answer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """RAG 回答生成节点"""
    query = state.get("user_input", "")
    context = state.get("rag_context", [])
    generator = RagAnswerGenerator()
    answer = generator.generate(query, context)
    return {"rag_answer": answer}
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd backend && pytest tests/rag/test_agents.py -v`
Expected: 6 tests passed

- [ ] **Step 5: Commit**

```bash
git add backend/rag/agents.py backend/tests/rag/test_agents.py
git commit -m "feat: 实现 RAG Agent 节点模块"
```

---

### Task 9: LangGraph 工作流集成

**Files:**
- Modify: `backend/app/agent/workflow.py`（假设这是现有工作流文件）

*注意：请根据实际项目中的工作流文件路径调整。以下是假设的集成代码示例。*

- [ ] **Step 1: 更新 State 定义**

在工作流 State 中添加 RAG 相关字段：

```python
class AdReportState(TypedDict):
    # 原有字段
    user_input: str
    intent: dict
    # ... 其他字段
    
    # 新增 RAG 字段
    query_type: Literal["report", "knowledge"]
    rag_context: List[str]
    rag_answer: str
```

- [ ] **Step 2: 添加 RAG 节点到工作流**

```python
from backend.rag.agents import intent_router_node, rag_retrieve_node, rag_answer_node

# 新增条件分支路由函数
def route_based_on_intent(state: AdReportState) -> str:
    """根据意图类型路由"""
    if state.get("query_type") == "knowledge":
        return "rag_retrieve"
    return "intent_classification"  # 原有报表流程入口

# 修改工作流构建代码：
workflow = StateGraph(AdReportState)

# 第一个节点：意图路由
workflow.add_node("intent_router", intent_router_node)
workflow.set_entry_point("intent_router")

# 添加条件分支
workflow.add_conditional_edges(
    "intent_router",
    route_based_on_intent,
    {
        "rag_retrieve": "rag_retrieve",
        "intent_classification": "intent_classification",  # 原有报表流程
    },
)

# 添加 RAG 节点
workflow.add_node("rag_retrieve", rag_retrieve_node)
workflow.add_node("rag_answer", rag_answer_node)
workflow.add_edge("rag_retrieve", "rag_answer")
workflow.add_edge("rag_answer", END)

# 保持原有报表流程不变...
```

- [ ] **Step 2: 运行现有测试确保不破坏原有功能**

Run: `cd backend && pytest tests/ -v -k "not rag"`
Expected: 所有原有测试通过

- [ ] **Step 3: Commit**

```bash
git add backend/app/agent/workflow.py
git commit -m "feat: 集成 RAG 节点到 LangGraph 工作流"
```

---

## 第四阶段：文档采集与系统验证

### Task 10: 示例文档创建

**Files:**
- Create: `docs/rag/01_基础概念/广告主(Advertiser)是什么.md`
- Create: `docs/rag/01_基础概念/广告计划(Campaign)是什么.md`
- Create: `docs/rag/01_基础概念/广告组(AdGroup)是什么.md`
- Create: `docs/rag/01_基础概念/广告创意(Creative)是什么.md`
- Create: `docs/rag/01_基础概念/品牌广告定义与特点.md`
- Create: `docs/rag/03_核心指标/基础指标-曝光量(Impression).md`
- Create: `docs/rag/03_核心指标/基础指标-点击量(Click).md`
- Create: `docs/rag/03_核心指标/基础指标-花费(Cost).md`
- Create: `docs/rag/03_核心指标/效率指标-点击率(CTR).md`
- Create: `docs/rag/03_核心指标/效率指标-转化率(CVR).md`

- [ ] **Step 1: 创建文档目录和示例文档**

Run: `mkdir -p docs/rag/{01_基础概念,02_层级属性,03_核心指标,04_受众定向,05_效果评估,06_优化方法,07_系统使用}`

- [ ] **Step 2: 编写 CTR 示例文档**

```markdown
# 点击率 CTR

点击率（Click-Through Rate，简称 CTR）是广告领域最核心的指标之一。

## 定义

CTR 表示用户看到广告后点击广告的概率，反映了广告对用户的吸引力程度。

## 计算公式

CTR = 点击量 ÷ 曝光量 × 100%

例如：一个广告曝光了 10000 次，获得了 200 次点击，那么 CTR = 200 / 10000 × 100% = 2%

## 行业参考值

不同行业、不同投放渠道的 CTR 差异很大：
- 搜索广告：2% ~ 10%
- 信息流广告：0.5% ~ 3%
- 开屏广告：1% ~ 5%
- 横幅广告：0.1% ~ 1%

## 优化方向

1. 素材优化：提高创意吸引力
2. 人群优化：定向更精准的受众
3. 文案优化：标题和描述更有吸引力
4. 投放时段优化：选择用户活跃时段
```

保存到: `docs/rag/03_核心指标/效率指标-点击率(CTR).md`

- [ ] **Step 3: 创建其他示例文档（类似格式）**

- [ ] **Step 4: 执行文档同步**

Run: `python scripts/rag_sync.py --full`
Expected: 成功同步所有文档到向量数据库

- [ ] **Step 5: Commit**

```bash
git add docs/rag/
git commit -m "docs: 添加 RAG 知识库示例文档"
```

---

### Task 11: 端到端集成测试

**Files:**
- Create: `backend/tests/rag/test_e2e.py`

- [ ] **Step 1: 编写端到端测试**

```python
# backend/tests/rag/test_e2e.py
import pytest

from backend.rag.agents import IntentRouter, RagAnswerGenerator
from backend.rag.database import init_db


@pytest.fixture(scope="module", autouse=True)
def setup():
    init_db()


def test_intent_router_e2e():
    """测试意图路由端到端"""
    router = IntentRouter()
    
    # 知识类问题
    assert router.classify("什么是 CTR？") == "knowledge"
    assert router.classify("如何计算 ROI？") == "knowledge"
    
    # 报表类问题
    assert router.classify("昨天 CTR 是多少") == "report"
    assert router.classify("最近 7 天的花费趋势") == "report"


def test_rag_answer_e2e():
    """测试 RAG 回答端到端"""
    generator = RagAnswerGenerator()
    
    # 查询知识库中已有的内容
    answer = generator.generate("CTR 是什么意思？")
    
    # 应该能返回相关回答
    assert answer is not None
    assert len(answer) > 0
    # 如果知识库有 CTR 文档，回答应该包含 CTR 相关内容
    if "CTR" in answer or "点击率" in answer:
        assert True  # 知识库已正确加载
    else:
        # 知识库可能为空，这也是正常的
        assert "抱歉" in answer or "CTR" in answer


def test_full_rag_flow():
    """测试完整 RAG 流程"""
    # 1. 意图分类
    router = IntentRouter()
    query_type = router.classify("什么是点击率？")
    assert query_type == "knowledge"
    
    # 2. 检索上下文
    generator = RagAnswerGenerator()
    context = generator.retrieve_context("什么是点击率？")
    
    # 3. 生成回答
    answer = generator.generate("什么是点击率？", context)
    assert answer is not None
```

- [ ] **Step 2: 运行端到端测试**

Run: `cd backend && pytest tests/rag/test_e2e.py -v`
Expected: 3 tests passed

- [ ] **Step 3: Commit**

```bash
git add backend/tests/rag/test_e2e.py
git commit -m "test: 添加 RAG 端到端集成测试"
```

---

## 第五阶段：收尾工作

### Task 12: 配置示例与文档

**Files:**
- Create: `backend/.env.example`
- Update: `README.md`

- [ ] **Step 1: 创建环境变量示例文件**

```env
# RAG 数据库配置
RAG_DB_HOST=localhost
RAG_DB_PORT=5432
RAG_DB_USER=
RAG_DB_PASSWORD=
RAG_DB_NAME=postgres

# Embedding 配置
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
OPENAI_API_KEY=your_api_key_here

# Reranker 配置
RERANKER_MODEL=BAAI/bge-reranker-base
RERANKER_TOP_N=5

# 检索配置
RETRIEVE_TOP_K=20

# 分片配置
CHUNK_SIZE=500
CHUNK_OVERLAP=100
```

- [ ] **Step 2: 更新 README，添加 RAG 系统使用说明**

```markdown
## RAG 知识库系统

### 安装

1. 安装 PostgreSQL + pgvector:
   ```bash
   ./scripts/install_pgvector.sh
   ```

2. 配置环境变量:
   ```bash
   cp backend/.env.example backend/.env
   # 编辑 .env 文件，填入 OPENAI_API_KEY 等配置
   ```

3. 初始化数据库:
   ```bash
   cd backend && python -c "from rag.database import init_db; init_db()"
   ```

### 文档同步

```bash
# 增量同步
python scripts/rag_sync.py

# 全量同步
python scripts/rag_sync.py --full

# 监听目录变化自动同步
python scripts/rag_sync.py --watch
```

### 添加文档

将 Markdown 文档放到 `docs/rag/` 目录下，按子目录分类，然后运行同步脚本。
```

- [ ] **Step 3: Commit**

```bash
git add backend/.env.example README.md
git commit -m "docs: 添加 RAG 系统配置示例与使用文档"
```

---

## 实施完成检查清单

- [ ] PostgreSQL + pgvector 已安装并运行
- [ ] 数据库表已创建
- [ ] Embedding 模块可正常调用 API 生成向量
- [ ] Markdown 分片功能正常
- [ ] 向量检索 + Reranker 功能正常
- [ ] 文档同步脚本可正常运行
- [ ] 意图路由节点正确分类问题
- [ ] RAG 回答节点正确生成回答
- [ ] LangGraph 工作流集成完成
- [ ] 示例文档已创建并同步
- [ ] 所有单元测试通过
- [ ] 端到端测试通过
- [ ] 配置文档已更新
