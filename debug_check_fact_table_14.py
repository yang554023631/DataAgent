#!/usr/bin/env python3
import sys
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Check how many documents exist for campaign_id=14 in ad_stat_data
dsl = {
  "query": {
    "bool": {
      "filter": [
        {"terms": {"advertiser_id": [6]}},
        {"terms": {"campaign_id": [14]}}
      ]
    }
  },
  "size": 5
}

response = es.search(index="ad_stat_data", body=dsl)
print(f"Total hits: {response['hits']['total']['value']}")
print()
if response['hits']['total']['value'] > 0:
    for i, hit in enumerate(response['hits']['hits']):
        source = hit['_source']
        print(f"Hit {i+1}:")
        print(f"  advertiser_id: {source.get('advertiser_id')}")
        print(f"  campaign_id: {source.get('campaign_id')}")
        print(f"  data_date: {source.get('data_date')}")
        print(f"  data_type: {source.get('data_type')}")
        print(f"  data_value: {source.get('data_value')}")
