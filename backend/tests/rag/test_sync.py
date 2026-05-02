import tempfile
import os
from pathlib import Path

from src.rag.sync import DocumentSyncer
from src.rag.database import init_db, get_db_session
from src.rag.models import RagDocument


def test_syncer_initialization():
    """测试同步器初始化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        syncer = DocumentSyncer(docs_dir=Path(tmpdir))
        assert syncer.docs_dir == Path(tmpdir)


def test_scan_directory():
    """测试扫描目录功能"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文档
        doc_dir = Path(tmpdir) / "01_基础概念"
        doc_dir.mkdir()

        test_file = doc_dir / "CTR是什么.md"
        test_file.write_text("# CTR 是什么\n\nCTR 是点击率...")

        syncer = DocumentSyncer(docs_dir=Path(tmpdir))
        md_files = syncer.scan_directory()

        assert len(md_files) == 1
        assert md_files[0].name == "CTR是什么.md"


def test_extract_title():
    """测试提取标题功能"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.md"
        test_file.write_text("# 测试标题\n\n内容...")

        syncer = DocumentSyncer(docs_dir=Path(tmpdir))
        content = test_file.read_text(encoding="utf-8")
        title = syncer._extract_title(content, test_file)
        assert title == "测试标题"


def test_extract_doc_type():
    """测试提取文档类型功能"""
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_dir = Path(tmpdir) / "02_核心指标"
        doc_dir.mkdir()
        test_file = doc_dir / "CTR.md"
        test_file.write_text("# CTR\n\n内容...")

        syncer = DocumentSyncer(docs_dir=Path(tmpdir))
        doc_type = syncer._extract_doc_type(test_file)
        assert doc_type == "核心指标"


def test_sync_new_document():
    """测试同步新文档"""
    init_db()

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文档
        test_file = Path(tmpdir) / "test_doc.md"
        test_file.write_text("# 测试文档\n\n这是测试内容。")

        syncer = DocumentSyncer(docs_dir=Path(tmpdir))
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

        syncer = DocumentSyncer(docs_dir=Path(tmpdir))
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


def test_sync_all():
    """测试批量同步"""
    init_db()

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建多个测试文档
        (Path(tmpdir) / "doc1.md").write_text("# 文档1\n\n内容1")
        (Path(tmpdir) / "doc2.md").write_text("# 文档2\n\n内容2")

        syncer = DocumentSyncer(docs_dir=Path(tmpdir))
        session = get_db_session()

        count = syncer.sync_all(session)
        assert count == 2

        session.close()
