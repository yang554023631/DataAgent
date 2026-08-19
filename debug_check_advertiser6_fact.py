#!/usr/bin/env python3
import sys
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Check total documents for advertiser 6 in fact table
dsl = {
  "query": {
    "bool": {
      "filter": [
        {"terms": {"advertiser_id": [6]}}
      ]
    }
  },
  "size": 0,
  "aggs": {
    "by_campaign": {
      "terms": {"field": "campaign_id", "size": 20}
    }
  }
}

response = es.search(index="ad_stat_data", body=dsl)
total = response['hits']['total']['value']
print(f"Total documents for advertiser 6: {total}")
print()

agg = response.get('aggregations', {})
by_campaign = agg.get('by_campaign', {})
buckets = by_campaign.get('buckets', [])
print(f"Top campaign_ids with data:")
for b in buckets:
    print(f"  campaign_id={b['key']}, doc_count={b['doc_count']}")
