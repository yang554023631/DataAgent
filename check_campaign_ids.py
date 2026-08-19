#!/usr/bin/env python3
import sys
sys.path.insert(0, './backend')
from src.tools.custom_report_client import es_client

# 检查campaign索引是否存在
if not es_client.indices.exists(index='campaign'):
    print('❌ campaign index does NOT exist')
    sys.exit(1)

print('✅ campaign index exists')

# 查询ID 12和13
query = {
    'query': {'terms': {'campaign_id': [12, 13]}},
    'size': 10,
    '_source': ['campaign_id', 'campaign_name']
}
response = es_client.search(index='campaign', **query)
hits = response['hits']['hits']
print(f'\nFound {len(hits)} hits for campaign_id 12, 13:')
for hit in hits:
    source = hit['_source']
    cid = source.get('campaign_id')
    cname = source.get('campaign_name')
    print(f'  - campaign_id={cid}, campaign_name={repr(cname)}')
