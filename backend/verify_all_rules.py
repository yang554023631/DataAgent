#!/usr/bin/env python3
"""
所有规则验证脚本 - 比对规则阈值与ES中实际数据范围
"""
import sys
sys.path.insert(0, '.')

from src.tools.custom_report_client import es_client, FACT_INDEX

print("="*90)
print("🎯 规则阈值 vs ES实际数据范围 完整比对")
print("="*90)

# 按创意ID聚合查询最近7天数据
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
    creative_id = b['key']
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

# 计算统计数据（不使用numpy）
ctrs = [c['ctr'] for c in creative_data]
cvrs = [c['cvr'] for c in creative_data]
cpcs = [c['cpc'] for c in creative_data]
cpas = [c['cpa'] for c in creative_data if c['cpa'] != float('inf')]

def calc_stats(values, name, unit=""):
    """计算统计数据"""
    if not values:
        return None
    sorted_v = sorted(values)
    n = len(sorted_v)
    min_v = sorted_v[0]
    max_v = sorted_v[-1]
    avg_v = sum(values) / n
    median_v = sorted_v[n // 2] if n % 2 == 1 else (sorted_v[n//2 - 1] + sorted_v[n//2]) / 2
    return {
        "name": name,
        "unit": unit,
        "min": min_v,
        "max": max_v,
        "avg": avg_v,
        "median": median_v,
        "count": n
    }

stats_ctr = calc_stats(ctrs, "CTR", "%")
stats_cvr = calc_stats(cvrs, "CVR", "%")
stats_cpc = calc_stats(cpcs, "CPC", "元")
stats_cpa = calc_stats(cpas, "CPA", "元")

print(f"\n📊 ES实际数据统计 (样本数: {len(creative_data)} 个创意)")
print("-"*90)
print(f"{'指标':<10} {'最小值':<15} {'最大值':<15} {'平均值':<15} {'中位数':<15}")
print("-"*90)

def fmt(v, unit, mult=1):
    if unit == "%":
        return f"{v*mult*100:.2f}%"
    elif unit == "元":
        return f"{v*mult:.2f}元"
    return f"{v*mult:.2f}"

for s in [stats_ctr, stats_cvr, stats_cpc, stats_cpa]:
    print(f"{s['name']:<10} {fmt(s['min'], s['unit']):<15} {fmt(s['max'], s['unit']):<15} {fmt(s['avg'], s['unit']):<15} {fmt(s['median'], s['unit']):<15}")

print("\n" + "="*90)
print("🔴 问题识别规则阈值比对 (P01-P09)")
print("="*90)

problem_rules = [
    {
        "id": "P01",
        "name": "受众定位偏差",
        "condition": "CTR 1%-3% AND CVR < 0.5%",
        "thresholds": ["CTR: 1.0%-3.0%", "CVR: < 0.5%"],
        "actual_vs": [
            f"CTR范围: {stats_ctr['min']*100:.2f}%-{stats_ctr['max']*100:.2f}%",
            f"CVR范围: {stats_cvr['min']*100:.2f}%-{stats_cvr['max']*100:.2f}%"
        ],
        "can_trigger": stats_cvr['min'] < 0.005
    },
    {
        "id": "P02",
        "name": "创意疲劳衰减",
        "condition": "连续3天CTR下降，降幅>20%",
        "thresholds": ["CTR降幅: > 20%"],
        "actual_vs": ["需要时序数据检测"],
        "can_trigger": "需时序数据"
    },
    {
        "id": "P03",
        "name": "时段投放浪费",
        "condition": "某时段消耗占比>20%且CPA是其他1.5倍",
        "thresholds": ["消耗占比: > 20%", "CPA倍数: >= 1.5x"],
        "actual_vs": [f"CPA极差: {max(cpas)/min(cpas):.1f}x"],
        "can_trigger": max(cpas)/min(cpas) >= 1.5 if cpas else False
    },
    {
        "id": "P04",
        "name": "频次失控",
        "condition": ">=10次用户消耗>30%但转化<5%",
        "thresholds": ["频次: >= 10", "消耗占比: >30%"],
        "actual_vs": ["需频次分布数据"],
        "can_trigger": "需频次数据"
    },
    {
        "id": "P05",
        "name": "流量作弊嫌疑",
        "condition": "CTR > 10% 且 跳出率 > 90%",
        "thresholds": ["CTR: > 10.0%", "跳出率: > 90%"],
        "actual_vs": [f"CTR最大值: {stats_ctr['max']*100:.2f}%"],
        "can_trigger": stats_ctr['max'] > 0.1
    },
    {
        "id": "P06",
        "name": "出价策略异常",
        "condition": "CPC环比翻倍 (>100%)",
        "thresholds": ["CPC变化: > 100%"],
        "actual_vs": ["需环比数据"],
        "can_trigger": "需环比数据"
    },
    {
        "id": "P07",
        "name": "地域渗透饱和",
        "condition": "覆盖>80% 且 CPA是其他1.5倍",
        "thresholds": ["覆盖: > 80%", "CPA倍数: >= 1.5x"],
        "actual_vs": ["需地域覆盖数据"],
        "can_trigger": "需地域数据"
    },
    {
        "id": "P08",
        "name": "设备兼容问题",
        "condition": "最差设备CTR <= 最好设备/3",
        "thresholds": ["CTR倍数: <= 0.33x"],
        "actual_vs": ["需分设备数据"],
        "can_trigger": "需设备数据"
    },
    {
        "id": "P09",
        "name": "竞品活动冲击",
        "condition": "CPC涨50%+ 且 CTR降30%+",
        "thresholds": ["CPC上涨: > 50%", "CTR下降: > 30%"],
        "actual_vs": ["需时序环比数据"],
        "can_trigger": "需环比数据"
    },
]

print(f"\n{'规则':<5} {'名称':<18} {'阈值条件':<25} {'实际ES范围':<25} {'能否触发':<10}")
print("-"*90)
for r in problem_rules:
    can = "✅ 可能" if r['can_trigger'] is True else ("❌ 不可能" if r['can_trigger'] is False else "⚠️ 需数据")
    print(f"{r['id']:<5} {r['name']:<18} {r['thresholds'][0]:<25} {r['actual_vs'][0]:<25} {can:<10}")
    for i in range(1, max(len(r['thresholds']), len(r['actual_vs']))):
        t = r['thresholds'][i] if i < len(r['thresholds']) else ""
        a = r['actual_vs'][i] if i < len(r['actual_vs']) else ""
        print(f"{'':<5} {'':<18} {t:<25} {a:<25} {'':<10}")

print("\n" + "="*90)
print("🟢 亮点识别规则阈值比对 (A01-A10)")
print("="*90)

highlight_rules = [
    {
        "id": "A01",
        "name": "CTR表现优异",
        "condition": "CTR > 基准3倍 (默认基准1.5% → 4.5%)",
        "thresholds": ["CTR: > 4.5%"],
        "actual_vs": [f"CTR最大值: {stats_ctr['max']*100:.2f}%"],
        "can_trigger": stats_ctr['max'] > 0.045,
        "suggest": f"建议阈值: > {stats_ctr['avg']*100*1.3:.2f}% (均值的130%)"
    },
    {
        "id": "A02",
        "name": "CVR表现优异",
        "condition": "CVR > 基准3倍 (默认基准3% → 9%)",
        "thresholds": ["CVR: > 9.0%"],
        "actual_vs": [f"CVR最大值: {stats_cvr['max']*100:.2f}%"],
        "can_trigger": stats_cvr['max'] > 0.09,
        "suggest": f"建议阈值: > {stats_cvr['avg']*100*1.3:.2f}% (均值的130%)"
    },
    {
        "id": "A03",
        "name": "CPC成本优势",
        "condition": "CPC < 均价50% (默认基准2元 → < 1元)",
        "thresholds": ["CPC: < 1.00元"],
        "actual_vs": [f"CPC最小值: {stats_cpc['min']:.2f}元"],
        "can_trigger": stats_cpc['min'] < 1.0,
        "suggest": f"建议阈值: < {stats_cpc['avg']*0.7:.2f}元 (均值的70%)"
    },
    {
        "id": "A04",
        "name": "消耗曲线健康",
        "condition": "预算利用率>90%，变异系数<0.2",
        "thresholds": ["预算利用率: > 90%", "变异系数: < 0.2"],
        "actual_vs": ["需日消耗分布数据"],
        "can_trigger": "需消耗数据",
        "suggest": "基于数据特征动态计算"
    },
    {
        "id": "A05",
        "name": "频次控制良好",
        "condition": "平均频次 1.5-2.5次",
        "thresholds": ["频次: 1.5-2.5"],
        "actual_vs": ["需频次分布数据"],
        "can_trigger": "需频次数据",
        "suggest": "可根据业务调整"
    },
    {
        "id": "A06",
        "name": "转化节奏理想",
        "condition": "24h转化占比 > 80%",
        "thresholds": ["24h转化占比: > 80%"],
        "actual_vs": ["需转化时间数据"],
        "can_trigger": "需转化数据",
        "suggest": "可根据业务调整"
    },
    {
        "id": "A07",
        "name": "分时段反差亮点",
        "condition": "某时段CVR > 整体3倍",
        "thresholds": ["CVR倍数: >= 3.0x"],
        "actual_vs": [f"CVR极差: {stats_cvr['max']/stats_cvr['min']:.1f}x"],
        "can_trigger": stats_cvr['max'] >= stats_cvr['min'] * 3,
        "suggest": f"建议阈值: >= 2.0x (当前最大差 {stats_cvr['max']/stats_cvr['min']:.1f}x)"
    },
    {
        "id": "A08",
        "name": "分设备反差亮点",
        "condition": "某设备ROI > 其他2倍",
        "thresholds": ["ROI倍数: >= 2.0x"],
        "actual_vs": ["需分设备ROI数据"],
        "can_trigger": "需设备数据",
        "suggest": "建议阈值: >= 1.5x"
    },
    {
        "id": "A09",
        "name": "分素材反差亮点",
        "condition": "CTR < 1% 且 CVR > 5%",
        "thresholds": ["CTR: < 1.0%", "CVR: > 5.0%"],
        "actual_vs": [
            f"CTR最小值: {stats_ctr['min']*100:.2f}%",
            f"CVR最大值: {stats_cvr['max']*100:.2f}%"
        ],
        "can_trigger": stats_ctr['min'] < 0.01 and stats_cvr['max'] > 0.05,
        "suggest": "建议: CTR < 均值*0.7 且 CVR > 均值*1.3"
    },
    {
        "id": "A10",
        "name": "展示份额优势",
        "condition": "展示份额 > 60%",
        "thresholds": ["展示份额: > 60%"],
        "actual_vs": ["需竞对数据"],
        "can_trigger": "需竞对数据",
        "suggest": "根据市场竞争度调整"
    },
]

print(f"\n{'规则':<5} {'名称':<18} {'阈值条件':<25} {'实际ES范围':<25} {'能否触发':<10}")
print("-"*90)
for r in highlight_rules:
    can = "✅ 可能" if r['can_trigger'] is True else ("❌ 不可能" if r['can_trigger'] is False else "⚠️ 需数据")
    print(f"{r['id']:<5} {r['name']:<18} {r['thresholds'][0]:<25} {r['actual_vs'][0]:<25} {can:<10}")
    for i in range(1, max(len(r['thresholds']), len(r['actual_vs']))):
        t = r['thresholds'][i] if i < len(r['thresholds']) else ""
        a = r['actual_vs'][i] if i < len(r['actual_vs']) else ""
        print(f"{'':<5} {'':<18} {t:<25} {a:<25} {'':<10}")

print("\n" + "="*90)
print("💡 核心问题总结")
print("="*90)

triggerable = sum(1 for r in problem_rules + highlight_rules if r['can_trigger'] is True)
not_triggerable = sum(1 for r in problem_rules + highlight_rules if r['can_trigger'] is False)
need_data = sum(1 for r in problem_rules + highlight_rules if r['can_trigger'] not in [True, False])

print(f"\n总规则数: {len(problem_rules) + len(highlight_rules)}")
print(f"  - 可能触发: {triggerable} 条")
print(f"  - 不可能触发: {not_triggerable} 条")
print(f"  - 需更多数据: {need_data} 条")

print(f"\n❌ 绝对不可能触发的规则 (当前绝对阈值与数据不匹配):")
for r in problem_rules + highlight_rules:
    if r['can_trigger'] is False:
        print(f"   {r['id']} {r['name']}: {r['condition']}")
        if 'suggest' in r:
            print(f"      → {r['suggest']}")

print(f"\n✅ 可能触发的规则:")
for r in problem_rules + highlight_rules:
    if r['can_trigger'] is True:
        print(f"   {r['id']} {r['name']}")

print("\n" + "="*90)
print("🔧 建议的改进方向")
print("="*90)
print("""
1. 【最大问题】绝对阈值与实际数据严重脱节：
   - CTR 基准 4.5% vs 实际最高 2.89%  → 永远无法触发
   - CVR 基准 9% vs 实际最高 3.97%   → 永远无法触发

2. 改为相对阈值（与数据集内均值比较）：
   - "表现优异" = > 均值的 130%
   - "表现很差" = < 均值的 70%

3. 相对阈值的优势：
   - 自动适应不同渠道/广告主的数据分布
   - 总能发现最好/最差的 15-20% 的对象
   - 不需要人工频繁调整基准值
""")
print("="*90)
