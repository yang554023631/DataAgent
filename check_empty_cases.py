#!/usr/bin/env python3
import json

with open('diversified_test_results.json', 'r') as f:
    data = json.load(f)

# 找出所有返回空的entity_table case
empty_cases = [c for c in data if c['error_message'] and '实体表格期望至少返回一条数据' in c['error_message']]

print(f"=== 总共 {len(empty_cases)} 个'实体表格返回空'case ===\n")

for case in empty_cases:
    print(f"测试ID: {case['test_id']}")
    print(f"Query: {case['query']}")
    print(f"分析类型: {case['analysis_type']}, 目标层级: {case['target_level']}")

    # 检查raw_response中advertiser_ids
    has_raw = 'raw_response' in case and case['raw_response']
    if has_raw and 'field_context' in case['raw_response']:
        fc = case['raw_response']['field_context']
        ads_ids = fc.get('advertiser_ids', 'NOT FOUND')
        print(f"advertiser_ids: {ads_ids}")

        # 如果有analysis_plan，看filter_steps
        if 'analysis_plan' in case['raw_response']:
            ap = case['raw_response']['analysis_plan']
            if 'filter_plan' in ap:
                fp = ap['filter_plan']
                steps = fp.get('steps', [])
                print(f"filter_plan 有 {len(steps)} 个步骤:")
                for s in steps:
                    print(f"  - step_{s['step_id']}: {s['step_type']} @ {s['level']}, index={s['index']}")

    print("-" * 60)
