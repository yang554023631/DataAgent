#!/usr/bin/env python3
import sys
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Search for any campaign with 'digital' in name on advertiser 6
must = [
    {"terms": {"advertiser_id": [6]}},
    {"wildcard": {"campaign_name": "*digital*"}}
]

dsl = {
    "query": {"bool": {"must": must}},
    "size": 10,
}

response = es.search(index="campaign", body=dsl)
print(f"Total matches: {response['hits']['total']['value']}")
print()
for hit in response["hits"]["hits"]:
    source = hit["_source"]
    print(f"campaign_id={source.get('campaign_id')}, name={source.get('campaign_name')}, status={source.get('status')}")
    # Check fact table
    dsl_fact = {
        "query": {"bool": {"filter": [
            {"terms": {"advertiser_id": [6]}},
            {"terms": {"campaign_id": [source.get('campaign_id')]}}
        ]}},
        "size": 0
    }
    fact_resp = es.search(index="ad_stat_data", body=dsl_fact)
    fact_count = fact_resp['hits']['total']['value']
    print(f"  → Fact table docs: {fact_count}")
