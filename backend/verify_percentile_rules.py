#!/usr/bin/env python3
"""
百分位数阈值验证
使用百分位数替代绝对阈值/均值百分比
"""
import sys
sys.path.insert(0, '.')

from src.tools.custom_report_client import es_client, FACT_INDEX

print("="*80)
print("🎯 百分位数阈值方案验证")
print("="*80)

# 查询数据
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
            "terms": {"field": "creative_id", "size": 1000},
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
    impressions = b['impressions']['value']['value']
    clicks = b['clicks']['value']['value']
    cost = b['cost']['value']['value']
    conversions = b['conversions']['value']['value']

    if impressions > 0 and clicks > 0:
        ctr = clicks / impressions
        cvr = conversions / clicks if clicks > 0 else 0
        cpa = cost / conversions if conversions > 0 else float('inf')
        cpc = cost / clicks if clicks > 0 else 0

        creative_data.append({
            "ctr": ctr, "cvr": cvr, "cpc": cpc, "cpa": cpa
        })

def percentile(sorted_values, p):
    """计算百分位数"""
    n = len(sorted_values)
    if n == 0:
        return None
    k = (n - 1) * p / 100
    f = int(k)
    c = f + 1 if f + 1 < n else f
    if f == c:
        return sorted_values[f]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)

ctrs = sorted([c['ctr'] for c in creative_data])
cvrs = sorted([c['cvr'] for c in creative_data])
cpcs = sorted([c['cpc'] for c in creative_data])
cpas = sorted([c['cpa'] for c in creative_data if c['cpa'] != float('inf')])

print(f"\n📊 数据样本: {len(creative_data)} 个创意")
print("="*80)

# 计算各百分位数
metrics = [
    ("CTR", ctrs, "%", 100),
    ("CVR", cvrs, "%", 100),
    ("CPC", cpcs, "元", 1),
    ("CPA", cpas, "元", 1)
]

print(f"\n{'指标':<8} {'P10(差)':<15} {'P20(较差)':<15} {'P50(中位)':<15} {'P80(较好)':<15} {'P90(好)':<15}")
print("-"*80)

for name, values, unit, mult in metrics:
    p10 = percentile(values, 10)
    p20 = percentile(values, 20)
    p50 = percentile(values, 50)
    p80 = percentile(values, 80)
    p90 = percentile(values, 90)

    def fmt(v):
        if unit == "%":
            return f"{v*mult:.2f}%"
        return f"{v*mult:.2f}{unit}"

    print(f"{name:<8} {fmt(p10):<15} {fmt(p20):<15} {fmt(p50):<15} {fmt(p80):<15} {fmt(p90):<15}")

print("\n" + "="*80)
print("🟢 亮点规则 - 百分位数方案 (TOP 20%)")
print("="*80)

highlight_scheme = [
    {
        "rule": "A01 CTR优异",
        "old": "> 4.5% (绝对)",
        "new_scheme": "> P80 (前20%)",
        "threshold": f"> {percentile(ctrs, 80)*100:.2f}%",
        "actual_trigger": f"将触发 {len([c for c in ctrs if c >= percentile(ctrs, 80)])} 个"
    },
    {
        "rule": "A02 CVR优异",
        "old": "> 9.0% (绝对)",
        "new_scheme": "> P80 (前20%)",
        "threshold": f"> {percentile(cvrs, 80)*100:.2f}%",
        "actual_trigger": f"将触发 {len([c for c in cvrs if c >= percentile(cvrs, 80)])} 个"
    },
    {
        "rule": "A03 CPC优势",
        "old": "< 1.00元 (绝对)",
        "new_scheme": "< P20 (后20%)",
        "threshold": f"< {percentile(cpcs, 20):.2f}元",
        "actual_trigger": f"将触发 {len([c for c in cpcs if c <= percentile(cpcs, 20)])} 个"
    },
    {
        "rule": "A07 CVR反差亮点",
        "old": "> 整体3倍",
        "new_scheme": "> P85 (前15%)",
        "threshold": f"> {percentile(cvrs, 85)*100:.2f}%",
        "actual_trigger": f"将触发约15%"
    },
]

print(f"\n{'规则':<18} {'旧阈值(绝对)':<18} {'新方案(百分位)':<18} {'实际阈值':<18} {'触发数量':<10}")
print("-"*80)
for s in highlight_scheme:
    print(f"{s['rule']:<18} {s['old']:<18} {s['new_scheme']:<18} {s['threshold']:<18} {s['actual_trigger']:<10}")

print("\n" + "="*80)
print("🔴 问题规则 - 百分位数方案 (BOTTOM 20%)")
print("="*80)

problem_scheme = [
    {
        "rule": "P01 CVR极低",
        "old": "< 0.5% (绝对)",
        "new_scheme": "< P20 (后20%)",
        "threshold": f"< {percentile(cvrs, 20)*100:.2f}%",
        "actual_trigger": f"将触发 {len([c for c in cvrs if c <= percentile(cvrs, 20)])} 个"
    },
    {
        "rule": "P03 CPA过高",
        "old": "> 其他1.5倍",
        "new_scheme": "> P80 (前20%差)",
        "threshold": f"> {percentile(cpas, 80):.2f}元",
        "actual_trigger": f"将触发 {len([c for c in cpas if c >= percentile(cpas, 80)])} 个"
    },
    {
        "rule": "P05 CTR异常",
        "old": "> 10% (绝对)",
        "new_scheme": "> P95 (异常检测)",
        "threshold": f"> {percentile(ctrs, 95)*100:.2f}%",
        "actual_trigger": f"仅触发极端异常"
    },
]

print(f"\n{'规则':<18} {'旧阈值(绝对)':<18} {'新方案(百分位)':<18} {'实际阈值':<18} {'触发数量':<10}")
print("-"*80)
for s in problem_scheme:
    print(f"{s['rule']:<18} {s['old']:<18} {s['new_scheme']:<18} {s['threshold']:<18} {s['actual_trigger']:<10}")

print("\n" + "="*80)
print("💡 百分位数方案的优势")
print("="*80)
print("""
1. ✅ 自动适应数据分布：不管数据整体高还是低，总能找到TOP/BOTTOM 20%
2. ✅ 触发比例可控：精确控制在 15-20%，不会出现"全是问题"或"没有亮点"
3. ✅ 相对比较公平：在同一个数据集内比较，跨数据集也有统一标准
4. ✅ 鲁棒性强：不受极端值影响（均值受极值影响大，百分位不受）
""")

print("\n" + "="*80)
print("🔧 推荐的百分位映射表")
print("="*80)
print("""
📌 亮点检测（发现亮点 → P80 (前20%)
   - CTR 优异: > P80
   - CVR 优异: > P80
   - CPC 优势: < P20
   - CPA 优势: < P20

🔴 问题检测（发现问题 → P20后20%严重问题)
   - CVR 极低: < P20
   - CPA 过高: > P80
   - CTR 异常: < P10 或 > P95 (异常检测，双向)
   - 反差对比: 某维度 > P85 且 某维度 < P15
""")
print("="*80)
