import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 基础路径
BASE_DIR = Path(__file__).parent.parent
RAG_DOCS_DIR = BASE_DIR.parent.parent / "docs" / "rag"

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
