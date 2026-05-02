from src.rag.splitter import MarkdownSplitter, Chunk


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
