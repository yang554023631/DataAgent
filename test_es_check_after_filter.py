#!/usr/bin/env python3
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# After filter: we have entity_ids [13] at level campaign
# Check doc count and sum
filters = [
    {
        "range": {
            "data_date": {
                "gte": "2000-01-01",
                "lte": "2026-08-17"
            }
        }
    },
    {"terms": {"advertiser_id": [6]}},
    {"terms": {"campaign_id": [13]}}
]

# Check doc count
dsl_count = {
    "query": {
        "bool": {
            "filter": filters
        }
    },
    "size": 0
}

result = es.search(index="ad_stat_data", body=dsl_count)
print(f"Total docs: {result['hits']['total']['value']}")

# Check sum for cost (data_type=3)
dsl_sum = {
    "query": {
        "bool": {
            "filter": filters
        }
    },
    "size": 0,
    "aggs": {
        "sum_cost": {
            "filter": {"term": {"data_type": 3}},
            "aggs": {
                "total": {"sum": {"field": "data_value"}}
            }
        }
    }
}

result2 = es.search(index="ad_stat_data", body=dsl_sum)
total = result2['aggregations']['sum_cost']['total']['value']
print(f"Sum of cost: {total}")
print(f"Sum > 0? {total > 0}")
