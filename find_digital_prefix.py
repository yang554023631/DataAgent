#!/usr/bin/env python3
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Search for any campaign name starts with or contains 'digital'
query = {
    "bool": {
        "must": [
            {"terms": {"advertiser_id": [6]}},
            {"wildcard": {"campaign_name": "*digital*"}}
        ]
    }
}

result = es.search(index="campaign", query=query, size=100)
print(f"Found {result['hits']['total']['value']} campaigns:")
for hit in result['hits']['hits']:
    source = hit['_source']
    cid = int(source['campaign_id'])
    name = source['campaign_name']
    status = source['status']

    # Check fact data
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
