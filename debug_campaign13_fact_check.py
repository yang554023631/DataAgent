#!/usr/bin/env python3
import sys
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Check fact table for campaign 13 (case 18)
dsl = {
  "query": {
    "bool": {
      "filter": [
        {"terms": {"advertiser_id": [6]}},
        {"terms": {"campaign_id": [13]}}
      ]
    }
  },
  "size": 0
}

response = es.search(index="ad_stat_data", body=dsl)
total = response['hits']['total']['value']
print(f"Total docs for advertiser=6, campaign=13: {total}")

# Let's also check with data_type=1 (cost)
dsl_cost = {
  "query": {
    "bool": {
      "filter": [
        {"terms": {"advertiser_id": [6]}},
        {"terms": {"campaign_id": [13]}},
        {"terms": {"data_type": [1]}}
      ]
    }
  },
  "size": 0
}
response_cost = es.search(index="ad_stat_data", body=dsl_cost)
total_cost = response_cost['hits']['total']['value']
print(f"Total cost docs: {total_cost}")
