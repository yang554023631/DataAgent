#!/usr/bin/env python3
"""
洞察规则验证脚本
真实查询ES数据，喂给规则引擎，看能检测出什么问题
"""
import sys
sys.path.insert(0, '.')

from src.tools.custom_report_client import build_es_query, parse_es_result, es_client
from src.tools.insight_rules import rule_engine
from src.models.insight import InsightResult

def print_insights(insights):
    """格式化打印洞察结果"""
    if not insights:
        print("  📊 未检测到显著问题或亮点")
        return

    problems = [i for i in insights if i.type.value == "problem"]
    highlights = [i for i in insights if i.type.value == "highlight"]

    if problems:
        print(f"\n  🔴 发现 {len(problems)} 个问题：")
        for p in problems:
            sev = " 🔴高" if p.severity.value == "high" else " 🟡中"
            print(f"    [{p.id}] {p.name} ({sev})")
            print(f"       证据: {p.evidence}")
            print(f"       建议: {p.suggestion}")
            print()

    if highlights:
        print(f"\n  🟢 发现 {len(highlights)} 个亮点：")
        for h in highlights:
            sev = " 🔥高" if h.severity.value == "high" else " ✨中"
            print(f"    [{h.id}] {h.name} ({sev})")
            print(f"       证据: {h.evidence}")
            print(f"       建议: {h.suggestion}")
            print()


def test_case_1_by_os():
    """测试用例1：按操作系统维度分析"""
    print("="*70)
    print("🎯 测试1：按操作系统分析（看iOS/Android差异）")
    print("="*70)

    query_request = {
        "metrics": ["impressions", "clicks", "cost", "conversions"],
        "group_by": [{"field": "audience_os"}],
        "time_range": {
            "start_date": "2026-04-21",
            "end_date": "2026-04-27"
        },
        "filters": []
    }

    index, es_query = build_es_query(query_request)
    response = es_client.search(index=index, **es_query)
    data = parse_es_result(response.body, query_request, query_request["group_by"])

    print(f"  查询到 {len(data)} 行数据：")
    for row in data:
        print(f"    - {row.get('name', '未知')}: "
              f"曝光={row.get('impressions',0)}, 点击={row.get('clicks',0)}, "
              f"转化={row.get('conversions',0)}")

    insights = rule_engine.analyze({"data": data}, {})
    print_insights(insights)


def test_case_2_by_hour():
    """测试用例2：按时段维度分析"""
    print("\n" + "="*70)
    print("🎯 测试2：按时段分析（发现低效投放时段）")
    print("="*70)

    query_request = {
        "metrics": ["impressions", "clicks", "cost", "conversions"],
        "group_by": [{"field": "data_hour"}],
        "time_range": {
            "start_date": "2026-04-27",
            "end_date": "2026-04-27"
        },
        "filters": []
    }

    index, es_query = build_es_query(query_request)
    response = es_client.search(index=index, **es_query)
    data = parse_es_result(response.body, query_request, query_request["group_by"])

    print(f"  查询到 {len(data)} 行数据：")
    for row in data:
        impressions = row.get('impressions',0)
        clicks = row.get('clicks',0)
        conversions = row.get('conversions',0)
        ctr = clicks / impressions * 100 if impressions > 0 else 0
        cvr = conversions / clicks * 100 if clicks > 0 else 0
        print(f"    - {row.get('name', '未知')}: "
              f"曝光={impressions}, 点击={clicks}, 转化={conversions}, "
              f"CTR={ctr:.2f}%, CVR={cvr:.2f}%")

    insights = rule_engine.analyze({"data": data}, {})
    print_insights(insights)


def test_case_3_by_interest():
    """测试用例3：按兴趣标签维度分析"""
    print("\n" + "="*70)
    print("🎯 测试3：按兴趣标签分析（发现受众定位偏差）")
    print("="*70)

    query_request = {
        "metrics": ["impressions", "clicks", "cost", "conversions"],
        "group_by": [{"field": "audience_interest"}],
        "time_range": {
            "start_date": "2026-04-21",
            "end_date": "2026-04-27"
        },
        "filters": []
    }

    index, es_query = build_es_query(query_request)
    response = es_client.search(index=index, **es_query)
    data = parse_es_result(response.body, query_request, query_request["group_by"])

    print(f"  查询到 {len(data)} 行数据：")
    for row in data:
        impressions = row.get('impressions',0)
        clicks = row.get('clicks',0)
        conversions = row.get('conversions',0)
        ctr = clicks / impressions * 100 if impressions > 0 else 0
        cvr = conversions / clicks * 100 if clicks > 0 else 0
        print(f"    - {row.get('name', '未知')}: "
              f"CTR={ctr:.2f}%, CVR={cvr:.2f}%")

    insights = rule_engine.analyze({"data": data}, {})
    print_insights(insights)


def test_case_4_by_date():
    """测试用例4：按日期趋势分析"""
    print("\n" + "="*70)
    print("🎯 测试4：按日期趋势分析（检测创意疲劳）")
    print("="*70)

    query_request = {
        "metrics": ["impressions", "clicks", "cost", "conversions"],
        "group_by": [{"field": "data_date"}],
        "time_range": {
            "start_date": "2026-04-21",
            "end_date": "2026-04-27"
        },
        "filters": []
    }

    index, es_query = build_es_query(query_request)
    response = es_client.search(index=index, **es_query)
    data = parse_es_result(response.body, query_request, query_request["group_by"])

    print(f"  查询到 {len(data)} 天数据：")
    for row in data:
        impressions = row.get('impressions',0)
        clicks = row.get('clicks',0)
        ctr = clicks / impressions * 100 if impressions > 0 else 0
        print(f"    - {row.get('name', '未知')}: CTR={ctr:.2f}%")

    insights = rule_engine.analyze({"data": data}, {})
    print_insights(insights)


def test_case_5_by_city():
    """测试用例5：按城市维度分析"""
    print("\n" + "="*70)
    print("🎯 测试5：按城市分析（发现地域饱和/反差亮点）")
    print("="*70)

    query_request = {
        "metrics": ["impressions", "clicks", "cost", "conversions", "reach", "frequency"],
        "group_by": [{"field": "audience_city"}],
        "time_range": {
            "start_date": "2026-04-21",
            "end_date": "2026-04-27"
        },
        "filters": []
    }

    index, es_query = build_es_query(query_request)
    response = es_client.search(index=index, **es_query)
    data = parse_es_result(response.body, query_request, query_request["group_by"])

    print(f"  查询到 {len(data)} 行数据：")
    for row in data:
        impressions = row.get('impressions',0)
        clicks = row.get('clicks',0)
        conversions = row.get('conversions',0)
        cost = row.get('cost',0)
        cpa = cost / conversions if conversions > 0 else float('inf')
        print(f"    - {row.get('name', '未知')}: "
              f"CPA={cpa:.0f}元, 转化={conversions}")

    insights = rule_engine.analyze({"data": data}, {})
    print_insights(insights)


if __name__ == "__main__":
    print("\n" + "🚀"*20)
    print("   洞察规则引擎 - 真实数据验证")
    print("🚀"*20 + "\n")

    try:
        # 运行所有测试用例
        test_case_1_by_os()
        test_case_2_by_hour()
        test_case_3_by_interest()
        test_case_4_by_date()
        test_case_5_by_city()

        print("\n" + "="*70)
        print("✅ 验证完成！")
        print("="*70)

    except Exception as e:
        print(f"\n❌ 验证出错: {e}")
        import traceback
        traceback.print_exc()
