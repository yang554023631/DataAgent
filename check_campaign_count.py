#!/usr/bin/env python3
import os
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
load_dotenv()

ES_URL = os.getenv('ES_URL')
ES_USER = os.getenv('ES_USER')
ES_PASSWORD = os.getenv('ES_PASSWORD')

if ES_USER and ES_PASSWORD:
    es = Elasticsearch(ES_URL, basic_auth=(ES_USER, ES_PASSWORD))
else:
    es = Elasticsearch(ES_URL)

# 查询campaign索引中广告主6有多少campaign
query = {
    'query': {
        'term': {'advertiser_id': '6'}
    }
}
result = es.count(index='campaign', body=query)
print(f'📊 广告主6总共有 {result["count"]} 个广告计划')

# 查询ad_stat_data中广告主6 4月份有数据的campaign
query = {
    'size': 0,
    'query': {
        'bool': {
            'filter': [
                {'term': {'advertiser_id': '6'}},
                {'range': {'date': {'gte': '2026-04-01', 'lte': '2026-04-30'}}
            ]
        }
    },
    'aggs': {
        'campaign_ids': {'terms': {'field': 'campaign_id', 'size': 100}}
    }
}
result = es.search(index='ad_stat_data', body=query)
buckets = result['aggregations']['campaign_ids']['buckets']
print(f'📊 广告主6 4月份有数据的广告计划数量: {len(buckets)}')
print(f'📋 广告计划ID列表: {[b["key"] for b in buckets]}')
