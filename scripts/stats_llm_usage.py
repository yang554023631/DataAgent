#!/usr/bin/env python3
"""
LLM 使用统计脚本
从日志文件中提取 LLM 调用记录，统计 prompt token 和响应时间

Usage:
    python scripts/stats_llm_usage.py <log_file>
"""

import json
import statistics
import sys


def main(log_file: str):
    """主函数"""
    tokens = []
    times = []

    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if '"event": "llm_call"' in line:
                try:
                    data = json.loads(line)
                    if 'prompt_tokens' in data:
                        tokens.append(data['prompt_tokens'])
                    if 'elapsed_ms' in data:
                        times.append(data['elapsed_ms'])
                except Exception as e:
                    print(f"Warning: failed to parse line: {e}")
                    continue

    if not tokens:
        print("No LLM call events found in log file.")
        return

    print("=== LLM 调用统计 ===\n")
    print(f"总调用次数: {len(tokens)}")
    print()
    print(f"平均 prompt token: {statistics.mean(tokens):.0f}")
    print(f"中位数 prompt token: {statistics.median(tokens):.0f}")
    print(f"最小 prompt token: {min(tokens):.0f}")
    print(f"最大 prompt token: {max(tokens):.0f}")
    print(f"总 prompt token: {sum(tokens):.0f}")
    print()

    if times:
        print(f"平均响应时间 (ms): {statistics.mean(times):.0f}")
        print(f"中位数响应时间 (ms): {statistics.median(times):.0f}")
        print(f"最小响应时间 (ms): {min(times):.0f}")
        print(f"最大响应时间 (ms): {max(times):.0f}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    main(sys.argv[1])
