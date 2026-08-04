import os
import logging
import tempfile
import pytest
from src.config.logging_config import setup_logging, ContextFilter
from src.config.context import set_request_id, set_session_id, request_id_var, session_id_var


def test_context_filter_injects_ids():
    """ContextFilter 正确注入 request_id 和 session_id"""
    # 设置上下文
    req_token = set_request_id("req-123")
    sess_token = set_session_id("sess-456")

    try:
        log_filter = ContextFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="test message", args=(), exc_info=None
        )
        result = log_filter.filter(record)
        assert result is True
        assert record.request_id == "req-123"
        assert record.session_id == "sess-456"
    finally:
        request_id_var.reset(req_token)
        session_id_var.reset(sess_token)


def test_context_filter_no_context():
    """无上下文时返回 -"""
    log_filter = ContextFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO,
        pathname="test.py", lineno=1,
        msg="test", args=(), exc_info=None
    )
    result = log_filter.filter(record)
    assert result is True
    assert record.request_id == "-"
    assert record.session_id == "-"


def test_setup_logging_creates_files(tmp_path, monkeypatch):
    """setup_logging 创建日志目录和文件"""
    # 临时修改配置
    from src.config import settings as s

    monkeypatch.setattr(s.settings, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(s.settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(s.settings, "LOG_BACKUP_DAYS", 30)

    setup_logging()

    log_dir = tmp_path / "logs"
    assert log_dir.exists()
    assert (log_dir / "app.log").exists()
    assert (log_dir / "error.log").exists()


def test_setup_logging_idempotent(tmp_path, monkeypatch):
    """重复调用 setup_logging 不会重复添加 handler"""
    from src.config import settings as s

    monkeypatch.setattr(s.settings, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(s.settings, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(s.settings, "LOG_BACKUP_DAYS", 30)

    setup_logging()
    handler_count_before = len(logging.getLogger().handlers)

    setup_logging()
    handler_count_after = len(logging.getLogger().handlers)

    assert handler_count_before == handler_count_after