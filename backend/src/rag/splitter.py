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
