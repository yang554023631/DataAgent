#!/usr/bin/env python3
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# After filter: entity_ids = [14], level = campaign
entity_ids = [14]
advertiser_ids = [6]
start_date = "2000-01-01"
end_date = "2026-08-17"

filters = [
    {
        "range": {
            "data_date": {
                "gte": start_date,
                "lte": end_date
            }
        }
    },
    {"terms": {"advertiser_id": advertiser_ids}},
    {"terms": {"campaign_id": entity_ids}}
]

# Check doc count
dsl = {
    "query": {"bool": {"filter": filters}},
    "size": 0
}

result = es.search(index="ad_stat_data", body=dsl)
print(f"Total docs: {result['hits']['total']['value']}")

# Check sum of core metrics (cost = data_type 3, impressions = data_type 1)
dsl_agg = {
    "query": {"bool": {"filter": filters}},
    "size": 0,
    "aggs": {
        "cost": {
            "filter": {"term": {"data_type": 3}},
            "aggs": {"total": {"sum": {"field": "data_value"}}}
        },
        "impressions": {
            "filter": {"term": {"data_type": 1}},
            "aggs": {"total": {"sum": {"field": "data_value"}}}
        }
    }
}

result2 = es.search(index="ad_stat_data", body=dsl_agg)
cost = result2['aggregations']['cost']['total']['value']
impressions = result2['aggregations']['impressions']['total']['value']

print(f"Sum cost: {cost}")
print(f"Sum impressions: {impressions}")
print(f"Total sum > 0: {cost + impressions > 0}")
