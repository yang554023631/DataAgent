#!/usr/bin/env python3
"""
亮点规则验证脚本
验证是否能检测出表现好的广告
"""
import sys
sys.path.insert(0, '.')

from src.tools.custom_report_client import es_client, FACT_INDEX
from src.tools.insight_rules import rule_engine

print("="*70)
print("🎯 测试：按创意ID分析 - 看规则能否检测出优质/劣质素材")
print("="*70)

# 按 creative_id 维度聚合查询
query = {
    "query": {
        "bool": {
            "must": [
                {"range": {"data_date": {"gte": "2026-04-21", "lte": "2026-04-27"}}}
            ]
        }
    },
    "size": 0,
    "aggs": {
        "by_creative": {
            "terms": {"field": "creative_id", "size": 100},
            "aggs": {
                "impressions": {"filter": {"term": {"data_type": 1}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                "clicks": {"filter": {"term": {"data_type": 2}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                "cost": {"filter": {"term": {"data_type": 3}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
                "conversions": {"filter": {"term": {"data_type": 4}}, "aggs": {"value": {"sum": {"field": "data_value"}}}},
            }
        }
    },
    "timeout": "30s"
}

response = es_client.search(index=FACT_INDEX, **query)
buckets = response['aggregations']['by_creative']['buckets']

creative_data = []
for b in buckets:
    creative_id = b['key']
    impressions = b['impressions']['value']['value']
    clicks = b['clicks']['value']['value']
    cost = b['cost']['value']['value']
    conversions = b['conversions']['value']['value']

    ctr = clicks / impressions if impressions > 0 else 0
    cvr = conversions / clicks if clicks > 0 else 0
    cpa = cost / conversions if conversions > 0 else float('inf')
    cpc = cost / clicks if clicks > 0 else 0

    creative_data.append({
        "name": f"创意{creative_id}",
        "id": creative_id,
        "impressions": impressions,
        "clicks": clicks,
        "cost": cost,
        "conversions": conversions,
        "ctr": ctr,
        "cvr": cvr,
        "cpc": cpc,
        "cpa": cpa
    })

# 计算整体均值
avg_ctr = sum(c['ctr'] for c in creative_data) / len(creative_data)
avg_cvr = sum(c['cvr'] for c in creative_data) / len(creative_data)
avg_cpc = sum(c['cpc'] for c in creative_data if c['cpc'] != float('inf')) / len([c for c in creative_data if c['cpc'] != float('inf')])
avg_cpa = sum(c['cpa'] for c in creative_data if c['cpa'] != float('inf')) / len([c for c in creative_data if c['cpa'] != float('inf')])

print(f"\n  📊 整体均值：")
print(f"     CTR: {avg_ctr*100:.2f}%")
print(f"     CVR: {avg_cvr*100:.2f}%")
print(f"     CPC: {avg_cpc:.2f}元")
print(f"     CPA: {avg_cpa:.2f}元")

print(f"\n  🟢 TOP 5 最佳创意（按CVR从高到低）：")
creative_data.sort(key=lambda x: x['cvr'], reverse=True)
for i, c in enumerate(creative_data[:5]):
    diff_ctr = (c['ctr'] - avg_ctr) / avg_ctr * 100
    diff_cvr = (c['cvr'] - avg_cvr) / avg_cvr * 100
    diff_cpa = (c['cpa'] - avg_cpa) / avg_cpa * 100 if c['cpa'] != float('inf') else 0
    print(f"     {i+1}. {c['name']}: CTR={c['ctr']*100:.2f}% ({diff_ctr:+.1f}%), "
          f"CVR={c['cvr']*100:.2f}% ({diff_cvr:+.1f}%), "
          f"CPA={c['cpa']:.2f}元 ({diff_cpa:+.1f}%)")

print(f"\n  🔴 TOP 5 最差创意（按CVR从低到高）：")
for i, c in enumerate(creative_data[-5:][::-1]):
    diff_ctr = (c['ctr'] - avg_ctr) / avg_ctr * 100
    diff_cvr = (c['cvr'] - avg_cvr) / avg_cvr * 100
    diff_cpa = (c['cpa'] - avg_cpa) / avg_cpa * 100 if c['cpa'] != float('inf') else 0
    print(f"     {i+1}. {c['name']}: CTR={c['ctr']*100:.2f}% ({diff_ctr:+.1f}%), "
          f"CVR={c['cvr']*100:.2f}% ({diff_cvr:+.1f}%), "
          f"CPA={c['cpa']:.2f}元 ({diff_cpa:+.1f}%)")

# 喂给规则引擎
print(f"\n{'='*70}")
print("🧠 调用规则引擎分析：")
print("="*70)

insights = rule_engine.analyze({"data": creative_data}, {})
problems = [i for i in insights if i.type.value == "problem"]
highlights = [i for i in insights if i.type.value == "highlight"]

print(f"\n  检测结果：{len(problems)}个问题，{len(highlights)}个亮点")

if highlights:
    print(f"\n  🟢 发现 {len(highlights)} 个亮点：")
    for h in highlights:
        print(f"\n  [{h.id}] {h.name} (价值等级：{h.severity.value})")
        print(f"     证据: {h.evidence}")
        print(f"     建议: {h.suggestion}")
else:
    print("\n  ❌ 没有检测到任何亮点！")
    print(f"\n  让我检查当前各亮点规则的触发阈值：")
    print(f"     A01(CTR优异): > 基准3倍（默认基准1.5% → 需 > 4.5%）")
    print(f"       实际最高CTR: {creative_data[0]['ctr']*100:.2f}%")
    print(f"       结论: {'✅ 超过阈值' if creative_data[0]['ctr'] > 0.045 else '❌ 不够触发'}")

    print(f"\n     A02(CVR优异): > 基准3倍（默认基准3% → 需 > 9%）")
    print(f"       实际最高CVR: {creative_data[0]['cvr']*100:.2f}%")
    print(f"       结论: {'✅ 超过阈值' if creative_data[0]['cvr'] > 0.09 else '❌ 不够触发'}")

    print(f"\n     A03(CPC优势): < 均价50%（默认基准2元 → 需 < 1元）")
    min_cpc = min(c['cpc'] for c in creative_data if c['cpc'] != float('inf'))
    print(f"       实际最低CPC: {min_cpc:.2f}元")
    print(f"       结论: {'✅ 低于阈值' if min_cpc < 1 else '❌ 不够触发'}")

print(f"\n{'='*70}")
print("💡 问题分析：")
print(f"  当前规则用的是『绝对阈值』，设得太极端了！")
print(f"  比如：CVR要 > 9% 才叫优秀，但实际最好的也只有 3.97%")
print(f"  但相对来看，最好的比最差的好 82%，这就是亮点！")
print(f"  建议改为：相对比较（> 均值的 130% 就算亮点）")
print("="*70)
