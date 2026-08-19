#!/usr/bin/env python3
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Check what data_date looks like in actual data
query = {
    "bool": {
        "must": [
            {"terms": {"campaign_id": [13]}},
            {"terms": {"advertiser_id": [6]}}
        ]
    }
}
result = es.search(index="ad_stat_data", query=query, size=5)
print(f"Total hits: {result['hits']['total']['value']}")
print()
for i, hit in enumerate(result['hits']['hits']):
    source = hit['_source']
    print(f"Hit {i+1}:")
    print(f"  data_date: {source.get('data_date')} (type: {type(source.get('data_date'))})")
    print(f"  data_type: {source.get('data_type')}")
    print(f"  data_value: {source.get('data_value')}")
    print(f"  campaign_id: {source.get('campaign_id')}")
    print(f"  advertiser_id: {source.get('advertiser_id')}")
    print()
