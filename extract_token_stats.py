#!/usr/bin/env python3
"""
从 app.log 提取每个测试请求对应的所有 llm_usage 统计
汇总到完整的 61 个测试结果中
"""

import json
import re
import os
from typing import Dict, List, Optional, Any


def extract_token_stats(log_path: str) -> Dict[str, int]:
    """
    从 app.log 提取每个 request_id 的 total_prompt_tokens
    返回 {request_id: total_prompt_tokens}
    """
    stats: Dict[str, int] = {}

    with open(log_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or 'llm_usage' not in line:
                continue

            # 提取所有 [] 中的内容
            # 格式: ... [INFO] [request_id] [session_id] [llm_usage] {json}
            brackets = re.findall(r'\[([^\]]+)\]', line)
            if len(brackets) < 4:
                continue

            # brackets[0] = INFO, brackets[1] = request_id, brackets[2] = session_id, brackets[3] = llm_usage
            request_id = brackets[1]
            if request_id == '-':
                continue  # empty request_id

            # 提取 json 部分 - 在最后一个 ] 之后
            json_start = line.rfind(']') + 1
            json_str = line[json_start:].strip()

            try:
                data = json.loads(json_str)
                prompt_tokens = data.get('prompt_tokens', 0)
                if request_id not in stats:
                    stats[request_id] = 0
                stats[request_id] += prompt_tokens
            except Exception:
                continue

    return stats


def main():
    # 读取三个结果文件
    all_tests: List[Dict[str, Any]] = []

    # e2e
    with open('e2e_test_results.json', 'r') as f:
        e2e_data = json.load(f)
        for result in e2e_data['results']:
            all_tests.append({
                'source': 'e2e',
                'test_id': result['test_id'],
                'test_name': result['test_name'],
                'attempts': result['retries'] + 1,
                'response_time': result['response_time'],
                'status': result['status'],
                'request_id': result.get('request_id'),
                'error_message': result.get('error_message'),
                'total_prompt_tokens': 0,
            })

    print(f"Loaded e2e: {len(all_tests)} tests")

    # part1
    with open('diversified_test_results_part1.json', 'r') as f:
        p1_data = json.load(f)
        for result in p1_data:
            all_tests.append({
                'source': 'part1',
                'test_id': result['test_id'],
                'test_name': result['test_name'],
                'attempts': result['attempts'],
                'response_time': result['response_time'],
                'status': result['status'],
                'request_id': result.get('request_id'),
                'error_message': result.get('error_message'),
                'total_prompt_tokens': 0,
            })

    print(f"Loaded part1: {len(p1_data)} tests")

    # part2
    with open('diversified_test_results_part2.json', 'r') as f:
        full_part2 = json.load(f)

    for result in full_part2:
        all_tests.append({
            'source': 'part2',
            'test_id': result['test_id'],
            'test_name': result['test_name'],
            'attempts': result['attempts'],
            'response_time': result['response_time'],
            'status': result['status'],
            'request_id': result.get('request_id'),
            'error_message': result.get('error_message'),
            'total_prompt_tokens': 0,
        })

    print(f"Added part2: {len(full_part2)} tests")

    # 提取 token 统计
    log_path = '/Users/simon/AL/DataAgent/backend/logs/app.log'
    token_stats = extract_token_stats(log_path)

    print(f"Extracted token stats for {len(token_stats)} unique request_ids")

    # 填充到每个测试
    total_tests = len(all_tests)
    total_success = sum(1 for t in all_tests if t['status'] == 'success')
    total_failed = sum(1 for t in all_tests if t['status'] != 'success')
    total_attempts = sum(t['attempts'] for t in all_tests)
    total_response_time = sum(t['response_time'] for t in all_tests)
    total_prompt_tokens = 0
    total_llm_calls = len(token_stats)

    matched = 0
    for test in all_tests:
        rid = test['request_id']
        if rid and rid in token_stats:
            test['total_prompt_tokens'] = token_stats[rid]
            total_prompt_tokens += token_stats[rid]
            matched += 1

    # 汇总输出
    summary = {
        'total_tests': total_tests,
        'success': total_success,
        'failed': total_failed,
        'total_attempts': total_attempts,
        'total_response_time_seconds': round(total_response_time, 2),
        'total_prompt_tokens': total_prompt_tokens,
        'avg_tokens_per_test': round(total_prompt_tokens / total_tests, 2) if total_tests > 0 else 0,
        'avg_tokens_per_llm_call': round(total_prompt_tokens / total_llm_calls, 2) if total_llm_calls > 0 else 0,
        'tests': all_tests,
    }

    with open('61_tests_full_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print("=" * 60)
    print("📊 61 个测试完整汇总")
    print("=" * 60)
    print(f"总测试用例: {total_tests}")
    print(f"成功: {total_success} ({total_success/total_tests*100:.1f}%)")
    print(f"失败: {total_failed}")
    print(f"总尝试次数: {total_attempts}")
    print(f"总响应时间: {round(total_response_time, 2)}s")
    print(f"总 prompt tokens: {total_prompt_tokens:,}")
    print(f"匹配 request_id: {matched}/{total_tests}")
    print(f"平均 tokens / 测试: {round(total_prompt_tokens / total_tests, 2):,}")
    if total_llm_calls > 0:
        print(f"平均 tokens / LLM 调用: {round(total_prompt_tokens / total_llm_calls, 2):,}")
    else:
        print("平均 tokens / LLM 调用: N/A (no llm_usage found)")
    print("=" * 60)
    print(f"\n结果已保存到: 61_tests_full_summary.json")


if __name__ == '__main__':
    main()
