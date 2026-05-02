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
backend_dir = script_dir / "backend"
sys.path.insert(0, str(backend_dir))

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

from src.rag.sync import DocumentSyncer, sync_documents
from src.rag.database import init_db, get_db_session


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
        if not HAS_WATCHDOG:
            print("错误: 请先安装 watchdog: pip install watchdog")
            sys.exit(1)

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
