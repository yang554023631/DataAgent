#!/usr/bin/env python3
"""
从ES全量数据计算百分位阈值并更新配置文件
用法: python tools/calc_percentile_thresholds.py --days 30
"""
import sys
import yaml
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, '.')

from src.tools.custom_report_client import es_client, FACT_INDEX


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


def fetch_all_creative_data(days=30):
    """从ES获取指定天数内的所有素材数据"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    print(f"📊 查询ES数据: {start_date.date()} ~ {end_date.date()} (最近{days}天)")

    query = {
        "query": {
            "bool": {
                "must": [
                    {"range": {"data_date": {
                        "gte": start_date.strftime("%Y-%m-%d"),
                        "lte": end_date.strftime("%Y-%m-%d")
                    }}}
                ]
            }
        },
        "size": 0,
        "aggs": {
            "by_creative": {
                "terms": {"field": "creative_id", "size": 10000},  # 最多1万个素材
                "aggs": {
                    "impressions": {
                        "filter": {"term": {"data_type": 1}},
                        "aggs": {"value": {"sum": {"field": "data_value"}}}
                    },
                    "clicks": {
                        "filter": {"term": {"data_type": 2}},
                        "aggs": {"value": {"sum": {"field": "data_value"}}}
                    },
                    "cost": {
                        "filter": {"term": {"data_type": 3}},
                        "aggs": {"value": {"sum": {"field": "data_value"}}}
                    },
                    "conversions": {
                        "filter": {"term": {"data_type": 4}},
                        "aggs": {"value": {"sum": {"field": "data_value"}}}
                    },
                }
            }
        },
        "timeout": "60s"
    }

    response = es_client.search(index=FACT_INDEX, **query)
    buckets = response['aggregations']['by_creative']['buckets']

    print(f"✅ 查询到 {len(buckets)} 个有效素材")
    return buckets


def calculate_metrics(buckets):
    """计算所有素材的CTR/CVR/CPC/CPA"""
    ctrs = []
    cvrs = []
    cpcs = []
    cpas = []

    for b in buckets:
        impressions = b['impressions']['value']['value']
        clicks = b['clicks']['value']['value']
        cost = b['cost']['value']['value']
        conversions = b['conversions']['value']['value']

        if impressions > 100:  # 过滤曝光太少的无效数据
            ctr = clicks / impressions if clicks > 0 else 0
            ctrs.append(ctr)

            if clicks > 0:
                cvr = conversions / clicks if conversions > 0 else 0
                cpc = cost / clicks if cost > 0 else 0
                cvrs.append(cvr)
                cpcs.append(cpc)

                if conversions > 0:
                    cpa = cost / conversions
                    cpas.append(cpa)

    print(f"\n📈 有效数据量:")
    print(f"  CTR: {len(ctrs)} 个素材")
    print(f"  CVR: {len(cvrs)} 个素材")
    print(f"  CPC: {len(cpcs)} 个素材")
    print(f"  CPA: {len(cpas)} 个素材")

    return {
        'ctrs': sorted(ctrs),
        'cvrs': sorted(cvrs),
        'cpcs': sorted(cpcs),
        'cpas': sorted(cpas)
    }


def calculate_thresholds(metrics):
    """计算各百分位阈值"""
    thresholds = {}

    # CTR阈值
    thresholds['A01_high_ctr'] = percentile(metrics['ctrs'], 80)  # P80 (下限)
    thresholds['A01_high_ctr_upper'] = percentile(metrics['ctrs'], 97)  # P97 (上限，避免与异常重叠)
    thresholds['P05_low_ctr'] = percentile(metrics['ctrs'], 5)    # P5
    thresholds['P05_high_ctr'] = percentile(metrics['ctrs'], 98)   # P98
    thresholds['A09_low_ctr'] = percentile(metrics['ctrs'], 15)    # P15

    # CVR阈值
    thresholds['A02_high_cvr'] = percentile(metrics['cvrs'], 80)  # P80
    thresholds['A07_high_cvr'] = percentile(metrics['cvrs'], 85)  # P85
    thresholds['A09_high_cvr'] = percentile(metrics['cvrs'], 85)  # P85
    thresholds['P01_low_cvr'] = percentile(metrics['cvrs'], 20)   # P20

    # CPC阈值（越低越好，所以P20是"好"的阈值）
    thresholds['A03_low_cpc'] = percentile(metrics['cpcs'], 20)   # P20

    # CPA阈值（越高越差，所以P80是"差"的阈值）
    thresholds['P03_high_cpa'] = percentile(metrics['cpas'], 80)  # P80

    return thresholds


def print_thresholds(thresholds):
    """打印阈值表格"""
    print("\n" + "="*80)
    print("🎯 推荐阈值配置")
    print("="*80)
    print(f"\n{'规则':<20} {'百分位':<10} {'推荐阈值':<15} {'说明'}")
    print("-"*80)
    print(f"A01 CTR表现优异     P80~P97   {thresholds['A01_high_ctr']*100:.2f}%~{thresholds['A01_high_ctr_upper']*100:.2f}%  CTR在此区间视为优质")
    print(f"A02 CVR表现优异     P80       {thresholds['A02_high_cvr']*100:.2f}%{' '*8} CVR >= {thresholds['A02_high_cvr']*100:.2f}%")
    print(f"A03 CPC成本优势     P20       {thresholds['A03_low_cpc']:.2f}元{' '*10} CPC <= {thresholds['A03_low_cpc']:.2f}元")
    print(f"A07 CVR反差亮点     P85       {thresholds['A07_high_cvr']*100:.2f}%{' '*8} CVR >= {thresholds['A07_high_cvr']*100:.2f}%")
    print(f"A09 精准定向潜力股  P15/P85   {thresholds['A09_low_ctr']*100:.2f}%/{thresholds['A09_high_cvr']*100:.2f}%  CTR低但CVR高")
    print(f"P01 CVR转化低下     P20       {thresholds['P01_low_cvr']*100:.2f}%{' '*8} CVR <= {thresholds['P01_low_cvr']*100:.2f}%")
    print(f"P03 CPA成本过高     P80       {thresholds['P03_high_cpa']:.2f}元{' '*9} CPA >= {thresholds['P03_high_cpa']:.2f}元")
    print(f"P05 CTR异常波动     P5/P98    {thresholds['P05_low_ctr']*100:.2f}%/{thresholds['P05_high_ctr']*100:.2f}%   区间外视为异常")
    print("="*80)


def update_config_file(thresholds, config_path='config/insight_rules.yaml'):
    """更新配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 更新亮点规则
    config['highlight_rules']['A01_high_ctr']['threshold'] = round(thresholds['A01_high_ctr'], 5)
    config['highlight_rules']['A01_high_ctr']['upper_threshold'] = round(thresholds['A01_high_ctr_upper'], 5)
    config['highlight_rules']['A02_high_cvr']['threshold'] = round(thresholds['A02_high_cvr'], 5)
    config['highlight_rules']['A03_low_cpc']['threshold'] = round(thresholds['A03_low_cpc'], 2)
    config['highlight_rules']['A07_cvr_contrast']['threshold'] = round(thresholds['A07_high_cvr'], 5)
    config['highlight_rules']['A09_ctr_low_cvr_high']['ctr_threshold'] = round(thresholds['A09_low_ctr'], 5)
    config['highlight_rules']['A09_ctr_low_cvr_high']['cvr_threshold'] = round(thresholds['A09_high_cvr'], 5)

    # 更新问题规则
    config['problem_rules']['P01_low_cvr']['threshold'] = round(thresholds['P01_low_cvr'], 5)
    config['problem_rules']['P03_high_cpa']['threshold'] = round(thresholds['P03_high_cpa'], 2)
    config['problem_rules']['P05_ctr_anomaly']['low_threshold'] = round(thresholds['P05_low_ctr'], 5)
    config['problem_rules']['P05_ctr_anomaly']['high_threshold'] = round(thresholds['P05_high_ctr'], 5)

    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"\n✅ 配置文件已更新: {config_path}")


def main():
    parser = argparse.ArgumentParser(description='从ES计算百分位阈值并更新配置')
    parser.add_argument('--days', type=int, default=30, help='查询最近N天数据（默认30天）')
    parser.add_argument('--dry-run', action='store_true', help='仅计算不更新配置文件')
    args = parser.parse_args()

    # 1. 获取数据
    buckets = fetch_all_creative_data(days=args.days)

    if len(buckets) < 100:
        print("⚠️  数据量太少，建议增加查询天数或检查ES数据")
        return

    # 2. 计算指标
    metrics = calculate_metrics(buckets)

    # 3. 计算阈值
    thresholds = calculate_thresholds(metrics)

    # 4. 打印结果
    print_thresholds(thresholds)

    # 5. 更新配置文件
    if not args.dry_run:
        update_config_file(thresholds)
        print("\n✨ 完成！规则引擎将在下一次重启后使用新阈值")
    else:
        print("\n📝 (dry-run模式，未更新配置文件)")


if __name__ == '__main__':
    main()
