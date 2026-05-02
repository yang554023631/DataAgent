import pytest
from sqlalchemy import text

from src.rag.database import init_db, get_db_session, engine


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
