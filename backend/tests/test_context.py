import pytest
from src.config.context import (
    get_request_id, set_request_id,
    get_session_id, set_session_id,
    truncate_log,
)


def test_truncate_log_short_text():
    """短文本不截断"""
    assert truncate_log("hello", 100) == "hello"


def test_truncate_log_exact_length():
    """正好等于max_len不截断"""
    text = "a" * 50
    assert truncate_log(text, 50) == text


def test_truncate_log_long_text():
    """长文本截断并标注总长度"""
    text = "a" * 2000
    result = truncate_log(text, 1000)
    assert len(result) > 1000  # 1000 + 后缀
    assert result.startswith("a" * 1000)
    assert "共2000字" in result


def test_truncate_log_chinese():
    """中文按字符数截断"""
    text = "你好" * 600  # 1200字
    result = truncate_log(text, 1000)
    assert result.endswith("... (共1200字)")
    assert len(result.replace("... (共1200字)", "")) == 1000


def test_truncate_log_empty():
    """空字符串"""
    assert truncate_log("", 100) == ""


def test_truncate_log_none_default_max_len():
    """默认max_len=1000"""
    text = "a" * 1500
    result = truncate_log(text)
    assert "共1500字" in result
    assert len(result.replace("... (共1500字)", "")) == 1000


def test_get_request_id_default():
    """默认返回 -"""
    assert get_request_id() == "-"


def test_set_and_get_request_id():
    """设置后可以读到"""
    token = set_request_id("test-req-123")
    assert get_request_id() == "test-req-123"
    # 重置
    from src.config.context import request_id_var
    request_id_var.reset(token)
    assert get_request_id() == "-"


def test_get_session_id_default():
    """默认返回 -"""
    assert get_session_id() == "-"


def test_set_and_get_session_id():
    """设置后可以读到"""
    token = set_session_id("sess-abc")
    assert get_session_id() == "sess-abc"
    # 重置
    from src.config.context import session_id_var
    session_id_var.reset(token)
    assert get_session_id() == "-"
