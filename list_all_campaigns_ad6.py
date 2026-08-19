#!/usr/bin/env python3
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Get all campaigns for advertiser 6
query = {
    "bool": {
        "must": [
            {"terms": {"advertiser_id": [6]}}
        ]
    }
}

result = es.search(index="campaign", query=query, size=50)
print(f"Found {result['hits']['total']['value']} campaigns for advertiser 6:")
print()

campaign_ids_with_data = []

for hit in result['hits']['hits']:
    source = hit['_source']
    cid = int(source['campaign_id'])
    name = source['campaign_name']
    status = source['status']

    # Check fact table
    q_fact = {
        "bool": {
            "must": [
                {"terms": {"advertiser_id": [6]}},
                {"terms": {"campaign_id": [cid]}}
            ]
        }
    }
    r_fact = es.search(index="ad_stat_data", query=q_fact, size=0)
    total = r_fact['hits']['total']['value']

    mark = "✅" if total > 0 else "❌"
    print(f"{mark} {cid:3d}: name='{name}' status={status} fact_rows={total}")

    if total > 0:
        campaign_ids_with_data.append((cid, name, total))

print()
print(f"Summary: {len(campaign_ids_with_data)} campaigns have fact data:")
for cid, name, total in campaign_ids_with_data:
    print(f"  {cid}: {name} ({total} rows)")
