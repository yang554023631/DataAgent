"""RAG 系统模块"""
import os
# 必须在导入任何使用 tokenizers 的模块之前设置
# 避免 forking 导致 LLM API 调用异常
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from .config import RAG_DOCS_DIR
from .database import init_db, get_db, get_db_session

__all__ = ["RAG_DOCS_DIR", "init_db", "get_db", "get_db_session"]
