#!/usr/bin/env python3
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# The query that should now work
query = {
  "bool": {
    "must": [
      {
        "range": {
          "data_date": {
            "gte": "2000-01-01",
            "lte": "2026-08-16"
          }
        }
      },
      {
        "terms": {
          "advertiser_id": [
            6
          ]
        }
      },
      {
        "terms": {
          "campaign_id": [
            10,
            12,
            13,
            15,
            16,
            17,
            18,
            19,
            20
          ]
        }
      },
      {
        "terms": {
          "campaign_id": [
            13
          ]
        }
      }
    ]
  }
}

result = es.search(index="ad_stat_data", query=query, size=0, aggs={
    "group_0": {
      "terms": {"field": "campaign_id", "size": 1000},
      "aggs": {
        "group_1": {
          "terms": {"field": "campaign_id", "size": 1000},
          "aggs": {
            "sum_cost": {
              "filter": {"term": {"data_type": 3}},
              "aggs": {"value": {"sum": {"field": "data_value"}}}
            },
            "sum_clicks": {
              "filter": {"term": {"data_type": 2}},
              "aggs": {"value": {"sum": {"field": "data_value"}}}
            }
          }
        }
      }
    }
})

print(f"Total matching docs: {result['hits']['total']['value']}")
print(f"Number of aggregation buckets: {len(result['aggregations']['group_0']['buckets'])}")
for bucket in result['aggregations']['group_0']['buckets']:
    print(f"  bucket {bucket['key']}:")
    for sub_bucket in bucket['group_1']['buckets']:
        cost = sub_bucket['sum_cost']['value']['value']
        clicks = sub_bucket['sum_clicks']['value']['value']
        print(f"    cost={cost}, clicks={clicks}")
